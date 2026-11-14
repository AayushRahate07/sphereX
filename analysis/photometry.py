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
from photutils.aperture import CircularAperture, CircularAnnulus, aperture_photometry

from data_models import SPHERExFrame, QualityFlag, NOMINAL_PIXEL_SCALE_ARCSEC


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

    # Exclude bad pixels / cosmic rays from sky background calculation
    clean_annulus_indices = (annulus_flag_mask & (int(QualityFlag.BAD_PIXEL) | int(QualityFlag.COSMIC_RAY))) == 0
    clean_annulus_pixels = annulus_data[clean_annulus_indices]

    if len(clean_annulus_pixels) < 5:
        # Fall back to all annulus pixels if too many were flagged
        clean_annulus_pixels = annulus_data
        quality_flags |= int(QualityFlag.CALIBRATION_WARN)

    # Compute robust sigma-clipped mean, median, and standard deviation
    _, bg_median, bg_std = sigma_clipped_stats(clean_annulus_pixels, sigma=sigma_clip, maxiters=5)
    bg_per_pixel = float(bg_median)
    bg_rms = float(bg_std) if not np.isnan(bg_std) else 0.0

    # 5. Measure raw aperture flux
    aper_table = aperture_photometry(frame.data, aperture)
    raw_flux = float(aper_table["aperture_sum"][0])
    aperture_area = float(aperture.area)
    annulus_area = float(annulus.area)

    # Net source flux in image data units
    net_flux_raw = raw_flux - (aperture_area * bg_per_pixel)

    # 6. Check saturation within aperture
    aper_mask = aperture.to_mask(method="center")
    aper_data = aper_mask.get_values(frame.data)
    raw_aper_flags = aper_mask.get_values(frame.mask)
    aper_flags = raw_aper_flags.astype(np.int64) if raw_aper_flags is not None else None

    peak_pixel = float(np.max(aper_data)) if aper_data is not None and len(aper_data) > 0 else 0.0
    is_saturated = False
    if aper_flags is not None and np.any((aper_flags & int(QualityFlag.SATURATED)) > 0):
        is_saturated = True
        quality_flags |= int(QualityFlag.SATURATED)
    elif peak_pixel >= saturation_threshold_mjy_sr:
        is_saturated = True
        quality_flags |= int(QualityFlag.SATURATED)

    # 7. Propagate uncertainties
    # A. Sum of pixel variance in aperture
    uncert_sq_table = aperture_photometry(frame.uncertainty ** 2, aperture)
    var_aper = float(uncert_sq_table["aperture_sum"][0])

    # B. Variance of background estimate: (A_aper^2 / N_clean_annulus) * bg_rms^2
    n_ann_clean = max(len(clean_annulus_pixels), 1)
    var_bg = (aperture_area ** 2 / n_ann_clean) * (bg_rms ** 2)

    net_err_raw = np.sqrt(max(var_aper + var_bg, 1e-30))

    # 8. Convert to physical flux density units (microJansky = uJy)
    if frame.flux_unit == "MJy/sr":
        # Surface brightness to flux density:
        # F_uJy = (MJy/sr) * Omega_pix_sr * 1e12
        unit_scale = frame.pixel_solid_angle_sr * 1e12
    elif frame.flux_unit in ["uJy/pixel", "uJy"]:
        unit_scale = 1.0
    else:
        # Unknown unit: treat as raw and issue warning flag
        unit_scale = 1.0
        quality_flags |= int(QualityFlag.CALIBRATION_WARN)

    flux_uJy = float(net_flux_raw * unit_scale * aperture_correction)
    flux_err_uJy = float(net_err_raw * unit_scale * aperture_correction)

    # 9. Compute Signal-to-Noise Ratio (SNR)
    snr = float(flux_uJy / flux_err_uJy) if flux_err_uJy > 0 else 0.0
    if snr < 3.0:
        quality_flags |= int(QualityFlag.LOW_SNR)

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
