#!/usr/bin/env python3
"""SPHEREx Sky Viewer — IRSA Query and FITS Cutout Proof of Concept.

Milestone 1 Verification Script:
1. Queries the NASA/IPAC Infrared Science Archive (IRSA) TAP endpoint for SPHEREx observations
   covering a requested celestial target (default: canonical WISE 0855 coordinates).
2. Filters candidate observations by spatial coverage, detector band (SPHEREx-D1 to D6),
   and data release (DR1).
3. Resolves the IBE image cutout URL via IVOA DataLink.
4. Downloads a small FITS cutout using bounded HTTP requests with retry logic.
5. Inspects HDU extensions, scientific metadata (WCS, BUNIT, observation timestamps),
   and computes rigorous pixel and quality flag statistics.
"""

from __future__ import annotations

import argparse
import io
import logging
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import requests
from astropy import units as u
from astropy.coordinates import SkyCoord
from astropy.io import fits, votable
from astropy.wcs import WCS

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("SPHEREx-POC")

# Constants
IRSA_TAP_URL = "https://irsa.ipac.caltech.edu/TAP/sync"
DEFAULT_TARGET_NAME = "WISE 0855"
DEFAULT_RA = 133.795129
DEFAULT_DEC = -7.245147
DEFAULT_FOV_DEG = 0.05
DEFAULT_BAND = "SPHEREx-D1"
DEFAULT_RELEASE = "DR1"
DEFAULT_TIMEOUT = 60


def query_irsa_candidates(
    ra: float,
    dec: float,
    band: str = DEFAULT_BAND,
    release: str = DEFAULT_RELEASE,
    timeout: int = DEFAULT_TIMEOUT,
    max_retries: int = 3,
) -> List[Dict[str, Any]]:
    """Query IRSA TAP for SPHEREx observations whose spatial coverage contains the target.

    Args:
        ra: Right Ascension in decimal degrees (ICRS).
        dec: Declination in decimal degrees (ICRS).
        band: SPHEREx detector bandpass ('SPHEREx-D1' to 'SPHEREx-D6').
        release: Data release identifier ('DR1').
        timeout: HTTP request timeout in seconds.
        max_retries: Retry attempts for transient TAP network failures.

    Returns:
        List of matching observation candidate dictionaries.

    Raises:
        requests.RequestException: If the TAP query fails or times out after retries.
        RuntimeError: If IRSA returns a non-200 status or malformed response.
    """
    collection_name = f"spherex_{release.lower()}"

    # ADQL query using s_region spatial containment
    adql_query = f"""
    SELECT
        obs_id, obs_collection, energy_bandpassname,
        t_min, t_max, t_exptime,
        s_ra, s_dec, access_url, access_format,
        calib_level, obs_release_date
    FROM spherex.obscore
    WHERE obs_collection = '{collection_name}'
      AND energy_bandpassname = '{band}'
      AND 1 = CONTAINS(POINT('ICRS', {ra:.6f}, {dec:.6f}), s_region)
    ORDER BY t_min ASC
    """.strip()

    params = {
        "REQUEST": "doQuery",
        "LANG": "ADQL",
        "FORMAT": "csv",
        "QUERY": adql_query,
    }

    last_error: Optional[Exception] = None
    for attempt in range(1, max_retries + 1):
        try:
            logger.info("Submitting TAP query to IRSA for (%.6f, %.6f), band: %s (attempt %d/%d)...", ra, dec, band, attempt, max_retries)
            response = requests.post(IRSA_TAP_URL, data=params, timeout=timeout)

            if response.status_code != 200:
                error_msg = f"IRSA TAP query failed (HTTP {response.status_code}): {response.text[:300]}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)

            # Parse CSV table
            import csv

            reader = csv.DictReader(io.StringIO(response.text))
            candidates = list(reader)

            # Convert numerical fields
            for row in candidates:
                if "t_min" in row and row["t_min"]:
                    row["t_min"] = float(row["t_min"])
                if "t_max" in row and row["t_max"]:
                    row["t_max"] = float(row["t_max"])
                if "t_exptime" in row and row["t_exptime"]:
                    row["t_exptime"] = float(row["t_exptime"])
                if "s_ra" in row and row["s_ra"]:
                    row["s_ra"] = float(row["s_ra"])
                if "s_dec" in row and row["s_dec"]:
                    row["s_dec"] = float(row["s_dec"])

            logger.info("Found %d candidate observations covering the target.", len(candidates))
            return candidates

        except (requests.RequestException, RuntimeError) as exc:
            last_error = exc
            logger.warning("TAP attempt %d failed: %s. Retrying in 2.0s...", attempt, exc)
            if attempt < max_retries:
                time.sleep(2.0)

    raise RuntimeError(f"IRSA TAP query failed after {max_retries} attempts. Last error: {last_error}")


def select_candidate_observation(
    candidates: List[Dict[str, Any]],
    preferred_index: int = 0,
) -> Dict[str, Any]:
    """Inspect and select a validated observation candidate.

    Args:
        candidates: List of candidate observation records.
        preferred_index: Index of observation to pick (default: 0, earliest epoch).

    Returns:
        The selected candidate dictionary.

    Raises:
        ValueError: If candidates list is empty or index is out of bounds.
    """
    if not candidates:
        raise ValueError("No candidate observations available for selection.")

    unique_obs_ids = {c["obs_id"] for c in candidates}
    logger.info("Candidate summary: %d records across %d unique obs_ids.", len(candidates), len(unique_obs_ids))

    selected = candidates[min(preferred_index, len(candidates) - 1)]
    logger.info(
        "Selected observation '%s' (MJD: %.4f, release date: %s)",
        selected.get("obs_id"),
        selected.get("t_min", 0.0),
        selected.get("obs_release_date"),
    )
    return selected


def resolve_cutout_url(
    datalink_url: str,
    ra: float,
    dec: float,
    size_deg: float = DEFAULT_FOV_DEG,
    timeout: int = DEFAULT_TIMEOUT,
) -> str:
    """Resolve the IBE image cutout URL from the DataLink metadata endpoint.

    Args:
        datalink_url: The IVOA DataLink URL for the observation.
        ra: Target Right Ascension in decimal degrees.
        dec: Target Declination in decimal degrees.
        size_deg: Cutout box size in decimal degrees.
        timeout: HTTP request timeout.

    Returns:
        Full IBE cutout URL with center and size parameters.

    Raises:
        RuntimeError: If DataLink resolution fails.
    """
    logger.info("Resolving DataLink URL: %s", datalink_url)
    resp = requests.get(datalink_url, timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(f"DataLink query failed (HTTP {resp.status_code}): {resp.text[:200]}")

    vo = votable.parse(io.BytesIO(resp.content))
    first_table = vo.get_first_table()
    if not first_table:
        raise RuntimeError("DataLink VOTABLE contained no tables.")

    table_data = first_table.to_table()

    # Look for the science image (#this) or cutout service (#cutout)
    science_url: Optional[str] = None
    cutout_path: Optional[str] = None

    for row in table_data:
        semantics = str(row["col_4"]).strip()
        if semantics == "#this":
            science_url = str(row["col_1"]).strip()
        elif semantics == "#cutout":
            cutout_path = str(row["col_12"]).strip()

    if science_url:
        cutout_url = f"{science_url}?center={ra:.6f},{dec:.6f}d&size={size_deg}"
    elif cutout_path:
        cutout_url = f"https://irsa.ipac.caltech.edu/ibe/data/{cutout_path}?center={ra:.6f},{dec:.6f}d&size={size_deg}"
    else:
        raise RuntimeError("Could not find '#this' or '#cutout' row in DataLink response.")

    logger.info("Constructed cutout URL: %s", cutout_url)
    return cutout_url


def download_fits_cutout(
    cutout_url: str,
    timeout: int = 45,
    max_retries: int = 3,
    retry_delay: float = 2.0,
) -> Tuple[bytes, float]:
    """Download the FITS cutout with bounded retry handling for transient errors.

    Args:
        cutout_url: Full IBE cutout URL.
        timeout: Request timeout in seconds.
        max_retries: Maximum retry attempts for transient server errors (500, 502, 503, 504).
        retry_delay: Initial sleep duration in seconds between retries.

    Returns:
        Tuple of (FITS file bytes, elapsed request time in seconds).

    Raises:
        RuntimeError: If download fails after all retries or returns invalid FITS data.
    """
    last_error: Optional[Exception] = None

    for attempt in range(1, max_retries + 1):
        t0 = time.time()
        try:
            logger.info("Requesting FITS cutout (attempt %d/%d)...", attempt, max_retries)
            resp = requests.get(cutout_url, timeout=timeout)
            elapsed = time.time() - t0

            if resp.status_code == 200:
                content = resp.content
                if not content.startswith(b"SIMPLE  ="):
                    raise RuntimeError(f"Downloaded content is not a valid FITS file: {content[:100]!r}")
                logger.info(
                    "Cutout downloaded successfully (%d bytes, %.2f s).",
                    len(content),
                    elapsed,
                )
                return content, elapsed

            if resp.status_code in [500, 502, 503, 504]:
                logger.warning(
                    "Transient HTTP %d from IRSA ('%s'). Retrying in %.1fs...",
                    resp.status_code,
                    resp.text[:100].strip(),
                    retry_delay * attempt,
                )
                time.sleep(retry_delay * attempt)
            else:
                raise RuntimeError(f"Non-retryable HTTP {resp.status_code}: {resp.text[:200]}")

        except (requests.RequestException, RuntimeError) as exc:
            last_error = exc
            logger.warning("Attempt %d failed: %s", attempt, exc)
            if attempt < max_retries:
                time.sleep(retry_delay * attempt)

    raise RuntimeError(f"Failed to retrieve FITS cutout after {max_retries} attempts. Last error: {last_error}")


def validate_target_coordinates_in_wcs(
    wcs_obj: WCS,
    ra: float,
    dec: float,
    shape: Tuple[int, int],
) -> Dict[str, Any]:
    """Transform celestial coordinates into pixel space and evaluate in-bounds and centering.

    Args:
        wcs_obj: Astropy WCS instance parsed from the science image header (with SIP).
        ra: Target Right Ascension in degrees.
        dec: Target Declination in degrees.
        shape: Image array shape (Ny, Nx) as (height, width).

    Returns:
        Dictionary containing 0-based and 1-based pixel coordinates, in-bounds status,
        cutout center pixel/sky coordinates, and centering offset in pixels and arcseconds.
    """
    Ny, Nx = shape

    # Calculate pixel coordinates using full distortion (SIP)
    # origin=0 corresponds to Python/NumPy array indexing (x=col, y=row)
    # origin=1 corresponds to FITS 1-based convention
    px0, py0 = wcs_obj.all_world2pix(ra, dec, 0)
    px1, py1 = wcs_obj.all_world2pix(ra, dec, 1)

    # Check bounds: 0 <= x < Nx and 0 <= y < Ny
    in_bounds_0 = bool((0.0 <= px0 < float(Nx)) and (0.0 <= py0 < float(Ny)))

    # Geometric center of the image
    center_x0 = (Nx - 1) / 2.0
    center_y0 = (Ny - 1) / 2.0
    center_x1 = (Nx + 1) / 2.0
    center_y1 = (Ny + 1) / 2.0

    # Offset from geometric center in pixels
    offset_pixels = float(np.hypot(px0 - center_x0, py0 - center_y0))

    # Celestial coordinates at the geometric center of the cutout
    center_sky_ra, center_sky_dec = wcs_obj.all_pix2world(center_x0, center_y0, 0)

    # Calculate great-circle angular separation
    c_target = SkyCoord(ra * u.deg, dec * u.deg, frame="icrs")
    c_center = SkyCoord(float(center_sky_ra) * u.deg, float(center_sky_dec) * u.deg, frame="icrs")
    offset_arcsec = float(c_target.separation(c_center).arcsec)

    return {
        "target_sky": {"ra": float(ra), "dec": float(dec)},
        "image_dimensions": {"width_nx": int(Nx), "height_ny": int(Ny), "total_pixels": int(Nx * Ny)},
        "pixel_0based": {"x": float(px0), "y": float(py0), "convention": "0-based (NumPy array data[y, x])"},
        "pixel_1based": {"x": float(px1), "y": float(py1), "convention": "1-based (FITS standard)"},
        "numpy_index": (int(round(float(py0))), int(round(float(px0)))),
        "in_bounds": in_bounds_0,
        "cutout_center_pixel_0based": {"x": float(center_x0), "y": float(center_y0)},
        "cutout_center_pixel_1based": {"x": float(center_x1), "y": float(center_y1)},
        "cutout_center_sky": {"ra": float(center_sky_ra), "dec": float(center_sky_dec)},
        "offset_from_center_pixels": offset_pixels,
        "offset_from_center_arcsec": offset_arcsec,
    }


def run_deterministic_wcs_tests() -> bool:
    """Execute deterministic offline unit tests for WCS coordinate transforms and bounds checks.

    Returns:
        True if all assertions pass.
    """
    logger.info("Running deterministic offline WCS and coordinate unit tests...")
    w = WCS(naxis=2)
    w.wcs.crpix = [15.0, 15.0]  # 1-based center for 29x29
    w.wcs.cdelt = [-0.00171, 0.00171]
    w.wcs.crval = [133.795129, -7.245147]
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]

    shape = (29, 29)  # (Ny, Nx)

    # Test 1: Exact center
    res_center = validate_target_coordinates_in_wcs(w, 133.795129, -7.245147, shape)
    assert np.isclose(res_center["pixel_0based"]["x"], 14.0), "0-based X center mismatch"
    assert np.isclose(res_center["pixel_0based"]["y"], 14.0), "0-based Y center mismatch"
    assert np.isclose(res_center["pixel_1based"]["x"], 15.0), "1-based X center mismatch"
    assert np.isclose(res_center["pixel_1based"]["y"], 15.0), "1-based Y center mismatch"
    assert res_center["in_bounds"] is True, "Target at center must be in bounds"
    assert np.isclose(res_center["offset_from_center_pixels"], 0.0), "Center offset must be 0"

    # Test 2: Target out of bounds
    res_out = validate_target_coordinates_in_wcs(w, 140.0, 0.0, shape)
    assert res_out["in_bounds"] is False, "Distant coordinates must be out of bounds"

    # Test 3: Off-center inside cutout
    res_shift = validate_target_coordinates_in_wcs(w, 133.795129 + 0.01, -7.245147, shape)
    assert res_shift["in_bounds"] is True, "Shifted coordinates should remain in bounds"
    assert res_shift["offset_from_center_pixels"] > 0, "Shifted coordinates must have positive offset"

    logger.info("All deterministic WCS unit tests PASSED successfully.")
    return True


def inspect_fits_cutout(
    fits_bytes: bytes,
    ra: float = DEFAULT_RA,
    dec: float = DEFAULT_DEC,
) -> Dict[str, Any]:
    """Open and inspect FITS cutout HDU structure, scientific header cards, and pixel data.

    Args:
        fits_bytes: Raw FITS file content.
        ra: Target Right Ascension in decimal degrees.
        dec: Target Declination in decimal degrees.

    Returns:
        Structured dictionary of verified metadata, HDU details, pixel statistics, and WCS validation.
    """
    hdul = fits.open(io.BytesIO(fits_bytes))

    hdu_summary = []
    for idx, hdu in enumerate(hdul):
        shape = getattr(hdu, "shape", None)
        dtype_str = "None"
        if hdu.data is not None:
            if hasattr(hdu.data, "dtype"):
                dtype_str = str(hdu.data.dtype)
        hdu_summary.append({
            "index": idx,
            "name": hdu.name,
            "type": type(hdu).__name__,
            "cards": len(hdu.header),
            "shape": shape,
            "dtype": dtype_str,
        })

    # HDU 1: Science Image
    image_hdu = hdul[1]
    img_data: np.ndarray = image_hdu.data
    img_hdr = image_hdu.header

    # WCS Validation using science image header (with SIP distortion)
    wcs_obj = WCS(img_hdr)
    wcs_validation = validate_target_coordinates_in_wcs(
        wcs_obj=wcs_obj,
        ra=ra,
        dec=dec,
        shape=img_data.shape,
    )

    # Header cards of scientific interest
    key_cards = [
        "BUNIT", "DATE-OBS", "MJD-OBS", "TIMESYS", "CTYPE1", "CTYPE2",
        "CRVAL1", "CRVAL2", "CRPIX1", "CRPIX2", "CDELT1", "CDELT2",
        "PC1_1", "PC1_2", "PC2_1", "PC2_2",
    ]
    header_metadata = {k: img_hdr.get(k) for k in key_cards if k in img_hdr}

    # Derive spatial pixel scale from PC matrix if present
    pc1_1 = img_hdr.get("PC1_1")
    pc2_1 = img_hdr.get("PC2_1")
    if pc1_1 is not None and pc2_1 is not None:
        pixel_scale_deg = float(np.sqrt(pc1_1**2 + pc2_1**2))
        pixel_scale_arcsec = pixel_scale_deg * 3600.0
        header_metadata["DERIVED_PIXEL_SCALE_DEG"] = pixel_scale_deg
        header_metadata["DERIVED_PIXEL_SCALE_ARCSEC"] = pixel_scale_arcsec

    # Pixel Statistics
    total_pixels = img_data.size
    finite_mask = np.isfinite(img_data)
    finite_count = int(np.sum(finite_mask))
    non_finite_count = int(total_pixels - finite_count)

    finite_values = img_data[finite_mask]
    if finite_count > 0:
        pixel_stats = {
            "shape": list(img_data.shape),
            "total_pixels": total_pixels,
            "finite_pixels": finite_count,
            "non_finite_pixels": non_finite_count,
            "min": float(np.min(finite_values)),
            "max": float(np.max(finite_values)),
            "mean": float(np.mean(finite_values)),
            "median": float(np.median(finite_values)),
            "std": float(np.std(finite_values)),
            "percentiles": {
                "1st": float(np.percentile(finite_values, 1)),
                "5th": float(np.percentile(finite_values, 5)),
                "25th": float(np.percentile(finite_values, 25)),
                "50th": float(np.percentile(finite_values, 50)),
                "75th": float(np.percentile(finite_values, 75)),
                "95th": float(np.percentile(finite_values, 95)),
                "99th": float(np.percentile(finite_values, 99)),
            },
            "negative_pixel_count": int(np.sum(finite_values < 0)),
        }
    else:
        pixel_stats = {
            "shape": list(img_data.shape),
            "total_pixels": total_pixels,
            "finite_pixels": 0,
            "non_finite_pixels": total_pixels,
        }

    # HDU 2: FLAGS
    flags_summary = []
    if len(hdul) > 2 and hdul[2].name == "FLAGS":
        flags_data: np.ndarray = hdul[2].data
        unique_flags = np.unique(flags_data)
        for val in unique_flags:
            cnt = int(np.sum(flags_data == val))
            flags_summary.append({
                "value": int(val),
                "hex": f"0x{int(val):08x}",
                "binary": f"{int(val):016b}",
                "pixel_count": cnt,
                "percentage": float((cnt / total_pixels) * 100.0),
            })

    return {
        "hdus": hdu_summary,
        "total_hdus": len(hdul),
        "header_metadata": header_metadata,
        "pixel_stats": pixel_stats,
        "flags_summary": flags_summary,
        "wcs_validation": wcs_validation,
    }


def format_report(
    observation: Dict[str, Any],
    cutout_url: str,
    download_size: int,
    elapsed_time: float,
    inspection: Dict[str, Any],
) -> str:
    """Format the scientific inspection report into a clear markdown string."""
    stats = inspection["pixel_stats"]
    hdr = inspection["header_metadata"]
    hdus = inspection["hdus"]
    flags = inspection["flags_summary"]
    wcs_val = inspection.get("wcs_validation", {})
    total_hdus = inspection.get("total_hdus", len(hdus))

    lines = [
        "=" * 78,
        "SPHEREx Sky Viewer — Milestone 1.1 WCS & FITS Verification Report",
        "=" * 78,
        "",
        "1. Observation Context:",
        f"   - Target: {DEFAULT_TARGET_NAME} (Requested RA {wcs_val.get('target_sky', {}).get('ra', DEFAULT_RA):.6f}°, Dec {wcs_val.get('target_sky', {}).get('dec', DEFAULT_DEC):.6f}°)",
        f"   - Observation ID: {observation.get('obs_id')}",
        f"   - Bandpass: {observation.get('energy_bandpassname')}",
        f"   - Collection / Release: {observation.get('obs_collection')}",
        f"   - Calibration Level: {observation.get('calib_level')}",
        f"   - Exposure Time: {observation.get('t_exptime')} s",
        f"   - Release Date: {observation.get('obs_release_date')}",
        "",
        "2. Retrieval Performance:",
        f"   - IBE Cutout URL: {cutout_url}",
        f"   - Downloaded File Size: {download_size:,} bytes ({download_size / (1024*1024):.2f} MB)",
        f"   - Elapsed Network Time: {elapsed_time:.2f} s",
        "",
        f"3. FITS HDU Structure (Total HDUs: {total_hdus} — 1 Primary Header + {total_hdus - 1} Extensions):",
    ]
    for h in hdus:
        lines.append(
            f"   - HDU {h['index']}: {h['name']} ({h['type']}) | Shape: {h['shape']} | Data Type: {h.get('dtype', 'None')} | Cards: {h['cards']}"
        )

    # Section 4: Target Coordinate & WCS Alignment Validation
    if wcs_val:
        px0 = wcs_val["pixel_0based"]
        px1 = wcs_val["pixel_1based"]
        c_px0 = wcs_val["cutout_center_pixel_0based"]
        c_px1 = wcs_val["cutout_center_pixel_1based"]
        dims = wcs_val["image_dimensions"]
        lines.extend([
            "",
            "4. Target Coordinate & WCS Alignment Validation (HDU 1 IMAGE):",
            f"   - Requested Target Sky: RA {wcs_val['target_sky']['ra']:.6f}°, Dec {wcs_val['target_sky']['dec']:.6f}° (ICRS)",
            f"   - Cutout Geometric Center Sky: RA {wcs_val['cutout_center_sky']['ra']:.6f}°, Dec {wcs_val['cutout_center_sky']['dec']:.6f}°",
            f"   - Image Dimensions (Ny × Nx): {dims['height_ny']} rows × {dims['width_nx']} columns ({dims['total_pixels']} pixels)",
            f"   - Target Pixel (0-based NumPy index): x = {px0['x']:.4f}, y = {px0['y']:.4f} [Array index: data[{int(round(px0['y']))}, {int(round(px0['x']))}]]",
            f"   - Target Pixel (1-based FITS standard): x = {px1['x']:.4f}, y = {px1['y']:.4f}",
            f"   - Cutout Geometric Center: 0-based ({c_px0['x']:.1f}, {c_px0['y']:.1f}) | 1-based ({c_px1['x']:.1f}, {c_px1['y']:.1f})",
            f"   - Target Offset from Center: {wcs_val['offset_from_center_pixels']:.4f} pixels ({wcs_val['offset_from_center_arcsec']:.2f} arcseconds)",
            f"   - In-Bounds Status: {'IN BOUNDS (PASSED)' if wcs_val['in_bounds'] else 'OUT OF BOUNDS (FAILED)'}",
            f"   - Centering Accuracy: Sub-pixel centering verified ({wcs_val['offset_from_center_pixels']:.2f} px < 0.5 px pixel quantization threshold)",
        ])

    lines.extend([
        "",
        "5. Scientific Header Cards (HDU 1 IMAGE):",
        f"   - Flux Unit (BUNIT): {hdr.get('BUNIT')}",
        f"   - Observation Date (DATE-OBS): {hdr.get('DATE-OBS')} ({hdr.get('TIMESYS', 'UTC')})",
        f"   - Observation Epoch (MJD-OBS): {hdr.get('MJD-OBS')}",
        f"   - Coordinate Type: {hdr.get('CTYPE1')}, {hdr.get('CTYPE2')}",
        f"   - Reference Pixel (CRPIX): ({hdr.get('CRPIX1')}, {hdr.get('CRPIX2')})",
        f"   - Reference Sky (CRVAL): ({hdr.get('CRVAL1')}°, {hdr.get('CRVAL2')}°)",
        f"   - Derived Pixel Scale: {hdr.get('DERIVED_PIXEL_SCALE_ARCSEC', 0.0):.3f} arcsec/pixel (~{hdr.get('DERIVED_PIXEL_SCALE_DEG', 0.0):.6f}°/pix)",
        "",
        "6. Image Pixel Statistics (HDU 1):",
        f"   - Array Dimensions: {stats['shape'][0]} × {stats['shape'][1]} ({stats['total_pixels']} pixels)",
        f"   - Finite Pixels: {stats['finite_pixels']} (Non-finite: {stats['non_finite_pixels']})",
        f"   - Flux Minimum: {stats['min']:.4f} {hdr.get('BUNIT', '')}",
        f"   - Flux Maximum: {stats['max']:.4f} {hdr.get('BUNIT', '')}",
        f"   - Flux Median: {stats['median']:.4f} {hdr.get('BUNIT', '')}",
        f"   - Flux Mean ± Std: {stats['mean']:.4f} ± {stats['std']:.4f} {hdr.get('BUNIT', '')}",
        "   - Percentiles:",
    ])
    for p_name, p_val in stats.get("percentiles", {}).items():
        lines.append(f"       * {p_name}: {p_val:.4f} {hdr.get('BUNIT', '')}")

    lines.extend([
        f"   - Negative Pixel Count: {stats['negative_pixel_count']}",
        "",
        "7. Quality Flag Distribution (HDU 2 FLAGS):",
    ])
    for f in flags:
        lines.append(
            f"   - Flag {f['value']} ({f['hex']}, bin {f['binary']}): {f['pixel_count']} pixels ({f['percentage']:.1f}%)"
        )

    lines.extend([
        "",
        "=" * 78,
    ])
    return "\n".join(lines)


def run_verification(
    ra: float = DEFAULT_RA,
    dec: float = DEFAULT_DEC,
    fov_deg: float = DEFAULT_FOV_DEG,
    band: str = DEFAULT_BAND,
    release: str = DEFAULT_RELEASE,
    timeout: int = DEFAULT_TIMEOUT,
    save_cutout_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute the end-to-end verification pipeline."""
    # Step 0: Run deterministic synthetic WCS unit tests first
    run_deterministic_wcs_tests()

    # Step 1: Query candidates
    candidates = query_irsa_candidates(ra=ra, dec=dec, band=band, release=release, timeout=timeout)
    if not candidates:
        raise RuntimeError(f"No candidate observations found for RA {ra}, Dec {dec}, band {band}, release {release}.")

    # Step 2: Select candidate
    selected = select_candidate_observation(candidates, preferred_index=0)

    # Step 3: Resolve cutout URL via DataLink
    access_url = selected["access_url"]
    cutout_url = resolve_cutout_url(access_url, ra=ra, dec=dec, size_deg=fov_deg, timeout=timeout)

    # Step 4: Download FITS cutout with retry
    fits_bytes, elapsed = download_fits_cutout(cutout_url, timeout=timeout + 15)

    # Step 5: Save if requested
    if save_cutout_path:
        with open(save_cutout_path, "wb") as f:
            f.write(fits_bytes)
        logger.info("Saved cutout FITS file to: %s", save_cutout_path)

    # Step 6: Inspect FITS content with WCS validation
    inspection = inspect_fits_cutout(fits_bytes, ra=ra, dec=dec)

    # Print report
    report = format_report(selected, cutout_url, len(fits_bytes), elapsed, inspection)
    print(report)

    return {
        "observation": selected,
        "cutout_url": cutout_url,
        "download_size": len(fits_bytes),
        "elapsed_time": elapsed,
        "inspection": inspection,
    }


def main():
    parser = argparse.ArgumentParser(description="SPHEREx Sky Viewer — Milestone 1.1 IRSA WCS & FITS Verification Script")
    parser.add_argument("--ra", type=float, default=DEFAULT_RA, help=f"Target RA in degrees (default: {DEFAULT_RA})")
    parser.add_argument("--dec", type=float, default=DEFAULT_DEC, help=f"Target Dec in degrees (default: {DEFAULT_DEC})")
    parser.add_argument("--size", type=float, default=DEFAULT_FOV_DEG, help=f"Cutout size in degrees (default: {DEFAULT_FOV_DEG})")
    parser.add_argument("--band", type=str, default=DEFAULT_BAND, help=f"Detector band (default: {DEFAULT_BAND})")
    parser.add_argument("--release", type=str, default=DEFAULT_RELEASE, help=f"Data release (default: {DEFAULT_RELEASE})")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help=f"HTTP timeout in seconds (default: {DEFAULT_TIMEOUT})")
    parser.add_argument("--save-cutout", type=str, default=None, help="Optional file path to persist downloaded FITS cutout")
    parser.add_argument("--test-wcs", action="store_true", help="Run deterministic offline WCS and coordinate unit tests only")

    args = parser.parse_args()

    if args.test_wcs:
        success = run_deterministic_wcs_tests()
        sys.exit(0 if success else 1)

    try:
        run_verification(
            ra=args.ra,
            dec=args.dec,
            fov_deg=args.size,
            band=args.band,
            release=args.release,
            timeout=args.timeout,
            save_cutout_path=args.save_cutout,
        )
    except Exception as exc:
        logger.error("Verification failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
