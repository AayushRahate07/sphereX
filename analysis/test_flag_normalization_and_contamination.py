"""
Comprehensive Verification Suite: SPHEREx Quality Flag Normalization & Contamination Prevention
================================================================================================
Covers Member 3 core requirements:
1. Normalization of official SPHEREx Level 2 FLAGS to QualityFlag enum without loss of raw bitmask.
2. Non-fatal behavior for astronomical sources (FLAG_SOURCE = 2097152) and full-sampling flags.
3. Fatal behavior for detector defects (FLAG_NONFUNC = 64, FLAG_TRANSIENT = 1, FLAG_OVERFLOW = 2).
4. Photometric aperture bad-pixel policy:
   - Rejection (< 50% valid pixels -> NaN flux, SNR=0, BAD_PIXEL | CALIBRATION_WARN).
   - Scaling (>= 50% valid pixels -> valid sum scaled by area, BAD_PIXEL | CALIBRATION_WARN).
5. Annulus background estimation excluding all fatal defects (BAD_PIXEL, COSMIC_RAY, SATURATED).
6. Photometric propagation when uncertainty is missing/NaN (flux_err = NaN, SNR = 0, CALIBRATION_WARN).
7. Stacking resilience against bad pixels and non-finite values in single epochs.
8. Stacking weighted mean resilience when an epoch has NaN uncertainty.
9. Stacking edge cases: all epochs invalid, or all uncertainties unavailable.
10. Wavelength provenance metadata tracking (EPSF_TABLE vs FITS_HEADER vs NOMINAL_BANDPASS_MIDPOINT).
"""

from pathlib import Path
import numpy as np
import pytest
from astropy.io import fits
from astropy.wcs import WCS

import sys
analysis_dir = str(Path(__file__).parent.resolve())
if analysis_dir not in sys.path:
    sys.path.insert(0, analysis_dir)

from data_models import (
    SPHERExFrame,
    QualityFlag,
    normalize_quality_flags,
    create_synthetic_cutout,
    FLAG_TRANSIENT,
    FLAG_OVERFLOW,
    FLAG_SUR_ERROR,
    FLAG_NONFUNC,
    FLAG_DICHROIC,
    FLAG_FULLSAMPLE,
    FLAG_SOURCE,
    FLAG_SNOWBALL,
)
from fits_loader import load_cutout_from_fits
from photometry import measure_aperture_photometry, CircularAperture
from stacking import stack_frames
from analysis import extract_light_curve, extract_spectrum

REAL_CACHED_FITS = Path("backend/cache/fits/spherex_dr1_2025W19_1B_0116_1_SPHEREx-D6_133.7613_-7.2423_0.0500.fits")


# =============================================================================
# 1. Quality Flag Normalization Tests
# =============================================================================
def test_normalize_quality_flags_mission_flags():
    """Verify official Level 2 bit positions are accurately normalized."""
    raw = np.array([
        0,                                   # Good
        FLAG_SOURCE,                         # 2097152: Known astronomical source (MUST be valid)
        FLAG_FULLSAMPLE,                     # 4096: Full sampling (MUST be valid)
        FLAG_NONFUNC,                        # 64: Non-functional pixel (fatal -> BAD_PIXEL)
        FLAG_TRANSIENT,                      # 1: Transient / cosmic ray (fatal -> COSMIC_RAY)
        FLAG_OVERFLOW,                       # 2: ADC overflow (fatal -> SATURATED)
        FLAG_SUR_ERROR,                      # 4: Sample-up-the-ramp fit error (fatal -> BAD_PIXEL)
        FLAG_DICHROIC,                       # 128: Dichroic boundary (fatal -> BAD_PIXEL)
        FLAG_SNOWBALL,                       # 524288: Snowball artifact (fatal -> BAD_PIXEL)
        FLAG_NONFUNC | FLAG_TRANSIENT,       # Combined defects
        FLAG_SOURCE | FLAG_NONFUNC,          # Source on a bad pixel -> must still flag BAD_PIXEL
    ], dtype=np.int32)

    norm = normalize_quality_flags(raw, is_mission_flags=True)

    # Clean pixels and benign indicators
    assert norm[0] == 0, "Clean pixel must normalize to GOOD (0)"
    assert norm[1] == 0, f"FLAG_SOURCE ({FLAG_SOURCE}) must normalize to GOOD (0), not invalidate target"
    assert norm[2] == 0, f"FLAG_FULLSAMPLE ({FLAG_FULLSAMPLE}) must normalize to GOOD (0)"

    # Fatal defects
    assert norm[3] == int(QualityFlag.BAD_PIXEL), "FLAG_NONFUNC must normalize to BAD_PIXEL"
    assert norm[4] == int(QualityFlag.COSMIC_RAY), "FLAG_TRANSIENT must normalize to COSMIC_RAY"
    assert norm[5] == int(QualityFlag.SATURATED), "FLAG_OVERFLOW must normalize to SATURATED"
    assert norm[6] == int(QualityFlag.BAD_PIXEL), "FLAG_SUR_ERROR must normalize to BAD_PIXEL"
    assert norm[7] == int(QualityFlag.BAD_PIXEL), "FLAG_DICHROIC must normalize to BAD_PIXEL"
    assert norm[8] == int(QualityFlag.COSMIC_RAY), "FLAG_SNOWBALL must normalize to COSMIC_RAY"

    # Multi-bit combinations
    assert norm[9] == int(QualityFlag.BAD_PIXEL | QualityFlag.COSMIC_RAY)
    assert norm[10] == int(QualityFlag.BAD_PIXEL)


def test_normalize_quality_flags_legacy_enum():
    """Verify legacy QualityFlag enum masks pass through unchanged when is_mission_flags=False."""
    legacy = np.array([0, 1, 2, 4, 8, 16, 32], dtype=np.int32)
    norm = normalize_quality_flags(legacy, is_mission_flags=False)
    np.testing.assert_array_equal(norm, legacy)


# =============================================================================
# 2. Photometry Aperture Bad-Pixel Policy Tests
# =============================================================================
def test_photometry_aperture_bad_pixel_rejection():
    """Verify aperture photometry rejects measurement when > 50% pixels are bad."""
    frame = create_synthetic_cutout(
        detector_id=2,
        wavelength_um=1.35,
        flux_uJy=2500.0,
        cutout_size=25,
        background_level_mjy_sr=1.0,
        noise_sigma_mjy_sr=0.01,
        source_offset_pix=(0.0, 0.0),
    )

    # Center is at (12, 12). Aperture radius 2.5 has 21 pixels.
    # Corrupt 15 of them (> 50%)
    aper = CircularAperture((12.0, 12.0), 2.5)
    ny, nx = frame.shape
    y, x = np.ogrid[:ny, :nx]
    in_aper = (x - 12.0) ** 2 + (y - 12.0) ** 2 <= (2.5 ** 2)
    aper_coords = np.argwhere(in_aper)

    for cy, cx in aper_coords[:15]:
        frame.mask[cy, cx] |= int(QualityFlag.BAD_PIXEL)
        frame.data[cy, cx] = np.nan

    meas = measure_aperture_photometry(frame, center_xy=(12.0, 12.0), aperture_radius_pix=2.5)

    assert np.isnan(meas.flux_uJy), f"Expected NaN flux for severely corrupted aperture, got {meas.flux_uJy}"
    assert np.isnan(meas.raw_flux)
    assert meas.snr == 0.0
    assert bool(meas.quality_flags & int(QualityFlag.BAD_PIXEL))
    assert bool(meas.quality_flags & int(QualityFlag.CALIBRATION_WARN))
    assert not bool(meas.quality_flags & int(QualityFlag.LOW_SNR)), "Rejected measurement must not be flagged LOW_SNR"


def test_photometry_aperture_bad_pixel_scaling():
    """Verify aperture photometry scales valid flux when < 50% pixels are bad."""
    injected_flux = 3000.0
    frame = create_synthetic_cutout(
        detector_id=2,
        wavelength_um=1.35,
        flux_uJy=injected_flux,
        cutout_size=25,
        background_level_mjy_sr=0.5,
        noise_sigma_mjy_sr=0.005,
        source_offset_pix=(0.0, 0.0),
    )

    # Corrupt 3 out of 21 pixels in the aperture (14% bad, 86% valid)
    ny, nx = frame.shape
    y, x = np.ogrid[:ny, :nx]
    in_aper = (x - 12.0) ** 2 + (y - 12.0) ** 2 <= (2.5 ** 2)
    aper_coords = np.argwhere(in_aper)

    # Corrupt border pixels of the aperture
    for cy, cx in aper_coords[-3:]:
        frame.mask[cy, cx] |= int(QualityFlag.BAD_PIXEL)
        frame.data[cy, cx] = np.nan

    meas = measure_aperture_photometry(frame, center_xy=(12.0, 12.0), aperture_radius_pix=2.5)

    assert np.isfinite(meas.flux_uJy), "Scaled flux should be finite"
    assert meas.snr > 30.0
    assert bool(meas.quality_flags & int(QualityFlag.BAD_PIXEL))
    assert bool(meas.quality_flags & int(QualityFlag.CALIBRATION_WARN))
    # Should recover flux reasonably close to injected value
    err_percent = abs(meas.flux_uJy - injected_flux) / injected_flux * 100.0
    assert err_percent < 25.0, f"Scaled flux error {err_percent:.2f}% exceeded 25%"


def test_photometry_annulus_excludes_fatal_flags():
    """Verify background annulus ignores fatal bad pixels and cosmic rays."""
    frame_clean = create_synthetic_cutout(
        detector_id=1,
        wavelength_um=0.95,
        flux_uJy=1500.0,
        cutout_size=25,
        background_level_mjy_sr=1.2,
        noise_sigma_mjy_sr=0.01,
        source_offset_pix=(0.0, 0.0),
    )
    meas_clean = measure_aperture_photometry(frame_clean)

    frame_corrupt = create_synthetic_cutout(
        detector_id=1,
        wavelength_um=0.95,
        flux_uJy=1500.0,
        cutout_size=25,
        background_level_mjy_sr=1.2,
        noise_sigma_mjy_sr=0.01,
        source_offset_pix=(0.0, 0.0),
    )
    # Inject high spike in annulus at radius 5.0 (between inner 4.0 and outer 6.0)
    frame_corrupt.data[12, 17] = 800.0
    frame_corrupt.mask[12, 17] |= int(QualityFlag.COSMIC_RAY)
    frame_corrupt.data[17, 12] = np.nan
    frame_corrupt.mask[17, 12] |= int(QualityFlag.BAD_PIXEL)

    meas_corrupt = measure_aperture_photometry(frame_corrupt)

    assert np.isclose(meas_corrupt.background_per_pixel, meas_clean.background_per_pixel, atol=0.05)
    assert np.isclose(meas_corrupt.flux_uJy, meas_clean.flux_uJy, rtol=0.02)


def test_photometry_unavailable_uncertainty():
    """Verify photometry gracefully handles frames with all-NaN uncertainty."""
    frame = create_synthetic_cutout(
        detector_id=1,
        wavelength_um=0.95,
        flux_uJy=2000.0,
        cutout_size=25,
        background_level_mjy_sr=0.5,
        source_offset_pix=(0.0, 0.0),
    )
    frame.uncertainty[:] = np.nan

    meas = measure_aperture_photometry(frame)

    assert np.isfinite(meas.flux_uJy)
    assert np.isnan(meas.flux_err_uJy)
    assert meas.snr == 0.0
    assert bool(meas.quality_flags & int(QualityFlag.CALIBRATION_WARN))
    assert not bool(meas.quality_flags & int(QualityFlag.LOW_SNR)), "Missing uncertainty must not set LOW_SNR"


# =============================================================================
# 3. Stacking Robustness and Edge Cases Tests
# =============================================================================
def test_stacking_one_invalid_epoch():
    """Verify median and weighted-mean stacking cleanly ignore a bad pixel in one epoch."""
    n_frames = 5
    flux = 1000.0
    frames = [
        create_synthetic_cutout(
            detector_id=1,
            wavelength_um=0.95,
            flux_uJy=flux,
            cutout_size=15,
            noise_sigma_mjy_sr=0.01,
            random_seed=200 + i,
        )
        for i in range(n_frames)
    ]

    # Poison pixel (7, 7) in frame 2 with NaN and BAD_PIXEL
    frames[2].data[7, 7] = np.nan
    frames[2].mask[7, 7] |= int(QualityFlag.BAD_PIXEL)

    for method in ("median", "weighted_mean"):
        stacked = stack_frames(frames, method=method)
        assert np.isfinite(stacked.data[7, 7]), f"Method {method} returned non-finite value at pixel (7, 7)"
        assert np.isfinite(stacked.uncertainty[7, 7])
        assert not bool(stacked.mask[7, 7] & int(QualityFlag.BAD_PIXEL))


def test_stacking_nan_uncertainty_resilience():
    """Verify weighted-mean stacking does NOT poison pixel when one epoch has NaN uncertainty."""
    frames = [
        create_synthetic_cutout(detector_id=1, wavelength_um=0.95, flux_uJy=1500.0, cutout_size=15, random_seed=300 + i)
        for i in range(4)
    ]

    # Frame 1 has NaN uncertainty at pixel (5, 5), but valid flux
    frames[1].uncertainty[5, 5] = np.nan

    stacked = stack_frames(frames, method="weighted_mean")

    assert np.isfinite(stacked.data[5, 5])
    assert np.isfinite(stacked.uncertainty[5, 5])
    assert stacked.uncertainty[5, 5] > 0.0


def test_stacking_all_epochs_invalid():
    """Verify pixel is cleanly tagged BAD_PIXEL with NaN when all epochs are bad."""
    frames = [
        create_synthetic_cutout(detector_id=1, wavelength_um=0.95, flux_uJy=1000.0, cutout_size=15, random_seed=400 + i)
        for i in range(3)
    ]

    # Poison pixel (8, 8) across ALL frames
    for f in frames:
        f.data[8, 8] = np.nan
        f.mask[8, 8] |= int(QualityFlag.BAD_PIXEL)

    stacked_med = stack_frames(frames, method="median")
    assert np.isnan(stacked_med.data[8, 8])
    assert np.isnan(stacked_med.uncertainty[8, 8])
    assert bool(stacked_med.mask[8, 8] & int(QualityFlag.BAD_PIXEL))

    stacked_wt = stack_frames(frames, method="weighted_mean")
    assert np.isnan(stacked_wt.data[8, 8])
    assert np.isnan(stacked_wt.uncertainty[8, 8])
    assert bool(stacked_wt.mask[8, 8] & int(QualityFlag.BAD_PIXEL))


def test_stacking_all_uncertainties_unavailable():
    """Verify weighted-mean falls back to unweighted median when uncertainties are unavailable."""
    frames = [
        create_synthetic_cutout(detector_id=1, wavelength_um=0.95, flux_uJy=1200.0, cutout_size=15, random_seed=500 + i)
        for i in range(3)
    ]

    # All frames have NaN uncertainty at (4, 4), but valid flux
    for f in frames:
        f.uncertainty[4, 4] = np.nan

    stacked = stack_frames(frames, method="weighted_mean")

    assert np.isfinite(stacked.data[4, 4])
    assert np.isnan(stacked.uncertainty[4, 4])
    assert bool(stacked.mask[4, 4] & int(QualityFlag.CALIBRATION_WARN))


# =============================================================================
# 4. Wavelength Provenance and Real FITS Integration Tests
# =============================================================================
def test_real_cached_spherex_wavelength_provenance_and_flags():
    """Verify real Level 2 FITS retains mission flags in raw_flags and tracks wavelength provenance."""
    if not REAL_CACHED_FITS.exists():
        pytest.skip(f"Real cached FITS not found at {REAL_CACHED_FITS}")

    frame = load_cutout_from_fits(
        fits_path=REAL_CACHED_FITS,
        target_ra_deg=133.761337,
        target_dec_deg=-7.242345,
        cutout_size=25,
    )

    # 1. Raw flags preservation
    assert frame.raw_flags is not None
    unique_raw = np.unique(frame.raw_flags)
    assert 2097152 in unique_raw, "Expected FLAG_SOURCE (2097152) in raw_flags"

    # 2. Normalized mask must NOT invalidate FLAG_SOURCE catalog objects
    source_locs = (frame.raw_flags == 2097152)
    assert np.all(frame.mask[source_locs] == 0), "FLAG_SOURCE must normalize to GOOD (0) in frame.mask"

    # 3. Non-functional detector pixels (65 = 64 + 1) MUST be flagged BAD_PIXEL in frame.mask
    dead_locs = ((frame.raw_flags & FLAG_NONFUNC) > 0)
    if np.any(dead_locs):
        assert np.all((frame.mask[dead_locs] & int(QualityFlag.BAD_PIXEL)) > 0)

    # 4. Wavelength provenance
    assert frame.additional_metadata.get("wavelength_source") == "EPSF_TABLE"
    assert frame.additional_metadata.get("is_wavelength_measured") is True
    assert np.isclose(frame.wavelength_um, 5.00108, atol=0.01)


def test_mock_fits_wavelength_provenance_header(tmp_path):
    """Verify fallback to FITS_HEADER when EPSF table is absent."""
    w = WCS(naxis=2)
    w.wcs.crpix = [8.0, 8.0]
    w.wcs.cdelt = [-0.0017, 0.0017]
    w.wcs.crval = [120.0, 30.0]
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]

    h0 = fits.PrimaryHDU()
    h0.header["DETECTOR"] = 3
    h0.header["WAVELEN"] = 2.05

    h_img = fits.ImageHDU(data=np.full((16, 16), 1.5, dtype=np.float32), header=w.to_header(), name="IMAGE")
    h_flg = fits.ImageHDU(data=np.zeros((16, 16), dtype=np.int32), name="FLAGS")
    h_var = fits.ImageHDU(data=np.full((16, 16), 0.04, dtype=np.float32), name="VARIANCE")

    fits_file = tmp_path / "header_wl.fits"
    fits.HDUList([h0, h_img, h_flg, h_var]).writeto(str(fits_file), overwrite=True)

    frame = load_cutout_from_fits(fits_file, target_ra_deg=120.0, target_dec_deg=30.0, cutout_size=9)

    assert frame.additional_metadata.get("wavelength_source") == "FITS_HEADER"
    assert frame.additional_metadata.get("is_wavelength_measured") is True
    assert np.isclose(frame.wavelength_um, 2.05, atol=1e-4)


def test_mock_fits_wavelength_provenance_nominal(tmp_path):
    """Verify fallback to NOMINAL_BANDPASS_MIDPOINT when neither EPSF nor header cards exist."""
    w = WCS(naxis=2)
    w.wcs.crpix = [8.0, 8.0]
    w.wcs.cdelt = [-0.0017, 0.0017]
    w.wcs.crval = [120.0, 30.0]
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]

    h0 = fits.PrimaryHDU()
    h0.header["DETECTOR"] = 4  # Band 4 nominal: (2.42 + 3.82) / 2 = 3.12 um

    h_img = fits.ImageHDU(data=np.full((16, 16), 1.5, dtype=np.float32), header=w.to_header(), name="IMAGE")
    h_flg = fits.ImageHDU(data=np.zeros((16, 16), dtype=np.int32), name="FLAGS")
    h_var = fits.ImageHDU(data=np.full((16, 16), 0.04, dtype=np.float32), name="VARIANCE")

    fits_file = tmp_path / "nominal_wl.fits"
    fits.HDUList([h0, h_img, h_flg, h_var]).writeto(str(fits_file), overwrite=True)

    frame = load_cutout_from_fits(fits_file, target_ra_deg=120.0, target_dec_deg=30.0, cutout_size=9)

    assert frame.additional_metadata.get("wavelength_source") == "NOMINAL_BANDPASS_MIDPOINT"
    assert frame.additional_metadata.get("is_wavelength_measured") is False
    assert np.isclose(frame.wavelength_um, 3.12, atol=1e-2)
    assert bool(frame.frame_quality_flags & int(QualityFlag.CALIBRATION_WARN))


# =============================================================================
# 5. Targeted Regression Tests for Confirmed Audit Defects
# =============================================================================
def test_aperture_variance_propagation_quadratic_scaling():
    """
    Verify Fix 1: When partial aperture flux is scaled by c = (n_total / n_valid),
    the aperture variance Var(c * X) must scale as c**2 * Var(X), not c * Var(X).
    """
    cutout_size = 25
    center_xy = (12.0, 12.0)
    aperture_r = 2.5  # 21 pixels inside aperture
    sigma_pix = 0.20  # input pixel uncertainty
    bg_level = 0.5    # flat background (bg_rms == 0 -> var_bg == 0)

    data = np.full((cutout_size, cutout_size), bg_level, dtype=np.float64)
    uncertainty = np.full((cutout_size, cutout_size), sigma_pix, dtype=np.float64)
    mask = np.zeros((cutout_size, cutout_size), dtype=np.int32)

    # Inject source core
    data[12, 12] += 10.0

    # Determine aperture pixel coordinates
    ny, nx = data.shape
    y, x = np.ogrid[:ny, :nx]
    in_aper = (x - center_xy[0]) ** 2 + (y - center_xy[1]) ** 2 <= (aperture_r ** 2)
    aper_coords = np.argwhere(in_aper)
    n_total = len(aper_coords)
    assert n_total == 21

    # Corrupt exactly 3 pixels on the border of the aperture
    for cy, cx in aper_coords[-3:]:
        mask[cy, cx] |= int(QualityFlag.BAD_PIXEL)
        data[cy, cx] = np.nan

    n_valid = n_total - 3  # 18 valid pixels
    scale_c = float(n_total) / float(n_valid)  # 21 / 18 = 7/6

    frame = SPHERExFrame(
        data=data,
        uncertainty=uncertainty,
        mask=mask,
        frame_id="scale_test",
        mjd=60000.0,
        timestamp_utc="2025-01-01T00:00:00",
        detector_id=2,
        band_name="DET2",
        wavelength_um=1.35,
        wavelength_fwhm_um=0.03,
        ra_deg=100.0,
        dec_deg=20.0,
        pixel_scale_arcsec=6.2,
        flux_unit="MJy/sr",
    )

    meas = measure_aperture_photometry(frame, center_xy=center_xy, aperture_radius_pix=aperture_r)

    # Theoretical expectation:
    # Since background is completely flat, bg_rms == 0, so var_bg == 0.
    # The valid pixel sum variance is n_valid * (sigma_pix ** 2).
    # Scaling flux by c multiplies variance by c**2:
    # Var_aper = (scale_c ** 2) * n_valid * (sigma_pix ** 2)
    # sigma_aper = scale_c * sqrt(n_valid) * sigma_pix
    sum_var = n_valid * (sigma_pix ** 2)
    expected_var_raw = (scale_c ** 2) * sum_var
    expected_err_raw = np.sqrt(expected_var_raw)
    unit_scale = frame.pixel_solid_angle_sr * 1e12
    expected_flux_err_uJy = expected_err_raw * unit_scale

    # Old buggy linear scaling would have produced:
    old_var_raw = scale_c * sum_var
    old_err_raw = np.sqrt(old_var_raw)
    old_flux_err_uJy = old_err_raw * unit_scale

    # Verify exact match with quadratic c**2 scaling:
    assert np.isclose(meas.flux_err_uJy, expected_flux_err_uJy, rtol=1e-5)
    # Verify it does NOT equal the old flawed linear error:
    assert not np.isclose(meas.flux_err_uJy, old_flux_err_uJy, rtol=1e-3)
    # The true uncertainty must be strictly larger than the flawed linear estimate:
    assert meas.flux_err_uJy > old_flux_err_uJy


def test_stacked_raw_flags_transient_rejection():
    """
    Verify Fix 2: When an epoch has a transient cosmic ray at pixel (y, x),
    the transient is rejected by the stack and does NOT contaminate stacked.raw_flags.
    Normalizing stacked.raw_flags must NOT evaluate to COSMIC_RAY.
    """
    n_frames = 5
    ny, nx = 15, 15
    target_yx = (7, 7)

    frames = []
    for i in range(n_frames):
        data = np.full((ny, nx), 2.0, dtype=np.float64)
        uncert = np.full((ny, nx), 0.10, dtype=np.float64)
        mask = np.zeros((ny, nx), dtype=np.int32)
        raw_flags = np.full((ny, nx), FLAG_SOURCE, dtype=np.int32)  # All frames have FLAG_SOURCE

        frames.append(
            SPHERExFrame(
                data=data,
                uncertainty=uncert,
                mask=mask,
                frame_id=f"frame_{i}",
                mjd=60000.0 + i,
                timestamp_utc=f"2025-01-0{i+1}T00:00:00",
                detector_id=1,
                band_name="DET1",
                wavelength_um=0.95,
                wavelength_fwhm_um=0.02,
                ra_deg=100.0,
                dec_deg=20.0,
                pixel_scale_arcsec=6.2,
                flux_unit="MJy/sr",
                raw_flags=raw_flags,
            )
        )

    # Inject massive transient cosmic ray spike into Frame 0 at (7, 7)
    frames[0].data[target_yx] = 999.0
    frames[0].mask[target_yx] |= int(QualityFlag.COSMIC_RAY)
    frames[0].raw_flags[target_yx] = FLAG_TRANSIENT  # Has transient flag

    # Stack frames
    stacked = stack_frames(frames, method="weighted_mean")

    # 1. Output flux at (7, 7) must equal clean value (2.0), not contaminated by 999.0
    assert np.isclose(stacked.data[target_yx], 2.0, atol=0.01)

    # 2. Output normalized mask must NOT have COSMIC_RAY
    assert (stacked.mask[target_yx] & int(QualityFlag.COSMIC_RAY)) == 0

    # 3. Output stacked.raw_flags must NOT have FLAG_TRANSIENT
    assert (stacked.raw_flags[target_yx] & FLAG_TRANSIENT) == 0

    # 4. Output stacked.raw_flags MUST preserve FLAG_SOURCE from the contributing clean epochs
    assert (stacked.raw_flags[target_yx] & FLAG_SOURCE) > 0

    # 5. Normalizing the stacked raw flags must NOT produce COSMIC_RAY!
    norm_stacked = normalize_quality_flags(stacked.raw_flags, is_mission_flags=True)
    assert norm_stacked[target_yx] == 0

    # 6. Provenance: all-epochs raw flag bitwise OR is preserved in metadata
    assert (stacked.additional_metadata["all_epochs_raw_flags"][target_yx] & FLAG_TRANSIENT) > 0


def test_distinguish_rejected_photometry_from_low_snr():
    """
    Verify Fix 3: Rejected measurements (due to bad pixels) must NOT be tagged LOW_SNR.
    LOW_SNR is reserved strictly for valid astronomical non-detections or sub-threshold sources.
    """
    # Part A: Rejected Measurement (> 50% bad pixels in aperture)
    corrupt_frame = create_synthetic_cutout(
        detector_id=2,
        wavelength_um=1.35,
        flux_uJy=3000.0,
        cutout_size=25,
        background_level_mjy_sr=1.0,
        noise_sigma_mjy_sr=0.01,
        source_offset_pix=(0.0, 0.0),
    )
    # Corrupt 15 of 21 pixels
    ny, nx = corrupt_frame.shape
    y, x = np.ogrid[:ny, :nx]
    in_aper = (x - 12.0) ** 2 + (y - 12.0) ** 2 <= (2.5 ** 2)
    for cy, cx in np.argwhere(in_aper)[:15]:
        corrupt_frame.mask[cy, cx] |= int(QualityFlag.BAD_PIXEL)
        corrupt_frame.data[cy, cx] = np.nan

    meas_rej = measure_aperture_photometry(corrupt_frame, center_xy=(12.0, 12.0), aperture_radius_pix=2.5)
    assert np.isnan(meas_rej.flux_uJy)
    assert bool(meas_rej.quality_flags & int(QualityFlag.BAD_PIXEL))
    # CRITICAL: Must NOT be flagged LOW_SNR
    assert not bool(meas_rej.quality_flags & int(QualityFlag.LOW_SNR))

    # Downstream light curve
    lc_rej = extract_light_curve([corrupt_frame], target_ra=133.76, target_dec=-7.24, target_name="CorruptTarget")
    assert np.isnan(lc_rej.fluxes_uJy[0])
    assert np.isnan(lc_rej.ab_magnitudes[0])
    assert bool(lc_rej.quality_flags[0] & int(QualityFlag.BAD_PIXEL))
    assert not bool(lc_rej.quality_flags[0] & int(QualityFlag.LOW_SNR))
    assert lc_rej.metadata["valid_epoch_count"] == 0
    assert lc_rej.metadata["rejected_epoch_count"] == 1

    # Downstream spectrum
    spec_rej = extract_spectrum([corrupt_frame], target_ra=133.76, target_dec=-7.24, target_name="CorruptTarget")
    assert np.isnan(spec_rej.fluxes_uJy[0])
    assert bool(spec_rej.quality_flags[0] & int(QualityFlag.BAD_PIXEL))
    assert not bool(spec_rej.quality_flags[0] & int(QualityFlag.LOW_SNR))
    assert spec_rej.metadata["valid_channels"] == 0
    assert spec_rej.metadata["rejected_channels"] == 1

    # Part B: Valid Low-SNR Measurement (faint sub-threshold source)
    faint_frame = create_synthetic_cutout(
        detector_id=1,
        wavelength_um=0.90,
        flux_uJy=0.001,  # Sub-threshold signal
        noise_sigma_mjy_sr=0.05,
        cutout_size=25,
    )
    meas_faint = measure_aperture_photometry(faint_frame)
    assert np.isfinite(meas_faint.flux_uJy)
    assert meas_faint.snr < 3.0
    # Must BE flagged LOW_SNR
    assert bool(meas_faint.quality_flags & int(QualityFlag.LOW_SNR))
    assert not bool(meas_faint.quality_flags & int(QualityFlag.BAD_PIXEL))

    # Downstream light curve
    lc_faint = extract_light_curve([faint_frame], target_ra=133.76, target_dec=-7.24, target_name="FaintTarget")
    assert np.isfinite(lc_faint.fluxes_uJy[0])
    assert bool(lc_faint.quality_flags[0] & int(QualityFlag.LOW_SNR))
    assert not bool(lc_faint.quality_flags[0] & int(QualityFlag.BAD_PIXEL))
    assert lc_faint.metadata["valid_epoch_count"] == 1
    assert lc_faint.metadata["rejected_epoch_count"] == 0
