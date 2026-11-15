"""RGB False-Colour Composite Endpoint for SPHEREx Sky Viewer.

Serves multi-band SPHEREx Level 2 infrared observations aligned onto a common
celestial WCS grid for scientific false-color composite visualization.
"""

import logging
import time
from typing import Dict, Tuple
from fastapi import APIRouter, HTTPException, Query, status
import numpy as np

from backend.app.config import (
    BAND_NOMINAL_WAVELENGTHS,
    DEFAULT_FOV_DEG,
    DEFAULT_PLATE_SCALE_DEG,
    DEFAULT_RELEASE,
    SUPPORTED_BANDS,
)
from backend.app.models.spherex import (
    RgbChannelInfo,
    RgbCompositeResponse,
    TargetInfo,
    WcsInfo,
)
from backend.app.processing.fits_parser import parse_fits_cutout
from backend.app.processing.reprojection import (
    create_fixed_common_wcs,
    reproject_observation_to_grid,
)
from backend.app.services.astrometry import (
    get_target_astrometry,
    propagate_coordinates_to_epoch,
)
from backend.app.services.retrieval import batch_retrieve_cutouts
from backend.app.services.selector import (
    SelectedObservation,
    SelectionError,
    TargetNotFoundError,
    get_target_name_if_preset,
    select_observations_for_target,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["rgb"])


@router.get(
    "/rgb",
    response_model=RgbCompositeResponse,
    summary="Generate multi-band false-color infrared RGB composite aligned on a shared sky grid",
    description=(
        "Retrieves real Level 2 SPHEREx observations across three distinct infrared bands (Red, Green, Blue), "
        "reprojects each channel onto a common celestial tangent plane accounting for proper motion, "
        "and computes per-channel robust display ranges while preserving original calibrated flux arrays."
    ),
)
def get_rgb_composite(
    ra: float = Query(..., description="Target Right Ascension in decimal degrees [0, 360]", ge=0.0, le=360.0),
    dec: float = Query(..., description="Target Declination in decimal degrees [-90, +90]", ge=-90.0, le=90.0),
    size: float = Query(DEFAULT_FOV_DEG, description="Field of view in degrees [0.01, 0.5]", ge=0.01, le=0.5),
    red_band: str = Query("SPHEREx-D6", description="Band mapped to Red channel (typically longest wavelength)"),
    green_band: str = Query("SPHEREx-D2", description="Band mapped to Green channel (intermediate wavelength)"),
    blue_band: str = Query("SPHEREx-D1", description="Band mapped to Blue channel (shortest wavelength)"),
    release: str = Query(DEFAULT_RELEASE, description="SPHEREx data release version"),
) -> RgbCompositeResponse:
    """Construct an RGB false-color composite from genuine Level 2 SPHEREx observations."""
    t_endpoint_start = time.perf_counter()
    channel_bands = {
        "red": red_band,
        "green": green_band,
        "blue": blue_band,
    }

    # 1. Parameter Validation
    for ch_name, band in channel_bands.items():
        if band not in SUPPORTED_BANDS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported bandpass '{band}' for channel '{ch_name}'. Must be one of: {', '.join(SUPPORTED_BANDS)}",
            )

    preset_name = get_target_name_if_preset(ra, dec)
    astro = get_target_astrometry(ra, dec, name=preset_name)

    # 2. Select compatible observations per channel (up to 3 candidates for fallback resilience)
    t_sel_start = time.perf_counter()
    selected_obs: Dict[str, SelectedObservation] = {}
    channel_candidates: Dict[str, List[SelectedObservation]] = {}
    coords_per_obs: Dict[str, Tuple[float, float]] = {}

    for ch_name, band in channel_bands.items():
        try:
            candidates = select_observations_for_target(
                ra=ra,
                dec=dec,
                band=band,
                release=release,
                max_frames=3,
                size_deg=size,
            )
            if not candidates:
                raise TargetNotFoundError(f"No SPHEREx observation found covering target in {band} ({ch_name} channel).")
            channel_candidates[ch_name] = candidates
            obs = candidates[0]
            selected_obs[ch_name] = obs

            if astro is not None:
                c_ra, c_dec = propagate_coordinates_to_epoch(ra, dec, obs.mjd, target_name=preset_name)
            else:
                c_ra, c_dec = ra, dec
            coords_per_obs[obs.obs_id] = (c_ra, c_dec)

        except SelectionError as err:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)) from err
        except TargetNotFoundError as err:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err
        except Exception as err:
            logger.error("Error selecting observation for %s channel (%s): %s", ch_name, band, err)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Archive query failed for {ch_name} channel ({band}): {err}",
            ) from err

    sel_dur_ms = (time.perf_counter() - t_sel_start) * 1000
    logger.info(
        "[TIMING] RGB channel selection for %s: 3 channels selected in %.2fms",
        preset_name or f"({ra:.4f}, {dec:.4f})", sel_dur_ms
    )

    # 3. Anchor common celestial tangent plane grid
    # Anchor to the red channel's observation epoch coordinates
    anchor_obs = selected_obs["red"]
    anchor_ra, anchor_dec = coords_per_obs[anchor_obs.obs_id]

    common_wcs, out_width, out_height = create_fixed_common_wcs(
        target_ra=anchor_ra,
        target_dec=anchor_dec,
        fov_deg=size,
        plate_scale_deg=DEFAULT_PLATE_SCALE_DEG,
    )

    wcs_model = WcsInfo(
        crval=(anchor_ra, anchor_dec),
        crpix=((out_width + 1) / 2.0, (out_height + 1) / 2.0),
        cdelt=(-DEFAULT_PLATE_SCALE_DEG, DEFAULT_PLATE_SCALE_DEG),
        ctype=("RA---TAN", "DEC--TAN"),
    )

    # 4. Batch retrieve FITS cutouts
    try:
        retrieved_paths = batch_retrieve_cutouts(
            observations=list(selected_obs.values()),
            ra=ra,
            dec=dec,
            size_deg=size,
            release=release,
            max_workers=3,
            coords_per_obs=coords_per_obs,
        )
    except Exception as err:
        logger.error("Error retrieving RGB FITS cutouts: %s", err)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to retrieve FITS cutouts for RGB channels: {err}",
        ) from err

    # Adaptive fallback for channels whose primary observation failed retrieval
    for ch_name, obs in list(selected_obs.items()):
        if obs.obs_id not in retrieved_paths:
            alt_candidates = channel_candidates.get(ch_name, [])[1:]
            for alt_obs in alt_candidates:
                logger.info("Attempting fallback observation %s for %s channel...", alt_obs.obs_id, ch_name)
                if alt_obs.obs_id not in coords_per_obs:
                    if astro is not None:
                        coords_per_obs[alt_obs.obs_id] = propagate_coordinates_to_epoch(ra, dec, alt_obs.mjd, target_name=preset_name)
                    else:
                        coords_per_obs[alt_obs.obs_id] = (ra, dec)
                alt_retrieved = batch_retrieve_cutouts(
                    observations=[alt_obs],
                    ra=ra,
                    dec=dec,
                    size_deg=size,
                    release=release,
                    max_workers=1,
                    coords_per_obs=coords_per_obs,
                )
                if alt_obs.obs_id in alt_retrieved:
                    retrieved_paths.update(alt_retrieved)
                    selected_obs[ch_name] = alt_obs
                    break

    missing_channels = [ch for ch, obs in selected_obs.items() if obs.obs_id not in retrieved_paths]
    if missing_channels:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to retrieve cutouts for channel(s): {', '.join(missing_channels)}.",
        )

    # 5. Process and Reproject Each Channel onto Common Tangent Plane
    channels_result: Dict[str, RgbChannelInfo] = {}

    for ch_name, obs in selected_obs.items():
        fits_path = retrieved_paths[obs.obs_id]
        t_ch_parse = time.perf_counter()
        parsed = parse_fits_cutout(
            source=fits_path,
            band=obs.band,
            fallback_obs_id=obs.obs_id,
            fallback_mjd=obs.mjd,
        )
        ch_parse_ms = (time.perf_counter() - t_ch_parse) * 1000

        t_ch_reproj = time.perf_counter()
        reprojected = reproject_observation_to_grid(
            observation=parsed,
            target_ra=anchor_ra,
            target_dec=anchor_dec,
            common_wcs=common_wcs,
            out_width=out_width,
            out_height=out_height,
            interpolation_order=1,
        )
        ch_reproj_ms = (time.perf_counter() - t_ch_reproj) * 1000

        file_size = fits_path.stat().st_size if fits_path.exists() else 0
        logger.info(
            "[TIMING] RGB channel '%s' (%s, %d bytes) parsed in %.2fms, reprojected (%dx%d) in %.2fms",
            ch_name, obs.obs_id, file_size, ch_parse_ms, out_width, out_height, ch_reproj_ms
        )

        clean_pixels = reprojected.flux[reprojected.flags == 0]
        if len(clean_pixels) > 0:
            p1_val = float(np.percentile(clean_pixels, 1))
            p99_val = float(np.percentile(clean_pixels, 99))
        else:
            p1_val = reprojected.min_flux
            p99_val = reprojected.max_flux

        flux_flat = [round(float(v), 5) for v in reprojected.flux.flatten()]
        flags_flat = [int(v) for v in reprojected.flags.flatten()]

        wavelength = parsed.wavelength_microns or BAND_NOMINAL_WAVELENGTHS.get(obs.band, 2.0)

        channels_result[ch_name] = RgbChannelInfo(
            band=obs.band,  # type: ignore[arg-type]
            wavelengthMicrons=round(wavelength, 2),
            obsId=parsed.obs_id,
            mjd=round(parsed.mjd_obs, 6),
            dateUtc=parsed.date_obs,
            flux=flux_flat,
            flags=flags_flat,
            minFlux=round(reprojected.min_flux, 5),
            maxFlux=round(reprojected.max_flux, 5),
            p1Flux=round(p1_val, 5),
            p99Flux=round(p99_val, 5),
        )

    # 6. Scientific Provenance Notice
    red_wave = channels_result["red"].wavelengthMicrons
    green_wave = channels_result["green"].wavelengthMicrons
    blue_wave = channels_result["blue"].wavelengthMicrons

    notice = (
        f"False-color infrared composite constructed from real SPHEREx Level 2 observations: "
        f"Red = {red_band} ({red_wave} µm), Green = {green_band} ({green_wave} µm), Blue = {blue_band} ({blue_wave} µm). "
        f"Display colors are a scientific visualization of infrared emission across 3 bands and do not represent human visual perception."
    )

    total_dur = time.perf_counter() - t_endpoint_start
    logger.info(
        "[TIMING] /api/rgb complete: target=%s fov=%.2f deg, 3 channels reprojected to (%dx%d) in %.2fs",
        preset_name or f"({ra:.4f}, {dec:.4f})", size, out_width, out_height, total_dur
    )

    return RgbCompositeResponse(
        target=TargetInfo(ra=ra, dec=dec, name=preset_name),
        fovDegrees=size,
        dataRelease=release,
        wcs=wcs_model,
        width=out_width,
        height=out_height,
        channels=channels_result,
        scientificNotice=notice,
        isSampleData=False,
    )
