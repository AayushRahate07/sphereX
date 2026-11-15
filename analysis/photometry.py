"""
SPHEREx Sky Viewer — Member 3 Core Photometry Engine
=====================================================
Implements aperture photometry and sky background estimation tailored to the
SPHEREx instrument characteristics.

Astrophysical Principles:
-------------------------
1. Aperture Photometry:
   Measures the total flux within a circular aperture centered on the astronomical source.
   Total raw sum inside aperture = S_raw.

2. Background Subtraction:
   Astronomical detectors capture zodiacal light, diffuse galactic dust emission,
   and cosmic infrared background. A circular annulus surrounding the aperture
   estimates the local sky background level (B) per pixel.
   Robust sigma-clipped statistics reject contaminants (cosmic rays, faint background
   stars) in the annulus.

3. Net Source Flux:
   F_net = S_raw - (A_aper * B)
   where A_aper is the effective pixel area of the circular aperture.

4. Error Propagation:
   sigma_net^2 = sigma_aper^2 + (A_aper^2 / N_ann) * sigma_ann^2
   where sigma_aper^2 is the sum of pixel variance inside the aperture,
   and (A_aper^2 / N_ann) * sigma_ann^2 accounts for the uncertainty in the
   background estimate.

5. Unit Conversion:
   SPHEREx level-2 cutouts are calibrated in surface brightness (MJy / sr).
   Total flux density in microJansky (uJy) is:
       F_uJy = F_net * Omega_pix * 1e12
   where Omega_pix is the pixel solid angle in steradians.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple
import numpy as np

from astropy.stats import sigma_clipped_stats

try:
    from photutils.aperture import CircularAperture, CircularAnnulus, aperture_photometry
    HAS_PHOTUTILS = True
except (ImportError, ModuleNotFoundError):
    HAS_PHOTUTILS = False

    class CircularAperture:
        """Lightweight circular aperture fallback when photutils is not installed."""
        def __init__(self, positions: Tuple[float, float], r: float):
            self.positions = positions
            self.r = float(r)
            self.area = np.pi * (self.r ** 2)

        def to_mask(self, method: str = "center"):
            xc, yc, r = self.positions[0], self.positions[1], self.r

            class _ApertureMaskHelper:
                def get_values(self, data: np.ndarray) -> np.ndarray:
                    if data is None:
                        return np.array([])
                    ny, nx = data.shape
                    y, x = np.ogrid[:ny, :nx]
                    return data[(x - xc) ** 2 + (y - yc) ** 2 <= (r ** 2)]

            return _ApertureMaskHelper()

    class CircularAnnulus:
        """Lightweight circular annulus fallback when photutils is not installed."""
        def __init__(self, positions: Tuple[float, float], r_in: float, r_out: float):
            self.positions = positions
            self.r_in = float(r_in)
            self.r_out = float(r_out)
            self.area = np.pi * (self.r_out ** 2 - self.r_in ** 2)

        def to_mask(self, method: str = "center"):
            xc, yc, r_in, r_out = self.positions[0], self.positions[1], self.r_in, self.r_out

            class _AnnulusMaskHelper:
                def get_values(self, data: np.ndarray) -> np.ndarray:
                    if data is None:
                        return np.array([])
                    ny, nx = data.shape
                    y, x = np.ogrid[:ny, :nx]
                    r_sq = (x - xc) ** 2 + (y - yc) ** 2
                    return data[(r_sq >= r_in ** 2) & (r_sq < r_out ** 2)]

            return _AnnulusMaskHelper()

    def aperture_photometry(data: np.ndarray, aperture: CircularAperture) -> dict:
        vals = aperture.to_mask().get_values(data)
        return {"aperture_sum": [float(np.nansum(vals)) if len(vals) > 0 else 0.0]}

try:
    from data_models import SPHERExFrame, QualityFlag, NOMINAL_PIXEL_SCALE_ARCSEC
except ImportError:
    from analysis.data_models import SPHERExFrame, QualityFlag, NOMINAL_PIXEL_SCALE_ARCSEC


@dataclass
class PhotometryMeasurement:
    """
    Result of aperture photometry on a single SPHEREx frame.
    """
    flux_uJy: float
    flux_err_uJy: float
    raw_flux: float
    background_per_pixel: float
    background_rms: float
    aperture_area_pix: float
    annulus_area_pix: float
    snr: float
    quality_flags: int
    is_saturated: bool
    peak_pixel_value: float
    center_xy: Tuple[float, float]
    aperture_radius_pix: float
    annulus_radii_pix: Tuple[float, float]


def measure_aperture_photometry(
    frame: SPHERExFrame,
    center_xy: Optional[Tuple[float, float]] = None,
    aperture_radius_pix: float = 2.5,
    annulus_inner_pix: float = 4.0,
    annulus_outer_pix: float = 6.0,
    sigma_clip: float = 3.0,
    aperture_correction: float = 1.0,
    saturation_threshold_mjy_sr: float = 50.0,
) -> PhotometryMeasurement:
    """
    Perform background-subtracted circular aperture photometry on a SPHERExFrame.

    Parameters:
    -----------
    frame : SPHERExFrame
        The input image cutout with data, uncertainty, and mask.
    center_xy : Optional[Tuple[float, float]], default None
        Source position (x, y) in pixel coordinates (0-indexed).
        If None, the geometric center of the cutout is used.
    aperture_radius_pix : float, default 2.5
        Radius of circular aperture in pixels (~15.5 arcsec).
    annulus_inner_pix : float, default 4.0
        Inner radius of concentric background annulus in pixels (~24.8 arcsec).
    annulus_outer_pix : float, default 6.0
        Outer radius of concentric background annulus in pixels (~37.2 arcsec).
    sigma_clip : float, default 3.0
        Sigma clipping threshold to reject outliers in the background annulus.
    aperture_correction : float, default 1.0
        Correction factor (>= 1.0) to account for flux in PSF wings beyond aperture radius.
    saturation_threshold_mjy_sr : float, default 50.0
        Surface brightness threshold above which pixels are considered saturated.

    Returns:
    --------
    PhotometryMeasurement
        Comprehensive photometric measurement with flux, error, background, and flags.
    """
    ny, nx = frame.shape

    # 1. Determine aperture center
    if center_xy is None:
        center_xy = ((nx - 1) / 2.0, (ny - 1) / 2.0)
    x_c, y_c = center_xy

    quality_flags = int(frame.frame_quality_flags)

    # 2. Check edge clipping: aperture or annulus extends outside image boundary
    if (
        (x_c - annulus_outer_pix < 0)
        or (x_c + annulus_outer_pix >= nx)
        or (y_c - annulus_outer_pix < 0)
        or (y_c + annulus_outer_pix >= ny)
    ):
        quality_flags |= int(QualityFlag.EDGE_ARTIFACT)

    # 3. Create circular aperture and background annulus
    aperture = CircularAperture((x_c, y_c), r=aperture_radius_pix)
    annulus = CircularAnnulus((x_c, y_c), r_in=annulus_inner_pix, r_out=annulus_outer_pix)

    # 4. Extract and estimate local sky background from annulus
    annulus_mask = annulus.to_mask(method="center")
    annulus_data = annulus_mask.get_values(frame.data)
    annulus_flag_mask = (
        annulus_mask.get_values(frame.mask).astype(np.int64)
        if annulus_mask.get_values(frame.mask) is not None
        else np.array([], dtype=np.int64)
    )

    if annulus_data is None or len(annulus_data) == 0:
        raise ValueError(f"Frame {frame.frame_id}: Annulus contains 0 pixels. Check cutout dimensions.")

    # Exclude bad pixels, cosmic rays, and saturated/edge pixels from sky background
    annulus_fatal = int(
        QualityFlag.BAD_PIXEL | QualityFlag.COSMIC_RAY | QualityFlag.EDGE_ARTIFACT | QualityFlag.SATURATED
    )
    clean_annulus_indices = np.isfinite(annulus_data) & ((annulus_flag_mask & annulus_fatal) == 0)
    clean_annulus_pixels = annulus_data[clean_annulus_indices]

    if len(clean_annulus_pixels) < 5:
        # Fall back to finite annulus pixels if too many were flagged
        finite_annulus = annulus_data[np.isfinite(annulus_data)]
        if len(finite_annulus) > 0:
            clean_annulus_pixels = finite_annulus
        else:
            clean_annulus_pixels = np.array([0.0])
        quality_flags |= int(QualityFlag.CALIBRATION_WARN)

    # Compute robust sigma-clipped mean, median, and standard deviation
    _, bg_median, bg_std = sigma_clipped_stats(clean_annulus_pixels, sigma=sigma_clip, maxiters=5)
    bg_per_pixel = float(bg_median) if np.isfinite(bg_median) else 0.0
    bg_rms = float(bg_std) if np.isfinite(bg_std) else 0.0

    # 5. Measure aperture pixels and identify invalid/flagged samples
    aperture_area = float(aperture.area)
    annulus_area = float(annulus.area)

    aper_mask = aperture.to_mask(method="center")
    aper_data = aper_mask.get_values(frame.data)
    raw_aper_flags = aper_mask.get_values(frame.mask)
    aper_flags = raw_aper_flags.astype(np.int64) if raw_aper_flags is not None else np.array([], dtype=np.int64)
    raw_aper_uncert = aper_mask.get_values(frame.uncertainty) if frame.uncertainty is not None else None
    aper_uncert = raw_aper_uncert.astype(np.float64) if raw_aper_uncert is not None else np.array([], dtype=np.float64)

    n_total = len(aper_data)
    fatal_mask = int(QualityFlag.BAD_PIXEL | QualityFlag.COSMIC_RAY | QualityFlag.EDGE_ARTIFACT)
    is_bad = ((aper_flags & fatal_mask) > 0) | (~np.isfinite(aper_data))
    is_sat = (aper_flags & int(QualityFlag.SATURATED)) > 0

    peak_pixel = float(np.nanmax(aper_data)) if (len(aper_data) > 0 and np.any(np.isfinite(aper_data))) else 0.0
    is_saturated = False
    if np.any(is_sat) or peak_pixel >= saturation_threshold_mjy_sr:
        is_saturated = True
        quality_flags |= int(QualityFlag.SATURATED)

    if np.any(is_bad):
        quality_flags |= int(QualityFlag.BAD_PIXEL)
    if np.any((aper_flags & int(QualityFlag.EDGE_ARTIFACT)) > 0):
        quality_flags |= int(QualityFlag.EDGE_ARTIFACT)
    if np.any((aper_flags & int(QualityFlag.COSMIC_RAY)) > 0):
        quality_flags |= int(QualityFlag.COSMIC_RAY)

    # 6. Apply scientifically defensible bad-pixel policy for source aperture
    n_valid = int(np.sum(~is_bad))
    if n_valid == 0 or (n_valid / max(n_total, 1) < 0.5):
        # Inadequate aperture coverage: reject measurement explicitly with NaN
        quality_flags |= int(QualityFlag.BAD_PIXEL | QualityFlag.CALIBRATION_WARN)
        raw_flux = np.nan
        net_flux_raw = np.nan
    elif n_valid < n_total:
        # Partial aperture coverage: scale valid sum by area fraction and warn
        quality_flags |= int(QualityFlag.BAD_PIXEL | QualityFlag.CALIBRATION_WARN)
        valid_sum = float(np.sum(aper_data[~is_bad]))
        raw_flux = valid_sum * (n_total / n_valid)
        net_flux_raw = raw_flux - (float(n_total) * bg_per_pixel)
    else:
        # Full coverage
        raw_flux = float(np.sum(aper_data))
        net_flux_raw = raw_flux - (float(n_total) * bg_per_pixel)

    # 7. Propagate uncertainties
    valid_unc = np.isfinite(aper_uncert) & (aper_uncert > 0.0) & (~is_bad)
    n_unc_valid = int(np.sum(valid_unc))
    n_ann_clean = max(len(clean_annulus_pixels), 1)
    var_bg = (float(n_total) ** 2 / n_ann_clean) * (bg_rms ** 2)

    if n_unc_valid == 0 or not np.isfinite(net_flux_raw):
        # Unavailable uncertainty or invalid source flux
        var_aper = np.nan
        net_err_raw = np.nan
        quality_flags |= int(QualityFlag.CALIBRATION_WARN)
    else:
        # For partial coverage where raw flux is scaled by c = (n_total / n_valid),
        # linear error propagation dictates that Var(c * X) = c**2 * Var(X).
        scale_c = float(n_total) / float(n_valid)
        unc_coverage_ratio = float(n_valid) / float(n_unc_valid)
        sum_unc_sq = float(np.sum(aper_uncert[valid_unc] ** 2))
        var_aper = (scale_c ** 2) * unc_coverage_ratio * sum_unc_sq
        if n_unc_valid < n_valid:
            quality_flags |= int(QualityFlag.CALIBRATION_WARN)
        net_err_raw = np.sqrt(max(var_aper + var_bg, 1e-30))

    # 8. Convert to physical flux density units (microJansky = uJy)
    if frame.flux_unit == "MJy/sr":
        unit_scale = frame.pixel_solid_angle_sr * 1e12
    elif frame.flux_unit in ["uJy/pixel", "uJy"]:
        unit_scale = 1.0
    else:
        unit_scale = 1.0
        quality_flags |= int(QualityFlag.CALIBRATION_WARN)

    if np.isfinite(net_flux_raw):
        flux_uJy = float(net_flux_raw * unit_scale * aperture_correction)
    else:
        flux_uJy = np.nan

    if np.isfinite(net_err_raw):
        flux_err_uJy = float(net_err_raw * unit_scale * aperture_correction)
    else:
        flux_err_uJy = np.nan

    # 9. Compute Signal-to-Noise Ratio (SNR)
    if np.isfinite(flux_uJy) and np.isfinite(flux_err_uJy) and flux_err_uJy > 0:
        snr = float(flux_uJy / flux_err_uJy)
        if snr < 3.0:
            quality_flags |= int(QualityFlag.LOW_SNR)
    elif np.isfinite(flux_uJy) and flux_uJy <= 0:
        # Valid measurement, but net flux non-positive after sky background subtraction
        snr = 0.0
        quality_flags |= int(QualityFlag.LOW_SNR)
    else:
        # Rejected measurement: do NOT tag LOW_SNR; preserve rejection/calibration flags
        snr = 0.0

    return PhotometryMeasurement(
        flux_uJy=flux_uJy,
        flux_err_uJy=flux_err_uJy,
        raw_flux=raw_flux,
        background_per_pixel=bg_per_pixel,
        background_rms=bg_rms,
        aperture_area_pix=aperture_area,
        annulus_area_pix=annulus_area,
        snr=snr,
        quality_flags=quality_flags,
        is_saturated=is_saturated,
        peak_pixel_value=peak_pixel,
        center_xy=center_xy,
        aperture_radius_pix=aperture_radius_pix,
        annulus_radii_pix=(annulus_inner_pix, annulus_outer_pix),
    )
