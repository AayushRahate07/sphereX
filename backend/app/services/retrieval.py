"""FITS Retrieval and Local Disk Caching Service.

Provides bounded, retry-safe downloading of SPHEREx Level 2 FITS cutouts
via IVOA DataLink and IRSA IBE with deterministic disk caching.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
import io
import logging
from pathlib import Path
import shutil
import time
from typing import Dict, List, Optional, Set, Tuple
from astropy.io import votable
import requests

from backend.app.config import (
    DEFAULT_FOV_DEG,
    DEFAULT_RELEASE,
    FITS_CACHE_DIR,
    SCRATCH_DIR,
)

# Shared HTTP connection pool for fast keep-alive reuse across IRSA requests
_RETRIEVAL_SESSION: Optional[requests.Session] = None

def get_retrieval_session() -> requests.Session:
    global _RETRIEVAL_SESSION
    if _RETRIEVAL_SESSION is None:
        s = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=24,
            pool_maxsize=24,
            max_retries=requests.adapters.Retry(total=2, backoff_factor=0.3, status_forcelist=[502, 503, 504]),
        )
        s.mount("https://", adapter)
        s.mount("http://", adapter)
        _RETRIEVAL_SESSION = s
    return _RETRIEVAL_SESSION
from backend.app.services.selector import SelectedObservation

logger = logging.getLogger(__name__)


class RetrievalError(RuntimeError):
    """Raised when FITS cutout retrieval fails after retries."""
    pass


def get_fits_cache_path(
    obs_id: str,
    band: str,
    size_deg: float = DEFAULT_FOV_DEG,
    release: str = DEFAULT_RELEASE,
    center_ra: Optional[float] = None,
    center_dec: Optional[float] = None,
) -> Path:
    """Compute standard deterministic local cache path for a FITS cutout."""
    if center_ra is not None and center_dec is not None:
        filename = f"spherex_{release.lower()}_{obs_id}_{band}_{center_ra:.4f}_{center_dec:.4f}_{size_deg:.4f}.fits"
    else:
        filename = f"spherex_{release.lower()}_{obs_id}_{band}_{size_deg:.4f}.fits"
    return FITS_CACHE_DIR / filename


_get_fits_cache_path = get_fits_cache_path


def get_cached_fits_path(
    obs_id: str,
    band: str,
    size_deg: float = DEFAULT_FOV_DEG,
    release: str = DEFAULT_RELEASE,
    center_ra: Optional[float] = None,
    center_dec: Optional[float] = None,
) -> Optional[Path]:
    """Return Path to local cached FITS cutout if present, valid (> 10KB), and covering target."""
    FITS_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Check coordinate-specific cache path if center coords provided
    if center_ra is not None and center_dec is not None:
        coord_cache_path = get_fits_cache_path(obs_id, band, size_deg, release, center_ra, center_dec)
        if coord_cache_path.exists() and coord_cache_path.stat().st_size > 10000:
            return coord_cache_path

    # 2. Check standard cache path
    legacy_path = get_fits_cache_path(obs_id, band, size_deg, release)
    if legacy_path.exists() and legacy_path.stat().st_size > 10000:
        # If specific center coordinates were requested, verify that the legacy cutout
        # actually covers the requested position comfortably inside the array
        if center_ra is not None and center_dec is not None:
            try:
                from astropy.io import fits
                from astropy.wcs import WCS
                with fits.open(legacy_path) as hdul:
                    img_hdr = hdul["IMAGE"].header if "IMAGE" in hdul else hdul[0].header
                    w = WCS(img_hdr)
                    pix = w.all_world2pix([[center_ra, center_dec]], 0)[0]
                    naxis1 = img_hdr.get("NAXIS1", 29)
                    naxis2 = img_hdr.get("NAXIS2", 29)
                    # Must be safely within array interior (at least 2 pixels from edge)
                    if 2 <= pix[0] <= naxis1 - 3 and 2 <= pix[1] <= naxis2 - 3:
                        return legacy_path
                    logger.debug(
                        "Legacy cutout %s does not cover (%.4f, %.4f); pix=(%.1f, %.1f)",
                        legacy_path.name, center_ra, center_dec, pix[0], pix[1]
                    )
            except Exception as exc:
                logger.warning("Could not verify WCS coverage of %s: %s", legacy_path, exc)
                return legacy_path
        else:
            return legacy_path

    # 3. Fallback to scratch directory if pre-cached from earlier verification runs
    scratch_patterns = [
        SCRATCH_DIR / f"benchmark_{obs_id}.fits",
        SCRATCH_DIR / f"{obs_id}.fits",
    ]
    for sp in scratch_patterns:
        if sp.exists() and sp.stat().st_size > 10000:
            cache_dest = get_fits_cache_path(obs_id, band, size_deg, release, center_ra, center_dec)
            try:
                shutil.copyfile(sp, cache_dest)
                logger.info("Found pre-cached FITS in scratch: %s. Copied to cache.", sp.name)
                return cache_dest
            except Exception as exc:
                logger.warning("Could not copy scratch FITS file %s: %s", sp, exc)
                return sp
    return None


def is_cutout_cached(
    obs_id: str,
    band: str,
    size_deg: float = DEFAULT_FOV_DEG,
    release: str = DEFAULT_RELEASE,
    center_ra: Optional[float] = None,
    center_dec: Optional[float] = None,
) -> bool:
    """Check whether a cutout is already available in local disk cache."""
    return get_cached_fits_path(obs_id, band, size_deg, release, center_ra, center_dec) is not None


def find_cached_obs_ids(
    obs_ids: List[str],
    band: str,
    size_deg: float = DEFAULT_FOV_DEG,
    release: str = DEFAULT_RELEASE,
    coords_per_obs: Optional[Dict[str, Tuple[float, float]]] = None,
) -> Set[str]:
    """Return the subset of observation IDs that currently exist in local cache."""
    cached: Set[str] = set()
    for obs_id in obs_ids:
        c_ra, c_dec = coords_per_obs.get(obs_id, (None, None)) if coords_per_obs else (None, None)
        if is_cutout_cached(obs_id, band, size_deg, release, c_ra, c_dec):
            cached.add(obs_id)
    return cached


def resolve_cutout_url_from_datalink(
    datalink_url: str,
    ra: float,
    dec: float,
    size_deg: float = DEFAULT_FOV_DEG,
    timeout: int = 30,
) -> str:
    """Resolve the IBE image cutout URL from the DataLink access URL."""
    try:
        resp = requests.get(datalink_url, timeout=timeout)
        if resp.status_code != 200:
            raise RetrievalError(f"DataLink query failed (HTTP {resp.status_code}): {resp.text[:200]}")

        vo = votable.parse(io.BytesIO(resp.content))
        table = vo.get_first_table()
        if not table:
            raise RetrievalError("DataLink response contained no tables.")

        table_data = table.to_table()
        science_url: Optional[str] = None
        cutout_path: Optional[str] = None

        for row in table_data:
            semantics = ""
            for sem_key in ("semantics", "col_4", "col4"):
                if sem_key in table_data.colnames:
                    semantics = str(row[sem_key]).strip()
                    break

            if semantics == "#this":
                for url_key in ("access_url", "col_1", "col1"):
                    if url_key in table_data.colnames:
                        science_url = str(row[url_key]).strip()
                        break
            elif semantics == "#cutout":
                for url_key in ("access_url", "col_12", "col12", "col_1"):
                    if url_key in table_data.colnames:
                        cutout_path = str(row[url_key]).strip()
                        break

        if science_url:
            return f"{science_url}?center={ra:.6f},{dec:.6f}d&size={size_deg}"
        elif cutout_path:
            return f"https://irsa.ipac.caltech.edu/ibe/data/{cutout_path}?center={ra:.6f},{dec:.6f}d&size={size_deg}"
        else:
            raise RetrievalError("Could not locate '#this' or '#cutout' in DataLink response.")

    except Exception as exc:
        raise RetrievalError(f"Failed to resolve DataLink URL ({datalink_url}): {exc}") from exc


def fetch_or_cache_fits_cutout(
    observation: SelectedObservation,
    ra: float,
    dec: float,
    size_deg: float = DEFAULT_FOV_DEG,
    release: str = DEFAULT_RELEASE,
    timeout: int = 35,
    max_retries: int = 3,
    center_ra: Optional[float] = None,
    center_dec: Optional[float] = None,
) -> Path:
    """Retrieve FITS cutout, utilizing local disk cache or downloading with bounded retry.

    Checks:
    1. Local FITS cache (backend/cache/fits/)
    2. Scratch directory cache from earlier verification runs
    3. Live IRSA IBE retrieval via DataLink with retry loop

    Returns:
        Path to local FITS cutout on disk.
    """
    FITS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    c_ra = center_ra if center_ra is not None else ra
    c_dec = center_dec if center_dec is not None else dec

    # 1. Local / Scratch Cache Check
    cached_path = get_cached_fits_path(observation.obs_id, observation.band, size_deg, release, center_ra=center_ra, center_dec=center_dec)
    if cached_path is not None:
        logger.info("FITS Cache Hit: %s (%d bytes)", cached_path.name, cached_path.stat().st_size)
        return cached_path

    cache_path = get_fits_cache_path(observation.obs_id, observation.band, size_deg, release, center_ra=center_ra, center_dec=center_dec)

    # 2. Live Download with Bounded Retries
    if not observation.access_url:
        raise RetrievalError(f"No access URL available to download observation {observation.obs_id}.")

    cutout_url = resolve_cutout_url_from_datalink(observation.access_url, c_ra, c_dec, size_deg, timeout=timeout)

    last_error: Optional[Exception] = None
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(
                "Downloading FITS cutout for %s (%s, attempt %d/%d)...",
                observation.obs_id, observation.band, attempt, max_retries
            )
            r = requests.get(cutout_url, timeout=timeout)
            if r.status_code == 200 and len(r.content) > 10000:
                # Atomic write via temp file
                tmp_path = cache_path.with_suffix(".tmp")
                with open(tmp_path, "wb") as f:
                    f.write(r.content)
                tmp_path.replace(cache_path)
                logger.info("FITS cutout saved: %s (%d bytes)", cache_path.name, len(r.content))
                return cache_path

            if r.status_code in (500, 502, 503, 504):
                logger.warning("Transient server status %d from IRSA IBE: %s", r.status_code, r.text[:100])
                time.sleep(1.5 * attempt)
            else:
                raise RetrievalError(f"IRSA IBE returned status {r.status_code}: {r.text[:150]}")

        except Exception as exc:
            last_error = exc
            logger.warning("Download attempt %d for %s failed: %s", attempt, observation.obs_id, exc)
            if attempt < max_retries:
                time.sleep(1.5 * attempt)

    raise RetrievalError(
        f"Failed to retrieve FITS cutout for {observation.obs_id} after {max_retries} attempts: {last_error}"
    )


def batch_retrieve_cutouts(
    observations: List[SelectedObservation],
    ra: float,
    dec: float,
    size_deg: float = DEFAULT_FOV_DEG,
    release: str = DEFAULT_RELEASE,
    max_workers: int = 6,
    coords_per_obs: Optional[Dict[str, Tuple[float, float]]] = None,
) -> Dict[str, Path]:
    """Retrieve a list of cutouts concurrently using a bounded thread pool.

    Maintains safe concurrency (max 4 workers) to respect IRSA server load limits.
    """
    results: Dict[str, Path] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_obs = {}
        for obs in observations:
            if coords_per_obs and obs.obs_id in coords_per_obs:
                c_ra, c_dec = coords_per_obs[obs.obs_id]
                future = executor.submit(
                    fetch_or_cache_fits_cutout,
                    obs,
                    ra,
                    dec,
                    size_deg,
                    release,
                    center_ra=c_ra,
                    center_dec=c_dec,
                )
            else:
                future = executor.submit(
                    fetch_or_cache_fits_cutout,
                    obs,
                    ra,
                    dec,
                    size_deg,
                    release,
                )
            future_to_obs[future] = obs

        for future in as_completed(future_to_obs):
            obs = future_to_obs[future]
            try:
                path = future.result()
                results[obs.obs_id] = path
            except Exception as exc:
                logger.error("Failed to retrieve cutout for %s: %s", obs.obs_id, exc)
                # We do not fail the entire batch if a single observation fails;
                # the caller can handle available frames or report partial results.

    return results


def retrieve_cutouts_adaptive(
    candidates: List[SelectedObservation],
    ra: float,
    dec: float,
    target_count: int,
    size_deg: float = DEFAULT_FOV_DEG,
    release: str = DEFAULT_RELEASE,
    max_download_attempts: int = 5,
    coords_per_obs: Optional[Dict[str, Tuple[float, float]]] = None,
) -> Tuple[List[SelectedObservation], Dict[str, Path]]:
    """Retrieve cutouts prioritizing cached observations and gracefully handling failures.

    Collects available cached observations first without network overhead.
    If more are needed to reach target_count, attempts downloads on uncached
    candidates up to max_download_attempts.

    Returns:
        Tuple of (chronologically sorted SelectedObservation list, dict of obs_id -> Path).
    """
    acquired_map: Dict[str, Tuple[SelectedObservation, Path]] = {}

    # 1. Collect all cached observations from candidates
    for obs in candidates:
        if len(acquired_map) >= target_count:
            break
        c_ra, c_dec = coords_per_obs.get(obs.obs_id, (None, None)) if coords_per_obs else (None, None)
        cached_path = get_cached_fits_path(obs.obs_id, obs.band, size_deg, release, center_ra=c_ra, center_dec=c_dec)
        if cached_path is not None:
            acquired_map[obs.obs_id] = (obs, cached_path)

    # 2. If shortfall remains, attempt bounded downloads of uncached candidates
    if len(acquired_map) < target_count:
        download_attempts = 0
        for obs in candidates:
            if len(acquired_map) >= target_count or download_attempts >= max_download_attempts:
                break
            if obs.obs_id in acquired_map:
                continue

            download_attempts += 1
            if coords_per_obs and obs.obs_id in coords_per_obs:
                c_ra, c_dec = coords_per_obs[obs.obs_id]
                fetch_kwargs = {"center_ra": c_ra, "center_dec": c_dec}
            else:
                fetch_kwargs = {}
            try:
                path = fetch_or_cache_fits_cutout(
                    observation=obs,
                    ra=ra,
                    dec=dec,
                    size_deg=size_deg,
                    release=release,
                    **fetch_kwargs,
                )
                acquired_map[obs.obs_id] = (obs, path)
            except Exception as exc:
                logger.warning(
                    "Adaptive retrieval download failed for %s (attempt %d/%d): %s",
                    obs.obs_id, download_attempts, max_download_attempts, exc
                )

    # 3. Sort acquired observations chronologically by MJD
    sorted_obs = sorted([obs for obs, _ in acquired_map.values()], key=lambda o: o.mjd)
    paths_dict = {obs.obs_id: path for obs, path in acquired_map.values()}

    return sorted_obs, paths_dict
