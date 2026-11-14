"""Observation Selection Service.

Queries or retrieves cached SPHEREx DR1 observations from IRSA TAP,
validates requested band and target coordinates, preserves distinct
exposures, and sorts epochs chronologically.
"""

from dataclasses import dataclass
import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import requests

from backend.app.config import (
    ABSOLUTE_MAX_FRAMES,
    DEFAULT_FOV_DEG,
    DEFAULT_MAX_FRAMES,
    DEFAULT_RELEASE,
    IRSA_TAP_URL,
    SCRATCH_DIR,
    SUPPORTED_BANDS,
    TAP_CACHE_DIR,
    TARGET_PRESETS,
)

logger = logging.getLogger(__name__)


class SelectionError(ValueError):
    """Raised when an invalid target, band, or query parameter is requested."""
    pass


class TargetNotFoundError(LookupError):
    """Raised when no observations cover the requested coordinates."""
    pass


@dataclass
class SelectedObservation:
    """Descriptor of a selected SPHEREx observation candidate."""
    obs_id: str
    band: str
    mjd: float
    exptime: float
    access_url: str
    s_ra: float
    s_dec: float
    release_date: Optional[str] = None


def get_target_name_if_preset(ra: float, dec: float, tolerance: float = 0.005) -> Optional[str]:
    """Identify if the given coordinates correspond to a known challenge preset target."""
    for preset in TARGET_PRESETS:
        if abs(ra - float(preset["ra"])) < tolerance and abs(dec - float(preset["dec"])) < tolerance:
            return str(preset["name"])
    return None


def _get_tap_cache_key(ra: float, dec: float, release: str) -> str:
    """Generate a deterministic disk cache key for a cone query."""
    coord_str = f"{ra:.5f}_{dec:.5f}_{release.lower()}"
    return hashlib.sha256(coord_str.encode("utf-8")).hexdigest()[:16]


def parse_tap_json_response(data: Any) -> List[Dict[str, Any]]:
    """Parse raw JSON returned by IRSA TAP into a validated list of row dictionaries.

    Handles:
    1. Pre-parsed list of row dictionaries (internal cache or test fixtures)
    2. Standard TAP JSON format: {"data": [...], "metadata": [{"name": ...}, ...]}
    3. IRSA VOTable JSON format: {"VOTABLE": {"RESOURCE_ARRAY": [{"TABLE": {"FIELD_ARRAY": ..., "DATA": ...}}]}}
    """
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict)]

    if not isinstance(data, dict):
        logger.warning("Unexpected TAP response type: %s; expected list or dict.", type(data))
        return []

    # Format A: Standard TAP JSON format with top-level "data" and "metadata"
    if "data" in data and "metadata" in data and isinstance(data["data"], list) and isinstance(data["metadata"], list):
        col_names = [col.get("name", f"col_{i}") if isinstance(col, dict) else f"col_{i}" for i, col in enumerate(data["metadata"])]
        records: List[Dict[str, Any]] = []
        for row in data["data"]:
            if isinstance(row, (list, tuple)):
                records.append(dict(zip(col_names, row)))
            elif isinstance(row, dict):
                records.append(row)
        return records

    # Format B: IRSA VOTable JSON format
    if "VOTABLE" in data and isinstance(data["VOTABLE"], dict):
        votable_obj = data["VOTABLE"]
        resource_array = votable_obj.get("RESOURCE_ARRAY", [])
        if not resource_array and "RESOURCE" in votable_obj:
            res_val = votable_obj["RESOURCE"]
            resource_array = res_val if isinstance(res_val, list) else [res_val]

        records = []
        for resource in resource_array:
            if not isinstance(resource, dict):
                continue
            table = resource.get("TABLE", {})
            if not isinstance(table, dict):
                continue

            field_array = table.get("FIELD_ARRAY", [])
            if not field_array and "FIELD" in table:
                f_val = table["FIELD"]
                field_array = f_val if isinstance(f_val, list) else [f_val]

            col_names = []
            for i, field in enumerate(field_array):
                if isinstance(field, dict):
                    xmlattr = field.get("<xmlattr>", {})
                    name = xmlattr.get("name") if isinstance(xmlattr, dict) else None
                    name = name or field.get("name") or f"col_{i}"
                else:
                    name = f"col_{i}"
                col_names.append(str(name))

            data_block = table.get("DATA", {})
            if isinstance(data_block, dict):
                tabledata = data_block.get("TABLEDATA", [])
                if isinstance(tabledata, list):
                    for row in tabledata:
                        if isinstance(row, (list, tuple)):
                            records.append(dict(zip(col_names, row)))
                        elif isinstance(row, dict):
                            records.append(row)
        return records

    logger.warning("Unrecognized TAP JSON structure with keys: %s", list(data.keys()))
    return []


def query_irsa_tap_for_target(
    ra: float,
    dec: float,
    release: str = DEFAULT_RELEASE,
    timeout: int = 45,
    max_retries: int = 3,
) -> List[Dict[str, Any]]:
    """Submit a cone query to IRSA TAP for spherex.obscore with caching.

    Checks:
    1. Local backend TAP cache (TAP_CACHE_DIR)
    2. Known scratch directory cache (targets_tap_cache.json)
    3. Live IRSA TAP service via ADQL with bounded retries
    """
    TAP_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_key = _get_tap_cache_key(ra, dec, release)
    cache_file = TAP_CACHE_DIR / f"tap_{cache_key}.json"

    # 1. Check local TAP cache
    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cached = json.load(f)
            records = parse_tap_json_response(cached)
            logger.info("Loaded %d TAP records from local cache for (%.5f, %.5f).", len(records), ra, dec)
            return records
        except Exception as exc:
            logger.warning("Could not read local TAP cache (%s): %s", cache_file, exc)

    # 2. Check pre-cached targets in scratch directory
    preset_name = get_target_name_if_preset(ra, dec)
    scratch_cache_file = SCRATCH_DIR / "targets_tap_cache.json"
    if preset_name and scratch_cache_file.exists():
        try:
            with open(scratch_cache_file, "r", encoding="utf-8") as f:
                scratch_data = json.load(f)
            if preset_name in scratch_data:
                records = parse_tap_json_response(scratch_data[preset_name])
                logger.info("Loaded %d TAP records from scratch cache for %s.", len(records), preset_name)
                # Save into local TAP cache
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(records, f)
                return records
        except Exception as exc:
            logger.warning("Could not read scratch TAP cache: %s", exc)

    # 3. Execute live TAP query if not cached
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
    ORDER BY t_min ASC
    """.strip()

    params = {
        "REQUEST": "doQuery",
        "LANG": "ADQL",
        "FORMAT": "json",
        "QUERY": adql_query,
    }

    last_error: Optional[Exception] = None
    import time
    for attempt in range(1, max_retries + 1):
        try:
            logger.info("Submitting live TAP query for (%.6f, %.6f), attempt %d/%d...", ra, dec, attempt, max_retries)
            resp = requests.post(IRSA_TAP_URL, data=params, timeout=timeout)
            if resp.status_code == 200:
                data = resp.json()
                records = parse_tap_json_response(data)

                # Persist parsed rows to local cache
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(records, f)
                return records

            raise RuntimeError(f"IRSA TAP returned HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as exc:
            last_error = exc
            logger.warning("TAP query attempt %d failed: %s", attempt, exc)
            if attempt < max_retries:
                time.sleep(2.0 * attempt)

    raise RuntimeError(f"Failed to query IRSA TAP after {max_retries} attempts: {last_error}")


def select_epoch_spaced_observations(
    observations: List[SelectedObservation],
    count: int,
) -> List[SelectedObservation]:
    """Deterministically select 'count' observations evenly spaced across observation epochs.

    Preserves chronological ordering, distinct observation IDs, and maximizes
    the temporal baseline across available observations.
    """
    n = len(observations)
    if n <= count:
        return observations
    if count <= 1:
        return [observations[0]]

    # Compute linearly spaced indices spanning [0, n - 1]
    selected_indices: List[int] = []
    seen = set()
    for i in range(count):
        idx = round(i * (n - 1) / (count - 1))
        if idx not in seen:
            selected_indices.append(idx)
            seen.add(idx)

    # If rounding produced fewer distinct indices, fill remaining slots
    if len(selected_indices) < count:
        for idx in range(n):
            if idx not in seen:
                selected_indices.append(idx)
                seen.add(idx)
                if len(selected_indices) == count:
                    break

    selected_indices.sort()
    return [observations[i] for i in selected_indices]


def select_observations_for_target(
    ra: float,
    dec: float,
    band: str = "SPHEREx-D1",
    release: str = DEFAULT_RELEASE,
    max_frames: Optional[int] = DEFAULT_MAX_FRAMES,
    cached_records: Optional[List[Dict[str, Any]]] = None,
    cached_obs_ids: Optional[Set[str]] = None,
    size_deg: float = DEFAULT_FOV_DEG,
    coords_per_obs: Optional[Dict[str, Tuple[float, float]]] = None,
) -> List[SelectedObservation]:
    """Select, validate, and chronologically sort observations for a target and band.

    Preserves distinct exposures; does not discard legitimate multi-epoch observations.
    Filters strictly by detector band (zero intra-band duplicates expected).
    Prioritizes locally cached observations when max_frames is bounded to ensure
    usable frames are returned immediately without network bottlenecks.
    When multiple cached observations exist across distinct epochs, spaces them
    evenly across the available temporal baseline.

    Args:
        ra: Right Ascension in decimal degrees.
        dec: Declination in decimal degrees.
        band: Detector bandpass identifier (e.g. 'SPHEREx-D1').
        release: SPHEREx data release (default: DR1).
        max_frames: Maximum number of frames to return (None for all available).
        cached_records: Optional in-memory records to bypass TAP query (useful for tests).
        cached_obs_ids: Optional set of pre-identified cached observation IDs.
        size_deg: Target field of view in degrees (used for disk cache inspection).

    Returns:
        List of SelectedObservation objects sorted strictly by observation epoch (MJD).

    Raises:
        SelectionError: For unsupported bands or invalid coordinate parameters.
        TargetNotFoundError: If no observations cover the coordinates in the chosen band.
    """
    if band not in SUPPORTED_BANDS:
        raise SelectionError(
            f"Unsupported bandpass '{band}'. Must be one of: {', '.join(SUPPORTED_BANDS)}"
        )

    if not (-90.0 <= dec <= 90.0) or not (0.0 <= ra <= 360.0):
        raise SelectionError(
            f"Coordinates out of range: RA must be in [0, 360], Dec in [-90, +90]. Got ({ra}, {dec})"
        )

    if cached_records is not None:
        records = cached_records
    else:
        records = query_irsa_tap_for_target(ra, dec, release=release)

    # Filter by band
    matching_records = [
        r for r in records
        if isinstance(r, dict) and r.get("energy_bandpassname") == band
    ]

    if not matching_records:
        raise TargetNotFoundError(
            f"No observations found covering RA={ra:.5f}, Dec={dec:.5f} in band '{band}' for release '{release}'."
        )

    # Duplicate handling:
    # Multiple distinct observations can have similar identifiers if taken in the same week,
    # but legitimate physical exposures have distinct observation IDs (e.g. 0116_1 vs 0116_2)
    # or distinct observation times. We deduplicate ONLY exact duplicate records.
    seen_keys = set()
    distinct_observations: List[SelectedObservation] = []

    for r in matching_records:
        obs_id = str(r.get("obs_id", ""))
        mjd = float(r.get("t_min", 0.0))
        exptime = float(r.get("t_exptime", 0.0))
        access_url = str(r.get("access_url", ""))
        s_ra = float(r.get("s_ra", ra))
        s_dec = float(r.get("s_dec", dec))
        release_date = r.get("obs_release_date")

        # Identity key for true duplication detection
        dedup_key = (obs_id, round(mjd, 6), access_url)
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)

        distinct_observations.append(
            SelectedObservation(
                obs_id=obs_id,
                band=band,
                mjd=mjd,
                exptime=exptime,
                access_url=access_url,
                s_ra=s_ra,
                s_dec=s_dec,
                release_date=release_date,
            )
        )

    # Sort strictly chronologically by observation epoch
    distinct_observations.sort(key=lambda obs: obs.mjd)

    # If no limit is specified, return all distinct observations up to absolute ceiling
    if max_frames is None:
        return distinct_observations[:ABSOLUTE_MAX_FRAMES]

    effective_max_frames = min(max(1, max_frames), ABSOLUTE_MAX_FRAMES)
    if len(distinct_observations) <= effective_max_frames:
        return distinct_observations

    # Cache-Aware Selection:
    # If cached observations exist for this target/band, prioritize them so
    # the endpoint returns usable frames immediately without network bottlenecks.
    if cached_obs_ids is None:
        try:
            from backend.app.services.retrieval import find_cached_obs_ids
            if coords_per_obs is None:
                from backend.app.services.astrometry import get_target_astrometry, propagate_coordinates_to_epoch
                preset_name = get_target_name_if_preset(ra, dec)
                astro = get_target_astrometry(ra, dec, name=preset_name)
                if astro is not None:
                    coords_per_obs = {
                        obs.obs_id: propagate_coordinates_to_epoch(ra, dec, obs.mjd, target_name=preset_name)
                        for obs in distinct_observations
                    }

            cached_obs_ids = find_cached_obs_ids(
                obs_ids=[obs.obs_id for obs in distinct_observations],
                band=band,
                size_deg=size_deg,
                release=release,
                coords_per_obs=coords_per_obs,
            )
        except Exception as exc:
            logger.debug("Could not inspect FITS cache during observation selection: %s", exc)
            cached_obs_ids = set()

    cached_obs = [obs for obs in distinct_observations if obs.obs_id in cached_obs_ids]
    uncached_obs = [obs for obs in distinct_observations if obs.obs_id not in cached_obs_ids]

    if len(cached_obs) >= effective_max_frames:
        # We have enough cached observations: space them across the available temporal baseline
        return select_epoch_spaced_observations(cached_obs, effective_max_frames)

    # Combine all available cached observations with the earliest uncached observations
    needed_uncached = effective_max_frames - len(cached_obs)
    selected = cached_obs + uncached_obs[:needed_uncached]
    # Maintain strict chronological ordering
    selected.sort(key=lambda obs: obs.mjd)
    return selected
