"""
Tests and Verification for SPHEREx Aperture Photometry Engine (Stage 2)
========================================================================
Validates:
1. Photometric recovery accuracy against known injected flux.
2. Background subtraction invariance across different sky brightness levels.
3. Contaminant robustness (sigma-clipping rejects outliers in annulus).
4. Saturation detection and bitwise flag setting.
5. Low SNR detection on sub-threshold faint sources.
6. Edge artifact flagging when aperture/annulus clips cutout borders.
"""

import numpy as np
from data_models import create_synthetic_cutout, QualityFlag
from photometry import measure_aperture_photometry


def test_flux_recovery_against_ground_truth():
    """Verify that measured aperture flux recovers injected synthetic flux accurately."""
    print("Test 1: Photometric flux recovery against ground truth...")
    injected_flux_uJy = 2500.0  # 2500 microJansky source (standard stellar target)
    background_mjy_sr = 1.0     # realistic near-IR sky background
    noise_sigma = 0.005         # 1-sigma pixel noise

    frame = create_synthetic_cutout(
        detector_id=2,  # Band 2 (1.11 - 1.64 um)
        wavelength_um=1.35,
        flux_uJy=injected_flux_uJy,
        cutout_size=25,
        background_level_mjy_sr=background_mjy_sr,
        noise_sigma_mjy_sr=noise_sigma,
        psf_fwhm_pix=1.0,
    )

    meas = measure_aperture_photometry(
        frame=frame,
        aperture_radius_pix=2.5,
        annulus_inner_pix=4.5,
        annulus_outer_pix=7.0,
    )

    percent_error = abs(meas.flux_uJy - injected_flux_uJy) / injected_flux_uJy * 100.0
    flux_diff = abs(meas.flux_uJy - injected_flux_uJy)
    print(f"  Injected Flux:  {injected_flux_uJy:.2f} uJy")
    print(f"  Measured Flux:  {meas.flux_uJy:.2f} +/- {meas.flux_err_uJy:.2f} uJy")
    print(f"  Recovery Error: {percent_error:.2f}% (SNR = {meas.snr:.1f})")
    print(f"  Residual / Uncertainty: {flux_diff / meas.flux_err_uJy:.2f} sigma")

    assert percent_error < 2.0, f"Recovery error {percent_error:.2f}% exceeded 2% tolerance"
    assert flux_diff < 3.0 * meas.flux_err_uJy, "Measured flux is outside 3-sigma error bar"
    assert meas.snr > 50.0, f"Expected high SNR, got {meas.snr}"
    assert (meas.quality_flags & int(QualityFlag.SATURATED)) == 0
    print("  [OK] Ground truth flux recovered with < 2% error and within 3-sigma confidence.\n")


def test_background_invariance():
    """Verify that net source flux is invariant across vastly different background levels."""
    print("Test 2: Background subtraction invariance...")
    true_flux = 300.0
    bg_levels = [0.2, 1.0, 5.0]  # spanning low to high zodiacal background
    measured_fluxes = []

    for bg in bg_levels:
        frame = create_synthetic_cutout(
            detector_id=3,
            wavelength_um=2.00,
            flux_uJy=true_flux,
            cutout_size=25,
            background_level_mjy_sr=bg,
            noise_sigma_mjy_sr=0.01,
        )
        meas = measure_aperture_photometry(frame=frame, aperture_radius_pix=2.5)
        measured_fluxes.append(meas.flux_uJy)
        print(f"  Sky Background: {bg:.1f} MJy/sr -> Measured: {meas.flux_uJy:.2f} uJy (estimated bg: {meas.background_per_pixel:.3f})")

    max_diff = max(measured_fluxes) - min(measured_fluxes)
    diff_percent = (max_diff / true_flux) * 100.0
    print(f"  Max variation across background levels: {diff_percent:.2f}%")
    assert diff_percent < 5.0, f"Background subtraction varied by {diff_percent:.2f}% (> 5%)"
    print("  [OK] Net flux is invariant to background emission.\n")


def test_sigma_clipped_annulus_robustness():
    """Verify that an outlier (simulated cosmic ray in annulus) does NOT bias background subtraction."""
    print("Test 3: Robustness against outliers in background annulus...")
    frame = create_synthetic_cutout(
        detector_id=1,
        wavelength_um=0.95,
        flux_uJy=200.0,
        cutout_size=25,
        background_level_mjy_sr=0.5,
        noise_sigma_mjy_sr=0.02,
    )

    # Clean measurement
    clean_meas = measure_aperture_photometry(frame=frame)

    # Artificially inject a huge cosmic ray spike (100 MJy/sr) in the annulus region
    # Center is at (12, 12). Pixel (12, 17) has radius r = 5.0 (inside annulus 4..6)
    frame.data[12, 17] = 100.0

    robust_meas = measure_aperture_photometry(frame=frame, sigma_clip=3.0)
    diff = abs(robust_meas.flux_uJy - clean_meas.flux_uJy)
    print(f"  Clean Sky Flux:     {clean_meas.flux_uJy:.2f} uJy (bg={clean_meas.background_per_pixel:.3f})")
    print(f"  Contaminated Annulus Flux: {robust_meas.flux_uJy:.2f} uJy (bg={robust_meas.background_per_pixel:.3f})")
    print(f"  Difference due to spike:   {diff:.2f} uJy")

    assert diff < (3.0 * clean_meas.flux_err_uJy), "Outlier spike biased background calculation!"
    print("  [OK] Sigma-clipping successfully rejected the annulus outlier.\n")


def test_saturation_and_low_snr_flags():
    """Verify that saturation and low-SNR flags are properly raised."""
    print("Test 4: Quality flags (saturation and low SNR)...")

    # A. Saturated source
    sat_frame = create_synthetic_cutout(
        detector_id=1,
        wavelength_um=0.90,
        flux_uJy=1000000.0,
        saturation_threshold_mjy_sr=50.0,
        simulate_saturation=True,
    )
    sat_meas = measure_aperture_photometry(sat_frame)
    assert sat_meas.is_saturated is True
    assert (sat_meas.quality_flags & int(QualityFlag.SATURATED)) > 0
    print("  [OK] Saturation correctly detected and flagged.")

    # B. Extremely faint source (sub-threshold)
    faint_frame = create_synthetic_cutout(
        detector_id=1,
        wavelength_um=0.90,
        flux_uJy=0.001,  # Virtually 0 flux
        noise_sigma_mjy_sr=0.05,
    )
    faint_meas = measure_aperture_photometry(faint_frame)
    assert (faint_meas.quality_flags & int(QualityFlag.LOW_SNR)) > 0
    print(f"  [OK] Low SNR correctly detected (SNR = {faint_meas.snr:.2f} < 3.0).")

    # C. Edge truncation
    edge_frame = create_synthetic_cutout(
        detector_id=1,
        wavelength_um=0.90,
        flux_uJy=100.0,
        cutout_size=15,
    )
    # Place aperture right at corner (x=1, y=1)
    edge_meas = measure_aperture_photometry(edge_frame, center_xy=(1.0, 1.0), annulus_outer_pix=6.0)
    assert (edge_meas.quality_flags & int(QualityFlag.EDGE_ARTIFACT)) > 0
    print("  [OK] Edge artifact correctly detected when aperture clips frame boundary.\n")


if __name__ == "__main__":
    print("=" * 70)
    print("SPHEREx Sky Viewer - Member 3 Photometry Engine Verification (Stage 2)")
    print("=" * 70 + "\n")
    test_flux_recovery_against_ground_truth()
    test_background_invariance()
    test_sigma_clipped_annulus_robustness()
    test_saturation_and_low_snr_flags()
    print("=" * 70)
    print("ALL STAGE 2 PHOTOMETRY ENGINE CHECKS PASSED SUCCESSFULLY!")
    print("=" * 70)
