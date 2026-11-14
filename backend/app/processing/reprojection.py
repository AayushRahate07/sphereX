"""Common-Grid Astrometric Reprojection Engine.

Provides fixed target-centered celestial tangent plane projection across
multi-epoch SPHEREx observations. Preserves physical proper motion and
relative motion by anchoring the spatial grid to the fixed celestial sphere.
"""

from dataclasses import dataclass
from typing import Optional, Tuple
from astropy.wcs import WCS
import numpy as np
import scipy.ndimage

from backend.app.config import DEFAULT_PLATE_SCALE_DEG
from backend.app.processing.flags import create_binary_quality_mask
from backend.app.processing.fits_parser import ParsedFitsObservation


@dataclass
class ReprojectedFrameResult:
    """Result of reprojecting a single observation onto the shared celestial grid."""
    flux: np.ndarray             # 2D float32 array of surface brightness (NaNs sanitized to 0.0)
    flags: np.ndarray            # 2D uint8 array (0 = clean, 1 = invalid)
    variance: Optional[np.ndarray]  # 2D float32 array of variance or None
    min_flux: float              # Minimum flux over valid/clean pixels
    max_flux: float              # Maximum flux over valid/clean pixels
    target_pixel_x: float        # Projected target X coordinate on shared grid (0-based)
    target_pixel_y: float        # Projected target Y coordinate on shared grid (0-based)


def create_fixed_common_wcs(
    target_ra: float,
    target_dec: float,
    fov_deg: float,
    plate_scale_deg: float = DEFAULT_PLATE_SCALE_DEG,
) -> Tuple[WCS, int, int]:
    """Construct a standardized North-up, East-left fixed celestial tangent plane WCS.

    The reference sky position (CRVAL) is anchored to the requested celestial coordinates
    and remains identical across all epochs. This fixed grid ensures that physical proper
    motion appears as image-plane displacement relative to background stars rather than
    being cancelled out by epoch-by-epoch recentering.

    Args:
        target_ra: Central Right Ascension in decimal degrees (ICRS).
        target_dec: Central Declination in decimal degrees (ICRS).
        fov_deg: Field of view in degrees.
        plate_scale_deg: Plate scale in degrees/pixel (default: ~6.1632 arcsec/px).

    Returns:
        Tuple of (Astropy WCS, output width in pixels, output height in pixels).
    """
    width = int(round(fov_deg / plate_scale_deg))
    height = int(round(fov_deg / plate_scale_deg))
    # Ensure odd pixel dimensions for symmetric centering if desired, or at least >= 3
    width = max(3, width)
    height = max(3, height)

    out_wcs = WCS(naxis=2)
    # 1-based FITS convention for CRPIX
    out_wcs.wcs.crpix = [(width + 1) / 2.0, (height + 1) / 2.0]
    out_wcs.wcs.crval = [target_ra, target_dec]
    # Standard astronomical projection: RA increases East (left, negative CDELT1),
    # Dec increases North (up, positive CDELT2)
    out_wcs.wcs.cdelt = [-plate_scale_deg, plate_scale_deg]
    out_wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]

    return out_wcs, width, height


def reproject_observation_to_grid(
    observation: ParsedFitsObservation,
    target_ra: float,
    target_dec: float,
    common_wcs: WCS,
    out_width: int,
    out_height: int,
    interpolation_order: int = 1,
) -> ReprojectedFrameResult:
    """Reproject a single SPHEREx observation onto the fixed common sky grid.

    Scientific & Engineering Design:
    1. Science flux is resampled using bilinear interpolation (order=1).
    2. Integer quality flags are NEVER interpolated as continuous flux; instead,
       the authoritative binary quality mask (0=good, 1=bad) is propagated via
       order=0 (nearest-neighbor) with strict out-of-bounds invalidation.
    3. NaNs and non-finite values in flux are replaced with 0.0 to guarantee standard
       JSON serialization without non-compliant NaN tokens, while setting the flag to 1.
    4. Target coordinates (target_ra, target_dec) are projected into the shared grid
       using common_wcs.all_world2pix().

    Limitations:
        Bilinear interpolation is a standard visual and preliminary alignment method.
        Rigorous flux-conserving pixel integration (e.g. drizzle) and full covariance
        propagation for correlated pixel noise are deferred to future milestones.

    Args:
        observation: ParsedFitsObservation from Level 2 FITS.
        target_ra: Requested target Right Ascension in decimal degrees.
        target_dec: Requested target Declination in decimal degrees.
        common_wcs: The shared Astropy WCS instance.
        out_width: Output grid width in pixels.
        out_height: Output grid height in pixels.
        interpolation_order: SciPy spline interpolation order (default 1 = bilinear).

    Returns:
        ReprojectedFrameResult with sanitized flux, quality mask, variance, and statistics.
    """
    in_wcs = observation.wcs
    in_flux = observation.flux
    in_flags = observation.raw_flags
    in_var = observation.variance

    # 1. Generate output pixel coordinates grid [0, out_height-1], [0, out_width-1]
    y_out, x_out = np.indices((out_height, out_width), dtype=np.float64)

    # 2. Output grid pixels -> Sky coordinates
    ra_out, dec_out = common_wcs.all_pix2world(x_out, y_out, 0)

    # 3. Sky coordinates -> Input detector pixel coordinates
    x_in, y_in = in_wcs.all_world2pix(ra_out, dec_out, 0)

    # 4. Out-of-bounds mask on input detector
    ny_in, nx_in = in_flux.shape
    out_of_bounds = (
        (x_in < 0.0)
        | (x_in > nx_in - 1.0)
        | (y_in < 0.0)
        | (y_in > ny_in - 1.0)
        | np.isnan(x_in)
        | np.isnan(y_in)
    )

    # 5. Resample Science Flux
    reprojected_flux = scipy.ndimage.map_coordinates(
        in_flux,
        [y_in, x_in],
        order=interpolation_order,
        mode="constant",
        cval=np.nan,
    )

    # 6. Quality Flags Propagation:
    # Convert input 32-bit flags into binary mask (0 = clean, 1 = invalid)
    in_clean_mask = create_binary_quality_mask(in_flags)

    # Resample binary mask using nearest-neighbor (order=0)
    reprojected_flags = scipy.ndimage.map_coordinates(
        in_clean_mask.astype(np.float64),
        [y_in, x_in],
        order=0,
        mode="constant",
        cval=1.0,
    )

    # Combine out-of-bounds, NaNs, and resampled flags
    final_flags = (reprojected_flags > 0.5) | out_of_bounds | np.isnan(reprojected_flux) | np.isinf(reprojected_flux)
    final_flags_uint8 = final_flags.astype(np.uint8)

    # 7. Resample Variance (if available)
    reprojected_var: Optional[np.ndarray] = None
    if in_var is not None:
        reprojected_var = scipy.ndimage.map_coordinates(
            in_var,
            [y_in, x_in],
            order=interpolation_order,
            mode="constant",
            cval=np.nan,
        )
        # Sanitize variance NaNs
        reprojected_var[final_flags] = 0.0
        reprojected_var = reprojected_var.astype(np.float32)

    # 8. Sanitize Flux Array for Safe JSON Serialization (No NaN/Infinity)
    sanitized_flux = np.where(final_flags, 0.0, reprojected_flux).astype(np.float32)

    # 9. Compute clean minFlux and maxFlux strictly over valid pixels
    clean_pixels = reprojected_flux[~final_flags]
    if len(clean_pixels) > 0:
        min_flux = float(np.nanmin(clean_pixels))
        max_flux = float(np.nanmax(clean_pixels))
    else:
        min_flux = 0.0
        max_flux = 0.0

    # 10. Project target position onto shared grid
    tgt_x, tgt_y = common_wcs.all_world2pix(target_ra, target_dec, 0)

    return ReprojectedFrameResult(
        flux=sanitized_flux,
        flags=final_flags_uint8,
        variance=reprojected_var,
        min_flux=min_flux,
        max_flux=max_flux,
        target_pixel_x=float(tgt_x),
        target_pixel_y=float(tgt_y),
    )
