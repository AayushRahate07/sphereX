#!/usr/bin/env python3
"""SPHEREx Sky Viewer — Milestone 1.2: First-Hours Target Audit Script.

Performs systematic data availability, time coverage, and scientific feasibility
audits across the 5 canonical challenge targets defined in the build plan:
1. WISE 0855 (cold brown dwarf)
2. Barnard's Star (high proper motion M-dwarf)
3. Epsilon Indi B (nearby T-dwarf binary)
4. RW Aurigae (variable young stellar object)
5. R Draconis (M-type Mira variable)
"""

from __future__ import annotations

import argparse
import io
import json
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

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("SPHEREx-Audit")

IRSA_TAP_URL = "https://irsa.ipac.caltech.edu/TAP/sync"

TARGETS = [
    {
        "name": "WISE 0855",
        "ra": 133.795129,
        "dec": -7.245147,
        "description": "Ultra-cold brown dwarf (~250 K, high proper motion ~8.1 arcsec/yr)",
        "default_fov": 0.05,
    },
    {
        "name": "Barnard's Star",
        "ra": 269.452075,
        "dec": 4.693364,
        "description": "M-dwarf with highest known proper motion (10.3 arcsec/yr)",
        "default_fov": 0.05,
    },
    {
        "name": "Epsilon Indi B",
        "ra": 330.840200,
        "dec": -56.786500,
        "description": "Nearby brown dwarf binary (T1 + T6)",
        "default_fov": 0.05,
    },
    {
        "name": "RW Aurigae",
        "ra": 77.108200,
        "dec": 30.401400,
        "description": "Classical T Tauri variable star (dimming events)",
        "default_fov": 0.05,
    },
    {
        "name": "R Draconis",
        "ra": 247.554400,
        "dec": 66.702900,
        "description": "Mira-type long-period pulsating variable star",
        "default_fov": 0.05,
    },
]

BANDS = [
    "SPHEREx-D1",
    "SPHEREx-D2",
    "SPHEREx-D3",
    "SPHEREx-D4",
    "SPHEREx-D5",
    "SPHEREx-D6",
]


def query_target_observations(
    ra: float,
    dec: float,
    release: str = "DR1",
    timeout: int = 60,
    max_retries: int = 3,
) -> List[Dict[str, Any]]:
    """Query IRSA TAP for all SPHEREx DR1 observations covering a sky position.

    Args:
        ra: Right Ascension in decimal degrees (ICRS).
        dec: Declination in decimal degrees (ICRS).
        release: Data release identifier ('DR1').
        timeout: HTTP timeout per attempt.
        max_retries: Maximum attempts for transient network issues.

    Returns:
        List of matching observation candidate records.
    """
    collection_name = f"spherex_{release.lower()}"
    adql_query = f"""
    SELECT
        obs_id, obs_collection, energy_bandpassname,
        t_min, t_max, t_exptime,
        s_ra, s_dec, access_url, access_format,
        calib_level, obs_release_date
    FROM spherex.obscore
    WHERE obs_collection = '{collection_name}'
      AND 1 = CONTAINS(POINT('ICRS', {ra:.6f}, {dec:.6f}), s_region)
    ORDER BY energy_bandpassname ASC, t_min ASC
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
            logger.info("Submitting TAP query for (%.6f, %.6f) [attempt %d/%d]...", ra, dec, attempt, max_retries)
            resp = requests.post(IRSA_TAP_URL, data=params, timeout=timeout)
            if resp.status_code == 200:
                import csv
                reader = csv.DictReader(io.StringIO(resp.text))
                candidates = list(reader)
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
                return candidates

            logger.warning("TAP returned HTTP %d: %s", resp.status_code, resp.text[:150])
            last_error = RuntimeError(f"HTTP {resp.status_code}: {resp.text[:150]}")
            time.sleep(2.0 * attempt)
        except Exception as exc:
            last_error = exc
            logger.warning("TAP attempt %d failed: %s", attempt, exc)
            time.sleep(2.0 * attempt)

    raise RuntimeError(f"Failed TAP query for ({ra}, {dec}) after {max_retries} attempts: {last_error}")


def analyze_target_data(target: Dict[str, Any], candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute per-band statistics, duplicate identification, and temporal baseline."""
    band_analysis: Dict[str, Any] = {}

    for b in BANDS:
        records = [r for r in candidates if r.get("energy_bandpassname") == b]
        raw_count = len(records)
        unique_obs_ids = {r["obs_id"] for r in records}
        unique_count = len(unique_obs_ids)

        # Check duplicate rows sharing obs_id within the same band
        duplicate_obs_ids = []
        obs_id_counts: Dict[str, int] = {}
        for r in records:
            oid = r["obs_id"]
            obs_id_counts[oid] = obs_id_counts.get(oid, 0) + 1
        for oid, count in obs_id_counts.items():
            if count > 1:
                duplicate_obs_ids.append({"obs_id": oid, "count": count})

        if records:
            t_mins = [r["t_min"] for r in records if "t_min" in r]
            t_maxs = [r["t_max"] for r in records if "t_max" in r]
            min_mjd = min(t_mins) if t_mins else None
            max_mjd = max(t_mins) if t_mins else None
            baseline_days = (max_mjd - min_mjd) if (min_mjd and max_mjd) else 0.0

            # Convert MJD to calendar dates
            # Formula: MJD = JD - 2400000.5. Unix epoch 1970-01-01 is MJD 40587.0
            from datetime import datetime, timezone
            min_date = datetime.fromtimestamp((min_mjd - 40587.0) * 86400, tz=timezone.utc).strftime("%Y-%m-%d") if min_mjd else "N/A"
            max_date = datetime.fromtimestamp((max_mjd - 40587.0) * 86400, tz=timezone.utc).strftime("%Y-%m-%d") if max_mjd else "N/A"
        else:
            min_mjd = None
            max_mjd = None
            baseline_days = 0.0
            min_date = "N/A"
            max_date = "N/A"

        band_analysis[b] = {
            "raw_record_count": raw_count,
            "unique_obs_id_count": unique_count,
            "duplicate_records": duplicate_obs_ids,
            "min_mjd": min_mjd,
            "max_mjd": max_mjd,
            "baseline_days": baseline_days,
            "start_date_utc": min_date,
            "end_date_utc": max_date,
            "usable_for_inspection": unique_count > 0,
        }

    return {
        "target": target,
        "total_records": len(candidates),
        "total_unique_obs_ids": len({r["obs_id"] for r in candidates}),
        "bands": band_analysis,
    }


def resolve_and_download_cutout(
    access_url: str,
    ra: float,
    dec: float,
    size_deg: float = 0.05,
    timeout: int = 45,
    max_retries: int = 3,
) -> Tuple[Optional[bytes], float, Optional[str]]:
    """Retrieve DataLink, resolve IBE cutout URL, and download FITS cutout."""
    # Step 1: DataLink resolution
    for dl_attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(access_url, timeout=timeout)
            if resp.status_code == 200:
                vo = votable.parse(io.BytesIO(resp.content))
                table_data = vo.get_first_table().to_table()
                science_url = None
                cutout_path = None
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
                    raise RuntimeError("No #this or #cutout found in DataLink")
                break
            time.sleep(2.0 * dl_attempt)
        except Exception as e:
            if dl_attempt == max_retries:
                return None, 0.0, None
            time.sleep(2.0 * dl_attempt)

    # Step 2: Cutout download with retry
    for attempt in range(1, max_retries + 1):
        t0 = time.time()
        try:
            r = requests.get(cutout_url, timeout=timeout)
            elapsed = time.time() - t0
            if r.status_code == 200 and r.content.startswith(b"SIMPLE  ="):
                return r.content, elapsed, cutout_url
            if r.status_code in [500, 502, 503, 504]:
                time.sleep(2.0 * attempt)
            else:
                return None, elapsed, cutout_url
        except Exception:
            time.sleep(2.0 * attempt)

    return None, 0.0, cutout_url


def analyze_wise0855_epochs(
    candidates: List[Dict[str, Any]],
    target_ra: float,
    target_dec: float,
    size_deg: float = 0.05,
) -> Dict[str, Any]:
    """Examine multi-epoch observations for WISE 0855 in D6 and D1 to evaluate motion."""
    logger.info("Beginning multi-epoch scientific investigation for WISE 0855...")

    results: Dict[str, Any] = {"D6": [], "D1": []}

    for band in ["SPHEREx-D6", "SPHEREx-D1"]:
        band_key = "D6" if "D6" in band else "D1"
        band_records = [r for r in candidates if r.get("energy_bandpassname") == band]
        if not band_records:
            continue

        # Sort chronologically by t_min
        band_records.sort(key=lambda x: x["t_min"])

        # Pick earliest epoch, middle epoch, and latest epoch
        selected_indices = [0]
        if len(band_records) > 2:
            selected_indices.append(len(band_records) // 2)
        if len(band_records) > 1:
            selected_indices.append(len(band_records) - 1)

        # Ensure unique indices
        selected_indices = sorted(list(set(selected_indices)))

        for idx in selected_indices:
            rec = band_records[idx]
            obs_id = rec["obs_id"]
            mjd = rec["t_min"]
            access_url = rec["access_url"]

            logger.info("Downloading cutout for %s epoch %d (obs_id: %s, MJD: %.4f)...", band, idx, obs_id, mjd)
            fits_bytes, elapsed, cutout_url = resolve_and_download_cutout(access_url, target_ra, target_dec, size_deg)

            if not fits_bytes:
                logger.warning("Failed to retrieve cutout for %s obs_id %s", band, obs_id)
                continue

            hdul = fits.open(io.BytesIO(fits_bytes))
            img_hdr = hdul[1].header
            img_data = hdul[1].data
            wcs_obj = WCS(img_hdr)

            # Target position in pixels
            px0_raw, py0_raw = wcs_obj.all_world2pix(target_ra, target_dec, 0)
            px0 = float(px0_raw)
            py0 = float(py0_raw)
            ix = int(round(px0))
            iy = int(round(py0))

            Ny, Nx = img_data.shape
            in_bounds = (0 <= ix < Nx) and (0 <= iy < Ny)

            # Extract local flux at target position (aperture sum in 3x3 box)
            if in_bounds:
                y_min, y_max = max(0, iy - 1), min(Ny, iy + 2)
                x_min, x_max = max(0, ix - 1), min(Nx, ix + 2)
                aperture_box = img_data[y_min:y_max, x_min:x_max]
                aperture_flux_sum = float(np.nansum(aperture_box))
                peak_pixel_flux = float(img_data[iy, ix])
            else:
                aperture_flux_sum = None
                peak_pixel_flux = None

            # Background statistics
            finite_vals = img_data[np.isfinite(img_data)]
            bg_median = float(np.median(finite_vals)) if len(finite_vals) > 0 else 0.0
            bg_std = float(np.std(finite_vals)) if len(finite_vals) > 0 else 0.0

            results[band_key].append({
                "obs_id": obs_id,
                "mjd": mjd,
                "date_obs": img_hdr.get("DATE-OBS"),
                "pixel_0based": (px0, py0),
                "pixel_index_round": (ix, iy),
                "in_bounds": in_bounds,
                "target_pixel_flux": peak_pixel_flux,
                "aperture_3x3_flux_sum": aperture_flux_sum,
                "background_median": bg_median,
                "background_std": bg_std,
                "cutout_url": cutout_url,
                "download_size": len(fits_bytes),
                "elapsed_time": elapsed,
            })

    return results


def run_full_target_audit(cache_dir: Optional[str] = None) -> Dict[str, Any]:
    """Execute target queries, analysis, and WISE 0855 multi-epoch inspection."""
    audit_results = []
    wise0855_candidates = []

    logger.info("Starting Milestone 1.2 First-Hours Target Audit...")

    import os
    candidate_cache_file = os.path.join(cache_dir, "targets_tap_cache.json") if cache_dir else None
    cached_data = {}
    if candidate_cache_file and os.path.exists(candidate_cache_file):
        try:
            with open(candidate_cache_file, "r") as f:
                cached_data = json.load(f)
            logger.info("Loaded cached TAP candidate data for %d targets.", len(cached_data))
        except Exception as e:
            logger.warning("Could not read candidate cache: %s", e)

    candidates_to_cache = dict(cached_data)

    for target in TARGETS:
        name = target["name"]
        ra = target["ra"]
        dec = target["dec"]
        logger.info("Auditing target: %s (RA %.6f, Dec %.6f)...", name, ra, dec)

        if name in candidates_to_cache:
            candidates = candidates_to_cache[name]
            logger.info("Target %s: using %d cached candidate records.", name, len(candidates))
        else:
            candidates = query_target_observations(ra, dec)
            logger.info("Target %s: returned %d candidate records from TAP.", name, len(candidates))
            candidates_to_cache[name] = candidates
            if candidate_cache_file:
                try:
                    with open(candidate_cache_file, "w") as f:
                        json.dump(candidates_to_cache, f)
                except Exception:
                    pass

        analysis = analyze_target_data(target, candidates)
        audit_results.append(analysis)

        if name == "WISE 0855":
            wise0855_candidates = candidates

    # Perform multi-epoch investigation on WISE 0855
    wise0855_epoch_data = analyze_wise0855_epochs(
        candidates=wise0855_candidates,
        target_ra=TARGETS[0]["ra"],
        target_dec=TARGETS[0]["dec"],
        size_deg=TARGETS[0]["default_fov"],
    )

    return {
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "targets_audit": audit_results,
        "wise0855_epochs": wise0855_epoch_data,
    }


def main():
    parser = argparse.ArgumentParser(description="SPHEREx Sky Viewer — Milestone 1.2 Target Audit")
    parser.add_argument("--output-json", type=str, default=None, help="Optional JSON output path for raw audit results")
    parser.add_argument("--cache-dir", type=str, default=None, help="Optional directory to cache candidate queries")
    args = parser.parse_args()

    results = run_full_target_audit(cache_dir=args.cache_dir)

    if args.output_json:
        with open(args.output_json, "w") as f:
            json.dump(results, f, indent=2)
        logger.info("Saved raw audit JSON to: %s", args.output_json)

    # Print markdown summary table
    print("\n" + "=" * 80)
    print("SPHEREx Sky Viewer — Milestone 1.2 Target Observation Availability Summary")
    print("=" * 80)
    for item in results["targets_audit"]:
        t = item["target"]
        print(f"\nTarget: {t['name']} | Canonical: RA {t['ra']:.6f}°, Dec {t['dec']:.6f}°")
        print(f"Description: {t['description']}")
        print(f"Total Records: {item['total_records']} | Unique Obs IDs: {item['total_unique_obs_ids']}")
        print(f"{'Band':<12} | {'Records':<8} | {'Unique IDs':<11} | {'Time Coverage (MJD)':<26} | {'Dates (UTC)':<24} | {'Baseline'}")
        print("-" * 100)
        for band_name, bdata in item["bands"].items():
            if bdata["raw_record_count"] > 0:
                mjd_str = f"{bdata['min_mjd']:.2f} - {bdata['max_mjd']:.2f}"
                date_str = f"{bdata['start_date_utc']} - {bdata['end_date_utc']}"
                baseline_str = f"{bdata['baseline_days']:.1f} days"
            else:
                mjd_str = "None"
                date_str = "None"
                baseline_str = "0 days"
            print(
                f"{band_name:<12} | {bdata['raw_record_count']:<8} | {bdata['unique_obs_id_count']:<11} | "
                f"{mjd_str:<26} | {date_str:<24} | {baseline_str}"
            )

    print("\n" + "=" * 80)
    print("WISE 0855 Multi-Epoch Cutout Analysis Summary")
    print("=" * 80)
    for band_key, epochs in results["wise0855_epochs"].items():
        print(f"\n--- Band {band_key} Multi-Epoch Inspections ({len(epochs)} epochs retrieved) ---")
        for ep in epochs:
            print(
                f"Obs ID: {ep['obs_id']} | MJD: {ep['mjd']:.4f} ({ep['date_obs']}) | "
                f"Target Pixel: ({ep['pixel_0based'][0]:.2f}, {ep['pixel_0based'][1]:.2f}) | "
                f"Target Flux: {ep['target_pixel_flux']:.4f} MJy/sr | "
                f"3x3 Box Flux: {ep['aperture_3x3_flux_sum']:.4f} MJy/sr | "
                f"Background: {ep['background_median']:.4f} ± {ep['background_std']:.4f} MJy/sr"
            )


if __name__ == "__main__":
    main()
