"""Frames Endpoint for SPHEREx Sky Viewer.

Serves multi-epoch SPHEREx Level 2 infrared observations reprojected onto
a fixed, target-centered common sky grid matching the frontend contract.
"""

import logging
import time
from typing import Dict, List, Optional, Tuple
from fastapi import APIRouter, HTTPException, Query, status

from backend.app.config import (
    ABSOLUTE_MAX_FRAMES,
    DEFAULT_BAND,
    DEFAULT_FOV_DEG,
    DEFAULT_MAX_FRAMES,
    DEFAULT_PLATE_SCALE_DEG,
    DEFAULT_RELEASE,
    SUPPORTED_BANDS,
)
from backend.app.models.spherex import (
    CatalogMarker,
    SpherexApiResponse,
    SpherexBand,
    SpherexFrame,
    TargetInfo,
    WcsInfo,
)
from backend.app.processing.fits_parser import InvalidFitsStructureError, parse_fits_cutout
from backend.app.processing.reprojection import (
    create_fixed_common_wcs,
    reproject_observation_to_grid,
)
from backend.app.services.astrometry import (
    get_target_astrometry,
    propagate_coordinates_to_epoch,
)
from backend.app.services.retrieval import RetrievalError, batch_retrieve_cutouts
from backend.app.services.selector import (
    SelectionError,
    TargetNotFoundError,
    get_target_name_if_preset,
    select_observations_for_target,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["frames"])

# In-memory response cache for sub-millisecond repeated queries
_RESPONSE_CACHE: Dict[str, SpherexApiResponse] = {}


def clear_frames_cache() -> None:
    """Clear in-memory response cache."""
    _RESPONSE_CACHE.clear()


@router.get(
    "/frames",
    response_model=SpherexApiResponse,
    summary="Retrieve multi-epoch SPHEREx observations aligned on a common sky grid",
    description=(
        "Queries IRSA DR1 observations for the specified sky coordinates and band, "
        "downloads and caches Level 2 FITS cutouts, normalizes quality flags, and "
        "reprojects all epochs onto a standardized, fixed target-centered celestial tangent plane."
    ),
)
def get_frames(
    ra: float = Query(..., description="Target Right Ascension in decimal degrees [0, 360]", ge=0.0, le=360.0),
    dec: float = Query(..., description="Target Declination in decimal degrees [-90, +90]", ge=-90.0, le=90.0),
    size: float = Query(DEFAULT_FOV_DEG, description="Field of view in degrees [0.01, 0.5]", ge=0.01, le=0.5),
    band: str = Query(DEFAULT_BAND, description="SPHEREx detector bandpass identifier"),
    release: str = Query(DEFAULT_RELEASE, description="SPHEREx data release version"),
    max_frames: int = Query(DEFAULT_MAX_FRAMES, description="Maximum number of frames to return", ge=1, le=ABSOLUTE_MAX_FRAMES),
) -> SpherexApiResponse:
    """Execute the vertical slice pipeline: Selection -> Retrieval -> Reprojection -> API Delivery."""
    t_endpoint_start = time.perf_counter()
    # 1. Parameter Validation
    if band not in SUPPORTED_BANDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported bandpass '{band}'. Must be one of: {', '.join(SUPPORTED_BANDS)}",
        )

    preset_name = get_target_name_if_preset(ra, dec)
    cache_key = f"{preset_name or f'{ra:.5f}_{dec:.5f}'}_{size:.4f}_{band}_{release}_{max_frames}"
    if cache_key in _RESPONSE_CACHE:
        logger.info("Serving frames from in-memory response cache for %s", cache_key)
        return _RESPONSE_CACHE[cache_key]

    astro = get_target_astrometry(ra, dec, name=preset_name)

    # 2. Observation Selection
    t_sel_start = time.perf_counter()
    try:
        selected_obs = select_observations_for_target(
            ra=ra,
            dec=dec,
            band=band,
            release=release,
            max_frames=max_frames,
            size_deg=size,
        )
    except SelectionError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)) from err
    except TargetNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err
    except Exception as err:
        logger.error("Unexpected error during observation selection: %s", err)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to query IRSA observation archive: {err}",
        ) from err

    sel_dur_ms = (time.perf_counter() - t_sel_start) * 1000
    logger.info(
        "[TIMING] Observation selection for %s (%s, FOV=%.2f): found %d frames in %.2fms",
        preset_name or f"({ra:.4f}, {dec:.4f})", band, size, len(selected_obs), sel_dur_ms
    )

    # Compute epoch-propagated coordinates per observation
    t_coord_start = time.perf_counter()
    coords_per_obs: Dict[str, Tuple[float, float]] = {}
    for obs in selected_obs:
        if astro is not None:
            c_ra, c_dec = propagate_coordinates_to_epoch(ra, dec, obs.mjd, target_name=preset_name)
        else:
            c_ra, c_dec = ra, dec
        coords_per_obs[obs.obs_id] = (c_ra, c_dec)

    # 3. Construct Fixed Common Sky Grid
    # For targets with proper motion, anchor the fixed sky grid to the object's position at
    # the first observation epoch. This ensures the target is well-framed at the center (crpix),
    # while the shared WCS grid remains identical across all epochs, preserving true physical motion.
    if astro is not None and selected_obs:
        first_obs = min(selected_obs, key=lambda o: o.mjd)
        grid_anchor_ra, grid_anchor_dec = coords_per_obs[first_obs.obs_id]
    else:
        grid_anchor_ra, grid_anchor_dec = ra, dec

    common_wcs, out_width, out_height = create_fixed_common_wcs(
        target_ra=grid_anchor_ra,
        target_dec=grid_anchor_dec,
        fov_deg=size,
        plate_scale_deg=DEFAULT_PLATE_SCALE_DEG,
    )
    coord_dur_ms = (time.perf_counter() - t_coord_start) * 1000
    logger.debug("[TIMING] Fixed common WCS (%dx%d) and coordinate propagation completed in %.2fms", out_width, out_height, coord_dur_ms)

    wcs_model = WcsInfo(
        crval=(grid_anchor_ra, grid_anchor_dec),
        crpix=((out_width + 1) / 2.0, (out_height + 1) / 2.0),
        cdelt=(-DEFAULT_PLATE_SCALE_DEG, DEFAULT_PLATE_SCALE_DEG),
        ctype=("RA---TAN", "DEC--TAN"),
    )

    # 4. Bounded FITS Retrieval & Local Caching
    try:
        retrieved_paths = batch_retrieve_cutouts(
            observations=selected_obs,
            ra=ra,
            dec=dec,
            size_deg=size,
            release=release,
            max_workers=4,
            coords_per_obs=coords_per_obs,
        )
    except Exception as err:
        logger.error("Fatal error during cutout batch retrieval: %s", err)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to retrieve cutouts from IRSA IBE: {err}",
        ) from err

    # If fewer than 2 frames were retrieved, attempt a small, bounded fallback
    # across at most 2 remaining candidates to achieve a minimal multi-epoch blink sequence.
    # We do NOT run fallback if >= 2 frames are already available, avoiding 30s timeouts.
    min_required_for_blink = min(2, max_frames)
    if len(retrieved_paths) < min_required_for_blink:
        try:
            all_candidates = select_observations_for_target(
                ra=ra,
                dec=dec,
                band=band,
                release=release,
                max_frames=None,
                size_deg=size,
            )
            already_attempted = {obs.obs_id for obs in selected_obs}
            remaining_candidates = [c for c in all_candidates if c.obs_id not in already_attempted]
            shortfall = min_required_for_blink - len(retrieved_paths)
            if remaining_candidates and shortfall > 0:
                candidates_to_try = remaining_candidates[:min(2, shortfall)]
                logger.info(
                    "Attempting bounded fallback retrieval for %d shortfall frames from %d remaining candidates...",
                    len(candidates_to_try), len(remaining_candidates)
                )
                for cand in candidates_to_try:
                    if cand.obs_id not in coords_per_obs:
                        if astro is not None:
                            coords_per_obs[cand.obs_id] = propagate_coordinates_to_epoch(ra, dec, cand.mjd, target_name=preset_name)
                        else:
                            coords_per_obs[cand.obs_id] = (ra, dec)

                extra_retrieved = batch_retrieve_cutouts(
                    observations=candidates_to_try,
                    ra=ra,
                    dec=dec,
                    size_deg=size,
                    release=release,
                    max_workers=2,
                    coords_per_obs=coords_per_obs,
                )
                retrieved_paths.update(extra_retrieved)
                for cand in candidates_to_try:
                    if cand.obs_id in extra_retrieved and cand not in selected_obs:
                        selected_obs.append(cand)
        except Exception as exc:
            logger.warning("Adaptive fallback candidate retrieval encountered an error: %s", exc)

    if not retrieved_paths:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to retrieve any candidate FITS cutouts from the archive.",
        )

    # 5. Process & Reproject Each Available Observation
    frames: List[SpherexFrame] = []
    # Sort selected observations chronologically before processing
    selected_obs.sort(key=lambda o: o.mjd)

    for obs in selected_obs:
        if obs.obs_id not in retrieved_paths:
            logger.warning("Observation %s was not retrieved; skipping.", obs.obs_id)
            continue

        fits_path = retrieved_paths[obs.obs_id]
        try:
            t_parse_start = time.perf_counter()
            parsed = parse_fits_cutout(
                source=fits_path,
                band=band,
                fallback_obs_id=obs.obs_id,
                fallback_mjd=obs.mjd,
            )
            parse_dur_ms = (time.perf_counter() - t_parse_start) * 1000

            t_reproj_start = time.perf_counter()
            reprojected = reproject_observation_to_grid(
                observation=parsed,
                target_ra=grid_anchor_ra,
                target_dec=grid_anchor_dec,
                common_wcs=common_wcs,
                out_width=out_width,
                out_height=out_height,
                interpolation_order=1,
            )
            reproj_dur_ms = (time.perf_counter() - t_reproj_start) * 1000

            file_size = fits_path.stat().st_size if fits_path.exists() else 0
            logger.info(
                "[TIMING] Frame %s parsed (%d bytes) in %.2fms, reprojected (%dx%d) in %.2fms",
                obs.obs_id, file_size, parse_dur_ms, out_width, out_height, reproj_dur_ms
            )

            # Format 1D arrays matching frontend contract
            flux_flat = [round(float(v), 5) for v in reprojected.flux.flatten()]
            flags_flat = [int(v) for v in reprojected.flags.flatten()]

            frames.append(
                SpherexFrame(
                    index=len(frames),
                    mjd=round(parsed.mjd_obs, 6),
                    dateUtc=parsed.date_obs,
                    wavelengthMicrons=round(parsed.wavelength_microns, 2),
                    band=band,  # type: ignore[arg-type]
                    width=out_width,
                    height=out_height,
                    flux=flux_flat,
                    flags=flags_flat,
                    minFlux=round(reprojected.min_flux, 5),
                    maxFlux=round(reprojected.max_flux, 5),
                    obsId=parsed.obs_id,
                )
            )
        except InvalidFitsStructureError as err:
            logger.warning("FITS structure error in %s: %s; skipping frame.", obs.obs_id, err)
        except Exception as err:
            logger.error("Error processing observation %s: %s; skipping frame.", obs.obs_id, err)

    if not frames:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process and reproject any retrieved FITS frames.",
        )

    # Strictly guarantee chronological ordering and 0-based sequential indexing
    frames.sort(key=lambda f: f.mjd)
    for idx, frame in enumerate(frames):
        frame.index = idx

    # 6. Target Metadata and Markers
    target_info = TargetInfo(
        ra=ra,
        dec=dec,
        name=preset_name,
    )

    markers = [
        CatalogMarker(
            id="target_nominal",
            ra=grid_anchor_ra,
            dec=grid_anchor_dec,
            label=f"{preset_name} (Target)" if preset_name else "Target Center",
        )
    ]

    total_dur = time.perf_counter() - t_endpoint_start
    logger.info(
        "[TIMING] /api/frames complete: target=%s fov=%.2f deg, band=%s, frames=%d/%d in %.2fs",
        preset_name or f"({ra:.4f}, {dec:.4f})", size, band, len(frames), len(selected_obs), total_dur
    )

    resp_obj = SpherexApiResponse(
        target=target_info,
        fovDegrees=size,
        band=band,  # type: ignore[arg-type]
        dataRelease=release,
        wcs=wcs_model,
        frameCount=len(frames),
        frames=frames,
        markers=markers,
        isSampleData=False,
    )
    if len(_RESPONSE_CACHE) > 100:
        _RESPONSE_CACHE.clear()
    _RESPONSE_CACHE[cache_key] = resp_obj
    return resp_obj
