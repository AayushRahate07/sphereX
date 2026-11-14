"""
SPHEREx Sky Viewer — Member 3 Astronomical Frame Stacking Engine
================================================================
Implements coaddition (stacking) of multiple SPHEREx cutouts to:
1. Increase Signal-to-Noise Ratio (SNR) by ~sqrt(N) for faint sources (e.g. WISE 0855).
2. Reject transient outliers (cosmic rays, satellite streaks, hot pixel glitches).
3. Align high-proper-motion stars (e.g., Barnard's Star, WISE 0855) via sub-pixel
   shift-and-add before coaddition.
4. Propagate pixel uncertainties and consolidate quality bitmasks.

Mathematical Formulation:
--------------------------
1. Signal-to-Noise Ratio Boost:
   For N independent frames with noise sigma:
       SNR_stacked = sqrt(N) * SNR_single

2. Weighted Mean Stacking:
   w_i = 1 / (sigma_i^2)
   I_stack(x, y) = sum(w_i * I_i(x, y)) / sum(w_i)
   sigma_stack(x, y) = 1 / sqrt(sum(w_i))

3. Median Stacking:
   I_stack(x, y) = median(I_1, I_2, ..., I_N)
   sigma_stack(x, y) ~ 1.2533 * sigma / sqrt(N)
"""

from __future__ import annotations
from typing import Dict, List, Optional, Tuple
import numpy as np
import scipy.ndimage as ndimage
from photutils.centroids import centroid_quadratic

from data_models import (
    SPHERExFrame,
    QualityFlag,
    NOMINAL_PIXEL_SCALE_ARCSEC,
)


def align_frame_to_center(
    frame: SPHERExFrame,
    search_radius_pix: int = 5,
    max_shift_pix: float = 3.5,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, Tuple[float, float]]:
    """
    Measures the source centroid and shifts image data to the exact geometric center.

    Uses 2D quadratic peak-fitting centroid and sub-pixel spline interpolation (scipy.ndimage.shift).
    Returns: (shifted_data, shifted_uncertainty, shifted_mask, (dx, dy))
    """
    ny, nx = frame.shape
    x_target = (nx - 1) / 2.0
    y_target = (ny - 1) / 2.0

    # 1. Search for the brightest source pixel within search_radius of the center
    x_min = max(int(np.floor(x_target - search_radius_pix)), 0)
    x_max = min(int(np.ceil(x_target + search_radius_pix + 1)), nx)
    y_min = max(int(np.floor(y_target - search_radius_pix)), 0)
    y_max = min(int(np.ceil(y_target + search_radius_pix + 1)), ny)

    search_box = frame.data[y_min:y_max, x_min:x_max]
    y_pk_sub, x_pk_sub = np.unravel_index(np.argmax(search_box), search_box.shape)
    x_pk = x_min + int(x_pk_sub)
    y_pk = y_min + int(y_pk_sub)

    # 2. Extract a tight 5x5 sub-box around the brightest pixel for precision centroiding
    fit_radius = 2
    bx_min = max(x_pk - fit_radius, 0)
    bx_max = min(x_pk + fit_radius + 1, nx)
    by_min = max(y_pk - fit_radius, 0)
    by_max = min(y_pk + fit_radius + 1, ny)

    peak_box = frame.data[by_min:by_max, bx_min:bx_max]

    try:
        x_c_sub, y_c_sub = centroid_quadratic(peak_box)
        if np.isnan(x_c_sub) or np.isnan(y_c_sub):
            x_c, y_c = float(x_pk), float(y_pk)
        else:
            x_c = bx_min + float(x_c_sub)
            y_c = by_min + float(y_c_sub)
    except Exception:
        x_c, y_c = float(x_pk), float(y_pk)

    # 3. Calculate sub-pixel shift to center
    dx = x_target - x_c
    dy = y_target - y_c

    # Guard: if shift exceeds max_shift_pix (e.g. noise peak), do not shift
    if np.sqrt(dx ** 2 + dy ** 2) > max_shift_pix:
        dx, dy = 0.0, 0.0

    # Shift arrays: scipy shift tuple is (shift_y, shift_x)
    shifted_data = ndimage.shift(frame.data, shift=(dy, dx), order=3, mode="nearest")
    shifted_uncert = ndimage.shift(frame.uncertainty, shift=(dy, dx), order=1, mode="nearest")
    shifted_mask = ndimage.shift(frame.mask.astype(np.float64), shift=(dy, dx), order=0, mode="nearest").astype(np.int32)

    return shifted_data, shifted_uncert, shifted_mask, (dx, dy)


def stack_frames(
    frames: List[SPHERExFrame],
    method: str = "weighted_mean",
    sigma_clip: Optional[float] = 3.0,
    align_centroids: bool = True,
    max_shift_pix: float = 3.5,
) -> SPHERExFrame:
    """
    Stack (coadd) a list of SPHEREx image cutouts into a single high-SNR frame.

    Parameters:
    -----------
    frames : List[SPHERExFrame]
        Cutouts to be stacked. All frames must belong to the same detector or
        have compatible central wavelengths.
    method : str, default 'weighted_mean'
        Stacking algorithm: 'weighted_mean', 'median', or 'mean'.
    sigma_clip : Optional[float], default 3.0
        Sigma threshold for rejecting transient outliers (cosmic rays, artifacts).
    align_centroids : bool, default True
        If True, aligns sources to sub-pixel center before coaddition (shift-and-add).
    max_shift_pix : float, default 3.5
        Maximum permitted shift in pixels to prevent locking onto noise spikes.

    Returns:
    --------
    SPHERExFrame
        The coadded, high-SNR SPHERExFrame with propagated uncertainties and consolidated mask.
    """
    if not frames:
        raise ValueError("Cannot stack frames: 'frames' list is empty.")

    if len(frames) == 1:
        return frames[0]

    # 1. Compatibility Checks
    ref_frame = frames[0]
    ref_det = ref_frame.detector_id
    ref_unit = ref_frame.flux_unit
    ref_shape = ref_frame.shape

    for f in frames[1:]:
        if f.shape != ref_shape:
            raise ValueError(f"Shape mismatch: {f.shape} vs {ref_shape}")
        if f.flux_unit != ref_unit:
            raise ValueError(f"Flux unit mismatch: {f.flux_unit} vs {ref_unit}")
        if abs(f.wavelength_um - ref_frame.wavelength_um) > 0.10:
            raise ValueError(
                f"Wavelength difference too large to stack: {f.wavelength_um:.3f} um vs {ref_frame.wavelength_um:.3f} um"
            )

    n_frames = len(frames)
    ny, nx = ref_shape

    # 2. Alignment (Shift-and-Add)
    shifted_data_list = []
    shifted_uncert_list = []
    shifted_mask_list = []
    shifts_applied = []

    for f in frames:
        if align_centroids:
            s_data, s_uncert, s_mask, (dx, dy) = align_frame_to_center(f, max_shift_pix=max_shift_pix)
            shifted_data_list.append(s_data)
            shifted_uncert_list.append(s_uncert)
            shifted_mask_list.append(s_mask)
            shifts_applied.append((dx, dy))
        else:
            shifted_data_list.append(np.copy(f.data))
            shifted_uncert_list.append(np.copy(f.uncertainty))
            shifted_mask_list.append(np.copy(f.mask))
            shifts_applied.append((0.0, 0.0))

    data_cube = np.array(shifted_data_list)      # Shape: (N, ny, nx)
    uncert_cube = np.array(shifted_uncert_list)  # Shape: (N, ny, nx)
    mask_cube = np.array(shifted_mask_list)      # Shape: (N, ny, nx)

    # 3. Coaddition Algorithms
    method = method.lower()
    weights = 1.0 / np.maximum(uncert_cube ** 2, 1e-30)

    if method == "median":
        stacked_data = np.median(data_cube, axis=0)
        # Median noise propagation: sigma_med = 1.2533 * sigma / sqrt(N)
        stacked_uncert = 1.2533 * np.median(uncert_cube, axis=0) / np.sqrt(n_frames)

    elif method == "mean":
        if sigma_clip is not None and n_frames >= 3:
            med = np.median(data_cube, axis=0)
            std = np.std(data_cube, axis=0)
            # Clip outliers
            clipped_cube = np.copy(data_cube)
            diff = np.abs(data_cube - med)
            outliers = diff > (sigma_clip * np.maximum(std, 1e-10))
            clipped_cube[outliers] = np.nan
            stacked_data = np.nanmean(clipped_cube, axis=0)
            # Fill any all-nan pixels with median
            nan_mask = np.isnan(stacked_data)
            stacked_data[nan_mask] = med[nan_mask]
        else:
            stacked_data = np.mean(data_cube, axis=0)

        stacked_uncert = np.sqrt(np.sum(uncert_cube ** 2, axis=0)) / n_frames

    elif method == "weighted_mean":
        if sigma_clip is not None and n_frames >= 3:
            med = np.median(data_cube, axis=0)
            std = np.std(data_cube, axis=0)
            diff = np.abs(data_cube - med)
            outliers = diff > (sigma_clip * np.maximum(std, 1e-10))
            weights[outliers] = 0.0

        weight_sum = np.sum(weights, axis=0)
        zero_weights = weight_sum <= 0
        weight_sum[zero_weights] = 1.0

        stacked_data = np.sum(weights * data_cube, axis=0) / weight_sum
        # For pixels where all were clipped, fall back to simple median
        if np.any(zero_weights):
            med_fallback = np.median(data_cube, axis=0)
            stacked_data[zero_weights] = med_fallback[zero_weights]

        # Propagated uncertainty: 1 / sqrt(sum(w))
        stacked_uncert = 1.0 / np.sqrt(weight_sum)

    else:
        raise ValueError(f"Unknown stacking method '{method}'. Choose 'weighted_mean', 'median', or 'mean'.")

    # 4. Mask Consolidation
    # Cosmic rays: transient artifact appearing in only 1 frame.
    # Sigma-clipping rejected it, so the stacked frame is clean of transient cosmic rays!
    # Permanent bad pixels: present across majority of frames.
    bad_pixel_flag = int(QualityFlag.BAD_PIXEL)
    persistent_bad = np.sum((mask_cube & bad_pixel_flag) > 0, axis=0) >= (n_frames // 2 + 1)

    # Saturation: if any frame saturated, keep flag to warn user
    saturated_flag = int(QualityFlag.SATURATED)
    any_saturated = np.any((mask_cube & saturated_flag) > 0, axis=0)

    stacked_mask = np.zeros((ny, nx), dtype=np.int32)
    stacked_mask[persistent_bad] |= bad_pixel_flag
    stacked_mask[any_saturated] |= saturated_flag

    # 5. Metadata Consolidation
    total_exposure_s = sum(f.exposure_time_s for f in frames)
    mean_mjd = float(np.mean([f.mjd for f in frames]))
    mean_wl = float(np.mean([f.wavelength_um for f in frames]))

    stacked_flags = int(QualityFlag.GOOD)
    if np.any(any_saturated):
        stacked_flags |= int(QualityFlag.SATURATED)

    meta = {
        "stack_method": method,
        "stacked_frame_count": n_frames,
        "input_frame_ids": [f.frame_id for f in frames],
        "applied_shifts_pixels": shifts_applied,
        "theoretical_snr_boost": float(np.sqrt(n_frames)),
        "is_coadded": True,
    }

    return SPHERExFrame(
        data=stacked_data,
        uncertainty=stacked_uncert,
        mask=stacked_mask,
        frame_id=f"stacked_{method}_{n_frames}_frames",
        mjd=mean_mjd,
        timestamp_utc=ref_frame.timestamp_utc,
        detector_id=ref_det,
        band_name=ref_frame.band_name,
        wavelength_um=mean_wl,
        wavelength_fwhm_um=ref_frame.wavelength_fwhm_um,
        ra_deg=ref_frame.ra_deg,
        dec_deg=ref_frame.dec_deg,
        pixel_scale_arcsec=ref_frame.pixel_scale_arcsec,
        flux_unit=ref_frame.flux_unit,
        exposure_time_s=total_exposure_s,
        data_release=ref_frame.data_release,
        frame_quality_flags=stacked_flags,
        additional_metadata=meta,
    )
