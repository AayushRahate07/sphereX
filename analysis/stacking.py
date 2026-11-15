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

try:
    from photutils.centroids import centroid_quadratic
except (ImportError, ModuleNotFoundError):
    def centroid_quadratic(data: np.ndarray) -> Tuple[float, float]:
        """Lightweight centroid fallback when photutils is not installed."""
        total = np.nansum(data)
        if total <= 0 or not np.isfinite(total):
            ny, nx = data.shape
            return (nx - 1) / 2.0, (ny - 1) / 2.0
        y_ind, x_ind = np.indices(data.shape)
        finite_data = np.where(np.isfinite(data), np.maximum(data, 0.0), 0.0)
        tot = float(np.sum(finite_data))
        if tot <= 0:
            ny, nx = data.shape
            return (nx - 1) / 2.0, (ny - 1) / 2.0
        return float(np.sum(x_ind * finite_data) / tot), float(np.sum(y_ind * finite_data) / tot)

try:
    from data_models import (
        SPHERExFrame,
        QualityFlag,
        NOMINAL_PIXEL_SCALE_ARCSEC,
    )
except ImportError:
    from analysis.data_models import (
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
    clean_box = np.where(np.isfinite(search_box), search_box, -1e9)
    y_pk_sub, x_pk_sub = np.unravel_index(np.argmax(clean_box), clean_box.shape)
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

    # Shift arrays: sanitize NaNs before spline interpolation so NaNs do not bleed
    nan_data = ~np.isfinite(frame.data)
    safe_data = np.where(nan_data, 0.0, frame.data)
    shifted_data = ndimage.shift(safe_data, shift=(dy, dx), order=3, mode="nearest")
    shifted_nan_data = ndimage.shift(nan_data.astype(np.float64), shift=(dy, dx), order=0, mode="nearest") > 0.5
    shifted_data[shifted_nan_data] = np.nan

    nan_u = ~np.isfinite(frame.uncertainty) | (frame.uncertainty <= 0.0)
    safe_u = np.where(nan_u, 0.0, frame.uncertainty)
    shifted_uncert = ndimage.shift(safe_u, shift=(dy, dx), order=1, mode="nearest")
    shifted_nan_u = ndimage.shift(nan_u.astype(np.float64), shift=(dy, dx), order=0, mode="nearest") > 0.5
    shifted_uncert[shifted_nan_u] = np.nan

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
    shifted_raw_flags_list = []
    shifts_applied = []

    has_raw = any(f.raw_flags is not None for f in frames)

    for f in frames:
        if align_centroids:
            s_data, s_uncert, s_mask, (dx, dy) = align_frame_to_center(f, max_shift_pix=max_shift_pix)
            shifted_data_list.append(s_data)
            shifted_uncert_list.append(s_uncert)
            shifted_mask_list.append(s_mask)
            shifts_applied.append((dx, dy))
            if has_raw and f.raw_flags is not None:
                s_raw = ndimage.shift(f.raw_flags.astype(np.float64), shift=(dy, dx), order=0, mode="nearest").astype(np.int32)
                shifted_raw_flags_list.append(s_raw)
        else:
            shifted_data_list.append(np.copy(f.data))
            shifted_uncert_list.append(np.copy(f.uncertainty))
            shifted_mask_list.append(np.copy(f.mask))
            shifts_applied.append((0.0, 0.0))
            if has_raw and f.raw_flags is not None:
                shifted_raw_flags_list.append(np.copy(f.raw_flags))

    data_cube = np.array(shifted_data_list)      # Shape: (N, ny, nx)
    uncert_cube = np.array(shifted_uncert_list)  # Shape: (N, ny, nx)
    mask_cube = np.array(shifted_mask_list)      # Shape: (N, ny, nx)

    # 3. Coaddition Algorithms with Strict Bad-Pixel Masking
    method = method.lower()
    fatal_mask = int(QualityFlag.BAD_PIXEL | QualityFlag.COSMIC_RAY | QualityFlag.EDGE_ARTIFACT)
    valid_samples = np.isfinite(data_cube) & ((mask_cube & fatal_mask) == 0)

    stacked_data = np.full((ny, nx), np.nan, dtype=np.float64)
    stacked_uncert = np.full((ny, nx), np.nan, dtype=np.float64)
    stacked_mask = np.zeros((ny, nx), dtype=np.int32)

    if method == "median":
        for y in range(ny):
            for x in range(nx):
                v_mask = valid_samples[:, y, x]
                if not np.any(v_mask):
                    stacked_data[y, x] = np.nan
                    stacked_uncert[y, x] = np.nan
                    stacked_mask[y, x] |= int(QualityFlag.BAD_PIXEL)
                else:
                    d_vals = data_cube[v_mask, y, x]
                    stacked_data[y, x] = float(np.median(d_vals))
                    u_mask = v_mask & np.isfinite(uncert_cube[:, y, x]) & (uncert_cube[:, y, x] > 0)
                    if np.any(u_mask):
                        u_vals = uncert_cube[u_mask, y, x]
                        stacked_uncert[y, x] = float(1.2533 * np.median(u_vals) / np.sqrt(len(u_vals)))
                    else:
                        stacked_uncert[y, x] = np.nan
                        stacked_mask[y, x] |= int(QualityFlag.CALIBRATION_WARN)

    elif method == "mean":
        for y in range(ny):
            for x in range(nx):
                v_mask = valid_samples[:, y, x]
                if not np.any(v_mask):
                    stacked_data[y, x] = np.nan
                    stacked_uncert[y, x] = np.nan
                    stacked_mask[y, x] |= int(QualityFlag.BAD_PIXEL)
                else:
                    d_vals = data_cube[v_mask, y, x]
                    if sigma_clip is not None and len(d_vals) >= 3:
                        med = np.median(d_vals)
                        std = np.std(d_vals)
                        diff = np.abs(d_vals - med)
                        clean = diff <= (sigma_clip * max(float(std), 1e-10))
                        if np.any(clean):
                            d_vals = d_vals[clean]
                    stacked_data[y, x] = float(np.mean(d_vals))
                    u_mask = v_mask & np.isfinite(uncert_cube[:, y, x]) & (uncert_cube[:, y, x] > 0)
                    if np.any(u_mask):
                        u_vals = uncert_cube[u_mask, y, x]
                        stacked_uncert[y, x] = float(np.sqrt(np.sum(u_vals ** 2)) / len(u_vals))
                    else:
                        stacked_uncert[y, x] = np.nan
                        stacked_mask[y, x] |= int(QualityFlag.CALIBRATION_WARN)

    elif method == "weighted_mean":
        for y in range(ny):
            for x in range(nx):
                v_mask = valid_samples[:, y, x]
                if not np.any(v_mask):
                    stacked_data[y, x] = np.nan
                    stacked_uncert[y, x] = np.nan
                    stacked_mask[y, x] |= int(QualityFlag.BAD_PIXEL)
                else:
                    u_mask = v_mask & np.isfinite(uncert_cube[:, y, x]) & (uncert_cube[:, y, x] > 0)
                    if np.any(u_mask):
                        d_vals = data_cube[u_mask, y, x]
                        u_vals = uncert_cube[u_mask, y, x]
                        w_vals = 1.0 / (u_vals ** 2)

                        if sigma_clip is not None and len(d_vals) >= 3:
                            med = np.median(d_vals)
                            std = np.std(d_vals)
                            diff = np.abs(d_vals - med)
                            outliers = diff > (sigma_clip * max(float(std), 1e-10))
                            w_vals[outliers] = 0.0

                        w_sum = float(np.sum(w_vals))
                        if w_sum > 0:
                            stacked_data[y, x] = float(np.sum(w_vals * d_vals) / w_sum)
                            stacked_uncert[y, x] = float(1.0 / np.sqrt(w_sum))
                        else:
                            stacked_data[y, x] = float(np.median(d_vals))
                            stacked_uncert[y, x] = float(np.mean(u_vals))
                            stacked_mask[y, x] |= int(QualityFlag.CALIBRATION_WARN)
                    else:
                        # Samples have valid flux, but all uncertainties are unavailable / NaN
                        d_vals = data_cube[v_mask, y, x]
                        stacked_data[y, x] = float(np.median(d_vals))
                        stacked_uncert[y, x] = np.nan
                        stacked_mask[y, x] |= int(QualityFlag.CALIBRATION_WARN)

    else:
        raise ValueError(f"Unknown stacking method '{method}'. Choose 'weighted_mean', 'median', or 'mean'.")

    # 4. Mask Consolidation
    bad_pixel_flag = int(QualityFlag.BAD_PIXEL)
    persistent_bad = np.sum((mask_cube & bad_pixel_flag) > 0, axis=0) >= (n_frames // 2 + 1)
    saturated_flag = int(QualityFlag.SATURATED)
    any_saturated = np.any((mask_cube & saturated_flag) > 0, axis=0)

    stacked_mask[persistent_bad] |= bad_pixel_flag
    stacked_mask[any_saturated] |= saturated_flag

    # Consolidate raw_flags if available:
    # Stacked raw_flags reflects the contributing valid samples at each pixel.
    # Rejected epoch defects (e.g. transients) do NOT contaminate the valid stacked pixel flags.
    stacked_raw_flags = None
    all_epochs_raw_flags = None
    if len(shifted_raw_flags_list) > 0:
        raw_cube = np.array(shifted_raw_flags_list, dtype=np.int32)
        all_epochs_raw_flags = np.bitwise_or.reduce(raw_cube, axis=0)

        masked_raw = np.where(valid_samples, raw_cube, 0)
        stacked_raw_flags = np.bitwise_or.reduce(masked_raw, axis=0)

        # Where ALL samples were invalid at a pixel, preserve all-epoch defect flags for diagnostics
        has_any_valid = np.any(valid_samples, axis=0)
        all_invalid = ~has_any_valid
        stacked_raw_flags[all_invalid] = all_epochs_raw_flags[all_invalid]

        # Consolidate persistent defects and saturation
        if np.any(persistent_bad):
            bad_raw = np.bitwise_or.reduce(np.where((mask_cube & bad_pixel_flag) > 0, raw_cube, 0), axis=0)
            stacked_raw_flags[persistent_bad] |= bad_raw[persistent_bad]
        if np.any(any_saturated):
            sat_raw = np.bitwise_or.reduce(np.where((mask_cube & saturated_flag) > 0, raw_cube, 0), axis=0)
            stacked_raw_flags[any_saturated] |= sat_raw[any_saturated]

    # 5. Metadata Consolidation
    total_exposure_s = sum(f.exposure_time_s for f in frames)
    mean_mjd = float(np.mean([f.mjd for f in frames]))
    mean_wl = float(np.mean([f.wavelength_um for f in frames]))

    stacked_flags = int(QualityFlag.GOOD)
    if np.any(any_saturated):
        stacked_flags |= int(QualityFlag.SATURATED)
    if np.any(persistent_bad):
        stacked_flags |= int(QualityFlag.BAD_PIXEL)

    return SPHERExFrame(
        data=stacked_data,
        uncertainty=stacked_uncert,
        mask=stacked_mask,
        frame_id=f"stacked_{ref_frame.frame_id}_{method}",
        mjd=mean_mjd,
        timestamp_utc=f"Stack_{n_frames}_epochs",
        detector_id=ref_det,
        band_name=ref_frame.band_name,
        wavelength_um=mean_wl,
        wavelength_fwhm_um=ref_frame.wavelength_fwhm_um,
        ra_deg=ref_frame.ra_deg,
        dec_deg=ref_frame.dec_deg,
        pixel_scale_arcsec=ref_frame.pixel_scale_arcsec,
        flux_unit=ref_unit,
        exposure_time_s=total_exposure_s,
        data_release=ref_frame.data_release,
        frame_quality_flags=stacked_flags,
        additional_metadata={
            "n_frames_stacked": n_frames,
            "stacked_frame_count": n_frames,
            "stack_method": method,
            "sigma_clip": sigma_clip,
            "shifts_applied": shifts_applied,
            "applied_shifts_pixels": shifts_applied,
            "input_frames": [f.frame_id for f in frames],
            "input_frame_ids": [f.frame_id for f in frames],
            "theoretical_snr_boost": float(np.sqrt(n_frames)),
            "is_coadded": True,
            "raw_flags": stacked_raw_flags,
            "all_epochs_raw_flags": all_epochs_raw_flags,
        },
        raw_flags=stacked_raw_flags,
    )
