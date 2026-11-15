"""
SPHEREx Sky Viewer — Member 3 FITS Loader & Astropy WCS Engine
==============================================================
Provides high-fidelity astronomical FITS I/O, World Coordinate System (WCS)
sub-image extraction with `astropy.nddata.Cutout2D`, coordinate parsing
(decimal and sexagesimal via `astropy.coordinates.SkyCoord`), and synthetic
survey FITS generation for testing and offline execution.

Standards & Conventions:
------------------------
- FITS Extension Format: Multi-Extension FITS (MEF)
    * Official NASA/IPAC IRSA Level 2 Cutouts:
        - HDU 0: PRIMARY (telescope, pointing, and observation metadata)
        - HDU 1: 'IMAGE' (calibrated surface brightness image, MJy/sr, with WCS)
        - HDU 2: 'FLAGS' (32-bit quality flag bitmask, int32)
        - HDU 3: 'VARIANCE' (variance in (MJy/sr)^2, float32)
    * Legacy / Mock Survey FITS:
        - HDU 0: PRIMARY (telescope & observation metadata)
        - HDU 1: 'SCI' (calibrated surface brightness image, MJy/sr, with WCS)
        - HDU 2: 'UNCERT' (1-sigma error per pixel, MJy/sr)
        - HDU 3: 'MASK' (quality flag bitmask, int32)
- Coordinate System: ICRS / J2000
- Projection: Gnomonic / Tangential ('RA---TAN', 'DEC--TAN')
- Plate Scale: 6.2 arcsec/pixel (0.00172222 deg/pixel)
- Citation Requirement: NASA/IPAC Infrared Science Archive (IRSA)
"""

from __future__ import annotations
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
from astropy.coordinates import SkyCoord
import astropy.units as u
from astropy.nddata import Cutout2D

try:
    from data_models import (
        SPHERExFrame,
        QualityFlag,
        SPHEREX_DETECTOR_BANDS,
        NOMINAL_PIXEL_SCALE_ARCSEC,
        normalize_quality_flags,
    )
except ImportError:
    from analysis.data_models import (
        SPHERExFrame,
        QualityFlag,
        SPHEREX_DETECTOR_BANDS,
        NOMINAL_PIXEL_SCALE_ARCSEC,
        normalize_quality_flags,
    )


# Solid angle of a SPHEREx pixel in steradians (6.2 arcsec on a side)
OMEGA_PIX_SR: float = (NOMINAL_PIXEL_SCALE_ARCSEC * np.pi / (180.0 * 3600.0)) ** 2


# -----------------------------------------------------------------------------
# 1. Celestial Coordinate Parsing
# -----------------------------------------------------------------------------
def parse_coordinates(
    ra_input: Union[str, float],
    dec_input: Optional[Union[str, float]] = None,
) -> Tuple[float, float, str]:
    """
    Parse arbitrary user input coordinates into Right Ascension and Declination
    in decimal degrees (J2000 / ICRS).

    Supports:
    1. Named challenge target presets: 'WISE_0855', 'BARNARD_STAR', 'EPSILON_INDI_B', etc.
    2. Single combined string: "133.790 -7.240", "133.790, -7.240", "08:55:09.6 -07:14:24"
    3. Separate strings or floats: ra="08h55m09.6s", dec="-07d14m24s" or ra=133.79, dec=-7.24

    Returns:
    --------
    Tuple[float, float, str] : (ra_deg, dec_deg, resolved_name)
    """
    # Check if input is a known challenge target preset
    preset_key = str(ra_input).strip().upper().replace(" ", "_").replace("'", "")
    try:
        try:
            from target_validation import TARGET_DATABASE
        except ImportError:
            from analysis.target_validation import TARGET_DATABASE
        if preset_key in TARGET_DATABASE:
            prof = TARGET_DATABASE[preset_key]
            return prof.ra_deg, prof.dec_deg, prof.common_name
    except Exception:
        challenge_presets = {
            "WISE_0855": (133.790, -7.240, "WISE J085510.83-071442.5"),
            "BARNARD_STAR": (269.452, 4.693, "Barnard's Star (GJ 699)"),
            "EPSILON_INDI_B": (330.840, -56.786, "Epsilon Indi Ba,Bb"),
            "RW_AUR": (77.108, 30.402, "RW Aurigae A"),
            "R_DRA": (248.370, 66.702, "R Draconis"),
        }
        if preset_key in challenge_presets:
            ra_p, dec_p, name_p = challenge_presets[preset_key]
            return ra_p, dec_p, name_p

    # Handle float inputs directly
    if isinstance(ra_input, (int, float)) and dec_input is not None and isinstance(dec_input, (int, float)):
        ra_val = float(ra_input) % 360.0
        dec_val = float(dec_input)
        if not (-90.0 <= dec_val <= 90.0):
            raise ValueError(f"Declination must be between -90 and +90 deg, got {dec_val}")
        return ra_val, dec_val, f"Target_RA{ra_val:.3f}_Dec{dec_val:+.3f}"

    ra_str = str(ra_input).strip()
    dec_str = str(dec_input).strip() if dec_input is not None else None

    # Handle combined string like "133.790 -7.240" or "133.790, -7.240"
    if dec_str is None or dec_str == "":
        cleaned = ra_str.replace(",", " ")
        parts = cleaned.split()
        if len(parts) == 2:
            ra_str, dec_str = parts[0], parts[1]
        elif len(parts) >= 6:
            # e.g. "08 55 09.6 -07 14 24"
            ra_str = " ".join(parts[:3])
            dec_str = " ".join(parts[3:])
        else:
            raise ValueError(
                f"Could not parse coordinate input '{ra_input}'. "
                "Expected either a target preset name, 'RA Dec' pair, or separate RA and Dec arguments."
            )

    # Try numeric decimal degree parsing first
    try:
        ra_val = float(ra_str) % 360.0
        dec_val = float(dec_str)
        if not (-90.0 <= dec_val <= 90.0):
            raise ValueError(f"Declination out of bounds [-90, +90]: {dec_val}")
        return ra_val, dec_val, f"Target_RA{ra_val:.3f}_Dec{dec_val:+.3f}"
    except ValueError:
        pass  # Proceed to SkyCoord parsing

    # Try Astropy SkyCoord parsing (supports sexagesimal, hours/degrees, colons)
    coord = None
    parse_errors = []

    # Attempt 1: hours / degrees
    try:
        coord = SkyCoord(ra_str, dec_str, unit=(u.hourangle, u.deg), frame="icrs")
    except Exception as e:
        parse_errors.append(str(e))

    # Attempt 2: degrees / degrees
    if coord is None:
        try:
            coord = SkyCoord(ra_str, dec_str, unit=(u.deg, u.deg), frame="icrs")
        except Exception as e:
            parse_errors.append(str(e))

    # Attempt 3: combined string representation
    if coord is None:
        try:
            coord = SkyCoord(f"{ra_str} {dec_str}", frame="icrs")
        except Exception as e:
            parse_errors.append(str(e))

    if coord is None:
        raise ValueError(
            f"Failed to parse celestial coordinates '{ra_str}', '{dec_str}'. Errors:\n"
            + "\n".join(parse_errors)
        )

    ra_deg = float(coord.ra.deg)
    dec_deg = float(coord.dec.deg)
    return ra_deg, dec_deg, f"Target_RA{ra_deg:.3f}_Dec{dec_deg:+.3f}"


# -----------------------------------------------------------------------------
# 2. Astropy WCS Builder
# -----------------------------------------------------------------------------
def build_spherex_wcs(
    ra_center_deg: float,
    dec_center_deg: float,
    crpix1: float,
    crpix2: float,
    pixel_scale_arcsec: float = NOMINAL_PIXEL_SCALE_ARCSEC,
) -> WCS:
    """
    Construct a standardized Astropy WCS object for SPHEREx observations.

    Parameters:
    -----------
    ra_center_deg : float
        Right Ascension at the reference pixel (J2000 degrees).
    dec_center_deg : float
        Declination at the reference pixel (J2000 degrees).
    crpix1, crpix2 : float
        Reference pixel coordinates (1-indexed FITS standard).
    pixel_scale_arcsec : float
        Detector pixel scale in arcseconds (nominal 6.2).
    """
    w = WCS(naxis=2)
    deg_per_pix = pixel_scale_arcsec / 3600.0

    w.wcs.crpix = [crpix1, crpix2]
    # In standard astronomical projections, RA increases to the left (East is -X)
    w.wcs.cdelt = [-deg_per_pix, deg_per_pix]
    w.wcs.crval = [ra_center_deg, dec_center_deg]
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    w.wcs.cunit = ["deg", "deg"]
    return w


# -----------------------------------------------------------------------------
# 3. SPHEREx FITS Writer (Multi-Extension Level-2 Format)
# -----------------------------------------------------------------------------
def create_mock_spherex_fits(
    filepath: Union[str, Path],
    target_ra_deg: float,
    target_dec_deg: float,
    detector_id: int,
    wavelength_um: float,
    flux_ujy: float,
    image_size: int = 64,
    target_name: str = "Target",
    mjd: float = 60300.0,
    exposure_time_s: float = 120.0,
    background_level_mjy_sr: float = 1.5,
    noise_sigma_mjy_sr: float = 0.15,
    is_saturated: bool = False,
    pixel_offset: Tuple[float, float] = (0.0, 0.0),
    random_seed: Optional[int] = None,
) -> Path:
    """
    Create an authentic multi-extension SPHEREx Level-2 FITS file with:
    - PrimaryHDU: metadata, telemetry, and IPAC/IRSA attribution.
    - ImageHDU ('SCI'): Calibrated surface brightness (MJy/sr) with tangential WCS.
    - ImageHDU ('UNCERT'): 1-sigma error per pixel (MJy/sr).
    - ImageHDU ('MASK'): Quality bitmask (int32).

    Parameters:
    -----------
    filepath : str or Path
        Target output file path.
    target_ra_deg, target_dec_deg : float
        Coordinates of the astronomical target in J2000 degrees.
    detector_id : int
        SPHEREx detector array (1 to 6).
    wavelength_um : float
        Observation wavelength in microns.
    flux_ujy : float
        Target source flux density in microJanskys (uJy).
    image_size : int, default 64
        Width and height of simulated detector region in pixels.
    is_saturated : bool, default False
        Whether the source should exceed detector saturation threshold (> 50 MJy/sr).
    pixel_offset : tuple of (dx, dy)
        Sub-pixel offset from the center to simulate natural pointing or dither.
    """
    rng = np.random.default_rng(random_seed)
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    # Reference pixel at frame center (1-based FITS coordinates)
    crpix1 = (image_size + 1.0) / 2.0
    crpix2 = (image_size + 1.0) / 2.0

    # Build WCS centered on target_ra, target_dec
    wcs = build_spherex_wcs(target_ra_deg, target_dec_deg, crpix1, crpix2)

    # Source position in 0-based pixel index
    # crpix - 1 + offset
    src_x = (image_size - 1.0) / 2.0 + pixel_offset[0]
    src_y = (image_size - 1.0) / 2.0 + pixel_offset[1]

    # Convert total source flux uJy to MJy/sr pixel sum:
    # 1 uJy = 1e-12 W/m^2/Hz = 1e-29 erg/s/cm^2/Hz = 1e-6 Jy
    # 1 MJy/sr = 1e6 Jy / sr
    # Total MJy = flux_ujy * 1e-6 / 1e6 = flux_ujy * 1e-12
    # Total pixel sum in MJy/sr = (flux_ujy * 1e-12) / OMEGA_PIX_SR
    total_pixel_sum_mjy_sr = (flux_ujy * 1e-12) / OMEGA_PIX_SR

    # 2D Gaussian PSF with FWHM ~ 1.0 pixel (sigma ~ 0.42466 pixel)
    psf_sigma = 1.0 / (2.0 * np.sqrt(2.0 * np.log(2.0)))
    y_coords, x_coords = np.mgrid[0:image_size, 0:image_size]
    r_sq = (x_coords - src_x) ** 2 + (y_coords - src_y) ** 2
    raw_profile = np.exp(-0.5 * r_sq / (psf_sigma ** 2))

    # Normalize discrete profile to match integrated pixel sum exactly
    source_flux_map = (raw_profile / np.sum(raw_profile)) * total_pixel_sum_mjy_sr

    if is_saturated:
        # Force peak to exceed linear limit of 50 MJy/sr
        source_flux_map = np.clip(source_flux_map, 0, None)
        source_flux_map[int(round(src_y)), int(round(src_x))] = 75.0

    # Inject realistic background field stars (r > 7 pix to avoid contaminating central aperture/annulus)
    field_star_offsets = [
        (-7.8, +8.2, 0.40),   # Top-left field star
        (+8.5, -7.5, 0.28),   # Bottom-right field star
        (+7.4, +8.6, 0.20),   # Top-right field star
        (-9.0, -7.0, 0.16),   # Bottom-left field star
    ]
    for dx_fs, dy_fs, frac in field_star_offsets:
        fs_x = src_x + dx_fs
        fs_y = src_y + dy_fs
        if 0 <= fs_x < image_size and 0 <= fs_y < image_size:
            r_fs_sq = (x_coords - fs_x) ** 2 + (y_coords - fs_y) ** 2
            p_fs = np.exp(-0.5 * r_fs_sq / (psf_sigma ** 2))
            fs_flux = (p_fs / np.sum(p_fs)) * (total_pixel_sum_mjy_sr * frac)
            source_flux_map += fs_flux

    # Background and Gaussian noise
    bg_noise = rng.normal(loc=0.0, scale=noise_sigma_mjy_sr, size=(image_size, image_size))
    sci_data = background_level_mjy_sr + source_flux_map + bg_noise

    # Uncertainty array (background noise + Poisson shot noise in quadrature)
    # Gain ~ 1.5 e-/ADU, exposure 120s
    shot_noise = np.sqrt(np.maximum(source_flux_map, 0.0) * 0.01)
    uncert_data = np.sqrt(noise_sigma_mjy_sr ** 2 + shot_noise ** 2)

    # Quality bitmask
    mask_data = np.zeros((image_size, image_size), dtype=np.int32)
    if is_saturated:
        peak_y, peak_x = int(round(src_y)), int(round(src_x))
        mask_data[peak_y, peak_x] |= int(QualityFlag.SATURATED)

    # Randomly inject occasional bad pixel
    if rng.random() < 0.1:
        bad_y, bad_x = rng.integers(0, image_size, size=2)
        if abs(bad_y - src_y) > 4 or abs(bad_x - src_x) > 4:
            mask_data[bad_y, bad_x] |= int(QualityFlag.BAD_PIXEL)
            sci_data[bad_y, bad_x] = 0.0

    # Build FITS Structure
    # HDU 0: Primary
    primary_hdr = fits.Header()
    primary_hdr["TELESCOP"] = ("SPHEREx", "Spectro-Photometer for History of the Universe")
    primary_hdr["INSTRUME"] = ("SPHEREx", "Linear Variable Filter Spectrograph")
    primary_hdr["ORIGIN"] = ("NASA/IPAC IRSA", "Infrared Science Archive Data Distribution")
    primary_hdr["OBJECT"] = (target_name, "Target identifier")
    primary_hdr["DETECTOR"] = (int(detector_id), f"SPHEREx Detector Array (1-6)")
    primary_hdr["BAND"] = (f"Band_{detector_id}", "SPHEREx Spectral Band")
    primary_hdr["WAVELEN"] = (float(wavelength_um), "Central wavelength in micrometers")
    wave_min, wave_max = SPHEREX_DETECTOR_BANDS[detector_id]
    primary_hdr["WAVE_MIN"] = (float(wave_min), "Band minimum wavelength in um")
    primary_hdr["WAVE_MAX"] = (float(wave_max), "Band maximum wavelength in um")
    primary_hdr["MJD_OBS"] = (float(mjd), "Observation epoch in Modified Julian Date")
    primary_hdr["EXPTIME"] = (float(exposure_time_s), "Total exposure time in seconds")
    primary_hdr["BUNIT"] = ("MJy/sr", "Calibrated surface brightness physical unit")
    primary_hdr["DATA_REL"] = ("DR1", "SPHEREx Public Data Release")
    primary_hdr["CIT_REQ"] = ("NASA/IPAC IRSA", "Mandatory citation for SPHEREx archival data")
    primary_hdu = fits.PrimaryHDU(header=primary_hdr)

    # HDU 1: Science Image with WCS
    sci_hdr = wcs.to_header()
    sci_hdr["EXTNAME"] = ("SCI", "Calibrated Science Image")
    sci_hdr["BUNIT"] = ("MJy/sr", "Surface brightness")
    sci_hdu = fits.ImageHDU(data=sci_data.astype(np.float32), header=sci_hdr, name="SCI")

    # HDU 2: Uncertainty Image
    uncert_hdr = fits.Header()
    uncert_hdr["EXTNAME"] = ("UNCERT", "1-sigma Uncertainty Image")
    uncert_hdr["BUNIT"] = ("MJy/sr", "Uncertainty in surface brightness")
    uncert_hdu = fits.ImageHDU(data=uncert_data.astype(np.float32), header=uncert_hdr, name="UNCERT")

    # HDU 3: Quality Bitmask
    mask_hdr = fits.Header()
    mask_hdr["EXTNAME"] = ("MASK", "Data Quality Bitmask")
    mask_hdr["BUNIT"] = ("bitmask", "Integer bit flags")
    mask_hdu = fits.ImageHDU(data=mask_data.astype(np.int32), header=mask_hdr, name="MASK")

    # Write out MEF
    hdul = fits.HDUList([primary_hdu, sci_hdu, uncert_hdu, mask_hdu])
    hdul.writeto(str(filepath), overwrite=True)
    return filepath


# -----------------------------------------------------------------------------
# 4. Cutout Extraction from FITS via Astropy WCS
# -----------------------------------------------------------------------------
def load_cutout_from_fits(
    fits_path: Union[str, Path],
    target_ra_deg: float,
    target_dec_deg: float,
    cutout_size: int = 25,
) -> SPHERExFrame:
    """
    Open a SPHEREx Level-2 FITS file (official NASA/IPAC IRSA format or legacy mock),
    convert target sky coordinates (RA, Dec) to pixel coordinates via WCS, extract
    a 2D cutout across IMAGE/SCI, FLAGS/MASK, and VARIANCE/UNCERT extensions,
    correctly convert variance to 1-sigma uncertainty, and return a validated SPHERExFrame.

    Parameters:
    -----------
    fits_path : str or Path
        Path to the SPHEREx FITS file.
    target_ra_deg, target_dec_deg : float
        Target coordinates in J2000 degrees.
    cutout_size : int, default 25
        Square cutout dimension in pixels.

    Returns:
    --------
    SPHERExFrame : Validated cutout frame ready for Member 3 photometry and spectrum analysis.
    """
    fits_path = Path(fits_path)
    if not fits_path.exists():
        raise FileNotFoundError(f"FITS file not found: {fits_path}")

    with fits.open(str(fits_path), memmap=False) as hdul:
        primary_hdr = hdul[0].header if len(hdul) > 0 else fits.Header()

        # 1. Locate Science Image HDU: Prefer official 'IMAGE', then 'SCI'
        sci_hdu = None
        if "IMAGE" in hdul and getattr(hdul["IMAGE"], "data", None) is not None:
            sci_hdu = hdul["IMAGE"]
        elif "SCI" in hdul and getattr(hdul["SCI"], "data", None) is not None:
            sci_hdu = hdul["SCI"]
        elif len(hdul) > 1 and getattr(hdul[1], "data", None) is not None:
            h1_name = str(hdul[1].name).upper()
            if h1_name not in ("FLAGS", "MASK", "VARIANCE", "UNCERT", "ZODI", "EPSF", "WCS-WAVE"):
                sci_hdu = hdul[1]

        if sci_hdu is None or sci_hdu.data is None or sci_hdu.data.ndim != 2:
            raise ValueError(
                f"Could not find a valid 2D science image HDU ('IMAGE' or 'SCI') in {fits_path.name}"
            )

        sci_hdr = sci_hdu.header
        wcs = WCS(sci_hdr)

        # 2. Locate Quality Flags / Mask HDU: Prefer official 'FLAGS', then 'MASK'
        flags_hdu = None
        if "FLAGS" in hdul and getattr(hdul["FLAGS"], "data", None) is not None:
            flags_hdu = hdul["FLAGS"]
        elif "MASK" in hdul and getattr(hdul["MASK"], "data", None) is not None:
            flags_hdu = hdul["MASK"]
        elif len(hdul) > 2 and getattr(hdul[2], "data", None) is not None:
            h2_name = str(hdul[2].name).upper()
            if h2_name == "FLAGS":
                flags_hdu = hdul[2]
            elif h2_name not in ("UNCERT", "VARIANCE", "ERROR", "SIGMA") and len(hdul) > 3 and str(hdul[3].name).upper() in ("MASK", "FLAGS"):
                flags_hdu = hdul[3]
            elif h2_name not in ("UNCERT", "VARIANCE", "ERROR", "SIGMA") and np.issubdtype(hdul[2].data.dtype, np.integer):
                flags_hdu = hdul[2]

        # 3. Locate Variance / Uncertainty HDU: Prefer official 'VARIANCE', then 'UNCERT'
        var_uncert_hdu = None
        is_variance = False

        if "VARIANCE" in hdul and getattr(hdul["VARIANCE"], "data", None) is not None:
            var_uncert_hdu = hdul["VARIANCE"]
            is_variance = True
        elif "UNCERT" in hdul and getattr(hdul["UNCERT"], "data", None) is not None:
            var_uncert_hdu = hdul["UNCERT"]
            is_variance = False
        elif "ERROR" in hdul and getattr(hdul["ERROR"], "data", None) is not None:
            var_uncert_hdu = hdul["ERROR"]
            is_variance = False
        elif "SIGMA" in hdul and getattr(hdul["SIGMA"], "data", None) is not None:
            var_uncert_hdu = hdul["SIGMA"]
            is_variance = False
        else:
            if sci_hdu.name.upper() == "IMAGE" and len(hdul) > 3 and getattr(hdul[3], "data", None) is not None:
                h3_name = str(hdul[3].name).upper()
                if h3_name not in ("FLAGS", "MASK"):
                    var_uncert_hdu = hdul[3]
                    is_variance = True
            elif sci_hdu.name.upper() == "SCI" and len(hdul) > 2 and getattr(hdul[2], "data", None) is not None:
                h2_name = str(hdul[2].name).upper()
                if h2_name not in ("FLAGS", "MASK"):
                    var_uncert_hdu = hdul[2]
                    is_variance = False

        # Convert celestial coordinates to pixel space
        target_coord = SkyCoord(ra=target_ra_deg * u.deg, dec=target_dec_deg * u.deg, frame="icrs")
        x_pix, y_pix = wcs.world_to_pixel(target_coord)

        x_pix = float(x_pix)
        y_pix = float(y_pix)

        # Check if target falls within extended detector bounds
        ny, nx = sci_hdu.data.shape
        if not (-cutout_size <= x_pix < nx + cutout_size and -cutout_size <= y_pix < ny + cutout_size):
            raise ValueError(
                f"Target ({target_ra_deg:.4f}, {target_dec_deg:.4f}) at pixel ({x_pix:.1f}, {y_pix:.1f}) "
                f"falls outside detector bounds [{nx} x {ny}] for file {fits_path.name}"
            )

        # Extract 2D Cutout for SCI / IMAGE
        sci_cutout = Cutout2D(
            sci_hdu.data,
            (x_pix, y_pix),
            (cutout_size, cutout_size),
            wcs=wcs,
            mode="partial",
            fill_value=np.nan,
        )
        sci_data = sci_cutout.data.astype(np.float64)

        # Extract matching Cutout for MASK / FLAGS
        if flags_hdu is not None:
            mask_cutout = Cutout2D(
                flags_hdu.data,
                (x_pix, y_pix),
                (cutout_size, cutout_size),
                mode="partial",
                fill_value=0,
            )
            raw_flags = mask_cutout.data.astype(np.int32)
            is_mission = (
                flags_hdu.name.upper() == "FLAGS"
                or sci_hdu.name.upper() == "IMAGE"
                or np.any(raw_flags > 127)
            )
            mask_data = normalize_quality_flags(raw_flags, is_mission_flags=is_mission)
        else:
            raw_flags = None
            mask_data = np.zeros((cutout_size, cutout_size), dtype=np.int32)

        # Out-of-bounds partial cutout pixel detection
        cut_yslice, cut_xslice = sci_cutout.slices_cutout
        inside_mask = np.zeros((cutout_size, cutout_size), dtype=bool)
        inside_mask[cut_yslice, cut_xslice] = True
        oob_mask = ~inside_mask
        if np.any(oob_mask):
            mask_data[oob_mask] |= int(QualityFlag.EDGE_ARTIFACT | QualityFlag.BAD_PIXEL)
            sci_data[oob_mask] = np.nan

        # Identify non-finite science flux and flag as bad pixels
        non_finite_flux = ~np.isfinite(sci_data)
        if np.any(non_finite_flux):
            mask_data[non_finite_flux] |= int(QualityFlag.BAD_PIXEL)
            sci_data[non_finite_flux] = np.nan

        # Extract matching Cutout for UNCERT / VARIANCE
        if var_uncert_hdu is not None:
            var_cutout = Cutout2D(
                var_uncert_hdu.data,
                (x_pix, y_pix),
                (cutout_size, cutout_size),
                mode="partial",
                fill_value=np.nan,
            )
            raw_var_uncert = var_cutout.data.astype(np.float64)

            if is_variance:
                # VARIANCE contains sigma^2 in (MJy/sr)^2: convert to 1-sigma uncertainty sigma
                valid_var = np.isfinite(raw_var_uncert) & (raw_var_uncert >= 0.0)
                uncert_data = np.full_like(raw_var_uncert, np.nan, dtype=np.float64)
                uncert_data[valid_var] = np.sqrt(raw_var_uncert[valid_var])
                mask_data[~valid_var] |= int(QualityFlag.BAD_PIXEL)
            else:
                # Already 1-sigma uncertainty
                valid_uncert = np.isfinite(raw_var_uncert) & (raw_var_uncert >= 0.0)
                uncert_data = np.full_like(raw_var_uncert, np.nan, dtype=np.float64)
                uncert_data[valid_uncert] = raw_var_uncert[valid_uncert]
                mask_data[~valid_uncert] |= int(QualityFlag.BAD_PIXEL)
        else:
            uncert_data = np.full((cutout_size, cutout_size), np.nan, dtype=np.float64)
            mask_data |= int(QualityFlag.CALIBRATION_WARN)

        # Extract detector ID: check header cards, parse strings if necessary
        detector_id = None
        raw_det = primary_hdr.get("DETECTOR", sci_hdr.get("DETECTOR", None))
        if raw_det is not None:
            if isinstance(raw_det, (int, np.integer)):
                detector_id = int(raw_det)
            else:
                m = re.search(r"(\d+)", str(raw_det))
                if m:
                    detector_id = int(m.group(1))

        if detector_id is None or detector_id not in SPHEREX_DETECTOR_BANDS:
            # Fallback: check filename for detector pattern (e.g. SPHEREx-D6)
            m_fn = re.search(r"SPHEREx-D(\d)", fits_path.name, re.IGNORECASE)
            if m_fn:
                detector_id = int(m_fn.group(1))
            else:
                detector_id = 1

        # Extract central wavelength in micrometers and record provenance
        wavelength_um = None
        wavelength_source = "NOMINAL_BANDPASS_MIDPOINT"

        raw_wave = primary_hdr.get(
            "WAVELEN", sci_hdr.get("WAVELEN", sci_hdr.get("CWAVE", primary_hdr.get("CWAVE", None)))
        )
        if raw_wave is not None:
            try:
                val = float(raw_wave)
                if val > 0:
                    wavelength_um = val
                    wavelength_source = "FITS_HEADER"
            except (ValueError, TypeError):
                wavelength_um = None

        if wavelength_um is None and "EPSF" in hdul and getattr(hdul["EPSF"], "data", None) is not None:
            epsf_data = hdul["EPSF"].data
            if hasattr(epsf_data, "names") and "CWAVE" in epsf_data.names:
                try:
                    val = float(epsf_data["CWAVE"][0])
                    if val > 0:
                        wavelength_um = val
                        wavelength_source = "EPSF_TABLE"
                except (IndexError, ValueError, TypeError):
                    wavelength_um = None

        # Verify wavelength is within physical bandpass of detector; if not, use band midpoint
        det_min, det_max = SPHEREX_DETECTOR_BANDS[detector_id]
        if wavelength_um is None or not ((det_min - 0.10) <= wavelength_um <= (det_max + 0.10)):
            wavelength_um = (det_min + det_max) / 2.0
            wavelength_source = "NOMINAL_BANDPASS_MIDPOINT"
            mask_data |= int(QualityFlag.CALIBRATION_WARN)

        # Read observation epoch, timing, and units
        raw_mjd = primary_hdr.get(
            "MJD_OBS",
            sci_hdr.get("MJD-OBS", sci_hdr.get("MJD_OBS", primary_hdr.get("MJD-OBS", 60300.0))),
        )
        try:
            mjd = float(raw_mjd)
        except (ValueError, TypeError):
            mjd = 60300.0

        raw_exp = primary_hdr.get("EXPTIME", sci_hdr.get("EXPTIME", 120.0))
        try:
            exposure_time_s = float(raw_exp)
        except (ValueError, TypeError):
            exposure_time_s = 120.0

        target_name = str(primary_hdr.get("OBJECT", sci_hdr.get("OBJECT", "Unknown_Target")))
        data_release = str(primary_hdr.get("DATA_REL", sci_hdr.get("DATA_REL", "DR1")))
        flux_unit = str(primary_hdr.get("BUNIT", sci_hdr.get("BUNIT", "MJy/sr"))).strip()

        # Calculate approximate wavelength resolution and FWHM:
        res_power = {1: 41.0, 2: 41.0, 3: 41.0, 4: 35.0, 5: 110.0, 6: 130.0}.get(detector_id, 41.0)
        wavelength_fwhm_um = wavelength_um / res_power

        frame_flags = int(QualityFlag.GOOD)
        if wavelength_source == "NOMINAL_BANDPASS_MIDPOINT" or var_uncert_hdu is None:
            frame_flags |= int(QualityFlag.CALIBRATION_WARN)

        # Formulate standardized SPHERExFrame with normalized mask and raw_flags
        frame = SPHERExFrame(
            data=sci_data,
            uncertainty=uncert_data,
            mask=mask_data,
            frame_id=f"SPHEREX_{fits_path.stem}",
            mjd=mjd,
            timestamp_utc=f"MJD_{mjd:.3f}",
            detector_id=detector_id,
            band_name=f"Band {detector_id}",
            wavelength_um=wavelength_um,
            wavelength_fwhm_um=wavelength_fwhm_um,
            ra_deg=target_ra_deg,
            dec_deg=target_dec_deg,
            pixel_scale_arcsec=NOMINAL_PIXEL_SCALE_ARCSEC,
            flux_unit=flux_unit,
            exposure_time_s=exposure_time_s,
            data_release=data_release,
            frame_quality_flags=frame_flags,
            additional_metadata={
                "fits_source": str(fits_path),
                "target_name": target_name,
                "center_pixel_x": float(sci_cutout.center_cutout[0]),
                "center_pixel_y": float(sci_cutout.center_cutout[1]),
                "original_detector_pixel": (x_pix, y_pix),
                "wcs": sci_cutout.wcs,
                "has_variance_hdu": is_variance,
                "sci_hdu_name": sci_hdu.name,
                "flags_hdu_name": flags_hdu.name if flags_hdu is not None else None,
                "uncert_hdu_name": var_uncert_hdu.name if var_uncert_hdu is not None else None,
                "wavelength_source": wavelength_source,
                "is_wavelength_measured": (wavelength_source != "NOMINAL_BANDPASS_MIDPOINT"),
                "raw_flags": raw_flags,
            },
            raw_flags=raw_flags,
        )
        return frame

# -----------------------------------------------------------------------------
# 5. FITS Cutout Inspection & Diagnostic Plotting
# -----------------------------------------------------------------------------
def plot_fits_inspection(
    frame: SPHERExFrame,
    output_path: Union[str, Path],
    aperture_radius_pix: float = 2.5,
    annulus_inner_pix: float = 4.0,
    annulus_outer_pix: float = 6.0,
    title: Optional[str] = None,
) -> Path:
    """
    Generate an astronomical multi-panel diagnostic plot of a SPHEREx FITS cutout:
    - Panel 1: Science Surface Brightness (SCI, MJy/sr) with aperture & sky annulus contours.
    - Panel 2: 1-sigma Uncertainty Map (UNCERT, MJy/sr).
    - Panel 3: Quality Bitmask (MASK) with color key for flagged pixels.

    Parameters:
    -----------
    frame : SPHERExFrame
        Cutout frame with data, uncertainty, and mask.
    output_path : str or Path
        Output image path (PNG format recommended).
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(1, 3, figsize=(15, 5), facecolor="#0e1117")

    fig_title = title or (
        f"SPHEREx FITS Inspection — {frame.additional_metadata.get('target_name', 'Target')} "
        f"(Det {frame.detector_id}, {frame.wavelength_um:.3f} um)"
    )
    fig.suptitle(fig_title, fontsize=13, fontweight="bold", color="white", y=0.98)

    cx = frame.additional_metadata.get("center_pixel_x", (frame.shape[1] - 1.0) / 2.0)
    cy = frame.additional_metadata.get("center_pixel_y", (frame.shape[0] - 1.0) / 2.0)

    # 1. SCI Panel
    im0 = axes[0].imshow(frame.data, origin="lower", cmap="inferno")
    axes[0].set_title("SCI: Surface Brightness (MJy/sr)", color="#50e3c2", fontsize=11)
    axes[0].set_facecolor("#0e1117")
    axes[0].tick_params(colors="white")

    # Add green aperture contour
    aper_circle = Circle((cx, cy), aperture_radius_pix, color="#00ff66", fill=False, lw=1.8, ls="--", label=f"Aperture (r={aperture_radius_pix}p)")
    axes[0].add_patch(aper_circle)

    # Add orange sky annulus contours
    ann_in = Circle((cx, cy), annulus_inner_pix, color="#ff9900", fill=False, lw=1.3, ls=":", label=f"Annulus ({annulus_inner_pix}-{annulus_outer_pix}p)")
    ann_out = Circle((cx, cy), annulus_outer_pix, color="#ff9900", fill=False, lw=1.3, ls=":")
    axes[0].add_patch(ann_in)
    axes[0].add_patch(ann_out)

    axes[0].plot(cx, cy, "+", color="#00ff66", markersize=8, markeredgewidth=1.5)
    axes[0].legend(loc="upper right", fontsize=8, facecolor="#1e222d", edgecolor="none", labelcolor="white")
    cb0 = fig.colorbar(im0, ax=axes[0], orientation="horizontal", pad=0.15, aspect=25)
    cb0.ax.xaxis.set_tick_params(color="white")
    plt.setp(plt.getp(cb0.ax.axes, "xticklabels"), color="white")

    # 2. UNCERT Panel
    im1 = axes[1].imshow(frame.uncertainty, origin="lower", cmap="magma")
    axes[1].set_title("UNCERT: 1-sigma Noise (MJy/sr)", color="#f5a623", fontsize=11)
    axes[1].set_facecolor("#0e1117")
    axes[1].tick_params(colors="white")
    cb1 = fig.colorbar(im1, ax=axes[1], orientation="horizontal", pad=0.15, aspect=25)
    cb1.ax.xaxis.set_tick_params(color="white")
    plt.setp(plt.getp(cb1.ax.axes, "xticklabels"), color="white")

    # 3. MASK Panel
    im2 = axes[2].imshow(frame.mask, origin="lower", cmap="Blues", vmin=0, vmax=max(4, int(np.max(frame.mask))))
    axes[2].set_title("MASK: Data Quality Bitmask", color="#b8e986", fontsize=11)
    axes[2].set_facecolor("#0e1117")
    axes[2].tick_params(colors="white")

    # Summarize flagged pixels
    n_sat = np.sum((frame.mask & int(QualityFlag.SATURATED)) > 0)
    n_bad = np.sum((frame.mask & int(QualityFlag.BAD_PIXEL)) > 0)
    n_cr = np.sum((frame.mask & int(QualityFlag.COSMIC_RAY)) > 0)
    n_edge = np.sum((frame.mask & int(QualityFlag.EDGE_ARTIFACT)) > 0)
    n_sources = np.sum((frame.raw_flags & (1 << 21)) > 0) if frame.raw_flags is not None else 0
    extra_src = f"\n- Catalog Sources: {n_sources}" if n_sources > 0 else ""
    extra_edge = f"\n- Edge Artifacts: {n_edge}" if n_edge > 0 else ""
    flag_summary = (
        f"Flags:\n- Good: {frame.mask.size - n_sat - n_bad - n_cr - n_edge}\n"
        f"- Saturated: {n_sat}\n- Bad Pixels: {n_bad}\n- Cosmic Rays: {n_cr}{extra_edge}{extra_src}"
    )
    axes[2].text(
        0.05, 0.95, flag_summary,
        transform=axes[2].transAxes,
        fontsize=8,
        verticalalignment="top",
        color="white",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#1e222d", alpha=0.8, edgecolor="none")
    )

    cb2 = fig.colorbar(im2, ax=axes[2], orientation="horizontal", pad=0.15, aspect=25)
    cb2.ax.xaxis.set_tick_params(color="white")
    plt.setp(plt.getp(cb2.ax.axes, "xticklabels"), color="white")

    plt.savefig(str(output_path), dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return output_path


# -----------------------------------------------------------------------------
# 6. Automated Survey Generator for User Target Coordinates
# -----------------------------------------------------------------------------
def generate_spherex_survey_for_target(
    target_ra_deg: float,
    target_dec_deg: float,
    target_name: str,
    output_dir: Union[str, Path],
    mode: str = "all",
    selected_bands: Optional[List[int]] = None,
    n_stack_frames: int = 5,
    period_days: Optional[float] = None,
) -> Dict[str, List[Path]]:
    """
    Synthesize authentic SPHEREx multi-detector and multi-epoch survey FITS files
    centered around user-provided celestial coordinates.

    Supports:
    - User-selected detector bands (1..6)
    - Custom variability period (days) for physical phase modeling
    - Custom number of dithered exposures for frame stacking

    Returns:
    --------
    Dict[str, List[Path]] : Mapping of mode categories to created FITS file paths.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    created_files: Dict[str, List[Path]] = {
        "spectrum": [],
        "lightcurve": [],
        "stack": [],
    }

    # Central wavelengths for the 6 SPHEREx detectors
    band_wavelengths = {
        1: 0.930,   # Band 1: Near-IR
        2: 1.375,   # Band 2: Near-IR
        3: 2.030,   # Band 3: Near-IR
        4: 3.120,   # Band 4: Mid-IR
        5: 4.120,   # Band 5: Mid-IR
        6: 4.710,   # Band 6: Mid-IR
    }

    # Default to all 6 bands if not specified
    if selected_bands is None:
        selected_bands = [1, 2, 3, 4, 5, 6]

    # Estimate astrophysical flux profile based on preset or default
    preset_key = target_name.upper().replace(" ", "_").replace("'", "")
    if preset_key == "WISE_0855":
        fluxes = {1: 0.1, 2: 0.2, 3: 0.8, 4: 15.0, 5: 180.0, 6: 420.0}
    elif preset_key == "BARNARD_STAR":
        fluxes = {1: 1850.0, 2: 2600.0, 3: 2100.0, 4: 950.0, 5: 580.0, 6: 420.0}
    elif preset_key == "EPSILON_INDI_B":
        fluxes = {1: 8.0, 2: 45.0, 3: 25.0, 4: 60.0, 5: 350.0, 6: 280.0}
    elif preset_key == "RW_AUR":
        fluxes = {1: 1200.0, 2: 1550.0, 3: 1850.0, 4: 2100.0, 5: 1950.0, 6: 1800.0}
    elif preset_key == "R_DRA":
        fluxes = {1: 4500.0, 2: 12000.0, 3: 25000.0, 4: 18000.0, 5: 9500.0, 6: 6200.0}
    else:
        # Generic stellar blackbody / infrared source
        fluxes = {1: 500.0, 2: 750.0, 3: 900.0, 4: 700.0, 5: 550.0, 6: 400.0}

    # 1. Spectral Set (Detectors in selected_bands)
    if mode in ["all", "spectrum"]:
        spec_dir = output_dir / "spectrum"
        spec_dir.mkdir(exist_ok=True)
        for det_id in selected_bands:
            if det_id in band_wavelengths:
                w_um = band_wavelengths[det_id]
                flx = fluxes.get(det_id, 500.0)
                fpath = spec_dir / f"spherex_det{det_id}_w{w_um:.3f}um.fits"
                create_mock_spherex_fits(
                    filepath=fpath,
                    target_ra_deg=target_ra_deg,
                    target_dec_deg=target_dec_deg,
                    detector_id=det_id,
                    wavelength_um=w_um,
                    flux_ujy=flx,
                    image_size=64,
                    target_name=target_name,
                    mjd=60300.0,
                    random_seed=100 + det_id,
                )
                created_files["spectrum"].append(fpath)

    # 2. Time-Series Light Curve Set (8-10 epochs in Band 3 or Band 5)
    if mode in ["all", "lightcurve"]:
        lc_dir = output_dir / "lightcurve"
        lc_dir.mkdir(exist_ok=True)
        det_id = 3 if 3 in selected_bands else (selected_bands[0] if selected_bands else 3)
        w_um = band_wavelengths.get(det_id, 2.030)
        base_flux = fluxes.get(det_id, 1000.0)

        n_epochs = 10
        period = float(period_days) if period_days is not None and period_days > 0 else 180.0
        dt = (1.5 * period) / n_epochs

        for epoch_idx in range(n_epochs):
            mjd = 60300.0 + epoch_idx * dt
            # Physical phase-modulated variability
            phase = (mjd - 60300.0) / period
            variation_factor = 1.0 + 0.38 * np.sin(2 * np.pi * phase)
            epoch_flux = base_flux * variation_factor

            # If R_DRA preset, test physical saturation at maximum
            is_sat = (preset_key == "R_DRA" and (epoch_idx % n_epochs) in [2, 3])

            fpath = lc_dir / f"spherex_epoch{epoch_idx+1}_mjd{mjd:.1f}.fits"
            create_mock_spherex_fits(
                filepath=fpath,
                target_ra_deg=target_ra_deg,
                target_dec_deg=target_dec_deg,
                detector_id=det_id,
                wavelength_um=w_um,
                flux_ujy=epoch_flux,
                image_size=64,
                target_name=target_name,
                mjd=mjd,
                is_saturated=is_sat,
                random_seed=200 + epoch_idx,
            )
            created_files["lightcurve"].append(fpath)

    # 3. Multi-Exposure Stacking Coaddition Set (n_stack_frames in Band 2)
    if mode in ["all", "stack"]:
        stack_dir = output_dir / "stack"
        stack_dir.mkdir(exist_ok=True)
        det_id = 2 if 2 in selected_bands else (selected_bands[0] if selected_bands else 2)
        w_um = band_wavelengths.get(det_id, 1.375)
        faint_flux = 320.0  # Faint source for clear SNR enhancement

        # Generate dither offsets in pixels
        rng = np.random.default_rng(42)
        dithers = [(0.0, 0.0)]
        for _ in range(n_stack_frames - 1):
            dx = rng.uniform(-0.45, 0.45)
            dy = rng.uniform(-0.45, 0.45)
            dithers.append((dx, dy))

        for exp_idx, (dx, dy) in enumerate(dithers):
            fpath = stack_dir / f"spherex_stack_exp{exp_idx+1}.fits"
            create_mock_spherex_fits(
                filepath=fpath,
                target_ra_deg=target_ra_deg,
                target_dec_deg=target_dec_deg,
                detector_id=det_id,
                wavelength_um=w_um,
                flux_ujy=faint_flux,
                image_size=64,
                target_name=target_name,
                mjd=60350.0 + exp_idx * 0.01,
                noise_sigma_mjy_sr=0.03,
                pixel_offset=(dx, dy),
                random_seed=300 + exp_idx,
            )
            created_files["stack"].append(fpath)

    return created_files

