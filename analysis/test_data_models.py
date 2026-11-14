"""
Tests and Verification for SPHEREx Data Models & Interfaces (Stage 1)
=====================================================================
Run this script to verify:
1. SPHERExFrame validation rules (shape consistency, detector ranges, wavelengths).
2. Synthetic cutout generation across all 6 SPHEREx detectors.
3. SpectrumResult and LightCurveResult data integrity and JSON export.
"""

import json
import numpy as np
from data_models import (
    SPHERExFrame,
    SpectrumResult,
    LightCurveResult,
    QualityFlag,
    SPHEREX_DETECTOR_BANDS,
    create_synthetic_cutout,
)


def test_frame_valid_creation():
    """Verify that a properly constructed SPHERExFrame passes validation."""
    print("Test 1: Valid SPHERExFrame creation across all 6 detectors...")
    wavelengths = {1: 0.95, 2: 1.35, 3: 2.05, 4: 3.10, 5: 4.10, 6: 4.70}
    for det_id, wl in wavelengths.items():
        frame = create_synthetic_cutout(
            detector_id=det_id,
            wavelength_um=wl,
            flux_uJy=150.0,
            frame_id=f"frame_det_{det_id}",
            target_name="Barnard_Star",
            ra_deg=269.452,
            dec_deg=4.693,
        )
        assert frame.shape == (21, 21), f"Expected (21, 21), got {frame.shape}"
        assert frame.detector_id == det_id
        assert frame.pixel_solid_angle_sr > 0.0
        print(f"  [OK] Detector {det_id} (lambda = {wl:.2f} um) OK. Solid angle = {frame.pixel_solid_angle_sr:.3e} sr")
    print("PASS: Valid frame creation verified.\n")


def test_frame_validation_guards():
    """Verify that SPHERExFrame guards against corrupted or invalid input from Member 2."""
    print("Test 2: Validation guards (mismatched shapes, bad detector, wrong wavelength)...")

    # A. Mismatched shape between data and uncertainty
    try:
        SPHERExFrame(
            data=np.zeros((15, 15)),
            uncertainty=np.zeros((15, 16)),  # Wrong shape
            mask=np.zeros((15, 15), dtype=np.uint16),
            frame_id="err_1",
            mjd=60000.0,
            timestamp_utc="2025-01-01T00:00:00",
            detector_id=1,
            band_name="DET1",
            wavelength_um=0.90,
            wavelength_fwhm_um=0.02,
            ra_deg=100.0,
            dec_deg=20.0,
        )
        assert False, "Should have raised ValueError on shape mismatch"
    except ValueError as e:
        print(f"  [OK] Caught shape mismatch: {e}")

    # B. Invalid detector ID (SPHEREx only has 1..6)
    try:
        SPHERExFrame(
            data=np.zeros((15, 15)),
            uncertainty=np.zeros((15, 15)),
            mask=np.zeros((15, 15), dtype=np.uint16),
            frame_id="err_2",
            mjd=60000.0,
            timestamp_utc="2025-01-01T00:00:00",
            detector_id=7,  # Invalid
            band_name="DET7",
            wavelength_um=0.90,
            wavelength_fwhm_um=0.02,
            ra_deg=100.0,
            dec_deg=20.0,
        )
        assert False, "Should have raised ValueError on invalid detector_id"
    except ValueError as e:
        print(f"  [OK] Caught invalid detector ID: {e}")

    # C. Wavelength incompatible with detector bandpass
    try:
        SPHERExFrame(
            data=np.zeros((15, 15)),
            uncertainty=np.zeros((15, 15)),
            mask=np.zeros((15, 15), dtype=np.uint16),
            frame_id="err_3",
            mjd=60000.0,
            timestamp_utc="2025-01-01T00:00:00",
            detector_id=1,  # Det 1 is 0.75 - 1.11 um
            band_name="DET1",
            wavelength_um=4.50,  # 4.5 um belongs to Det 6!
            wavelength_fwhm_um=0.02,
            ra_deg=100.0,
            dec_deg=20.0,
        )
        assert False, "Should have raised ValueError on incompatible wavelength"
    except ValueError as e:
        print(f"  [OK] Caught incompatible wavelength: {e}")

    print("PASS: All validation guards verified.\n")


def test_saturation_and_quality_flags():
    """Verify that bright sources trigger saturation flags correctly."""
    print("Test 3: Saturation detection and bitwise flag handling...")
    # Generate an extremely bright source exceeding linear threshold (50 MJy/sr)
    bright_frame = create_synthetic_cutout(
        detector_id=1,
        wavelength_um=0.90,
        flux_uJy=500000.0,  # Huge flux
        saturation_threshold_mjy_sr=50.0,
        simulate_saturation=True,
    )
    sat_pixels = np.sum((bright_frame.mask & QualityFlag.SATURATED) > 0)
    assert sat_pixels > 0, "Expected saturated pixels in mask"
    print(f"  [OK] Peak pixel value capped at {np.max(bright_frame.data):.1f} MJy/sr")
    print(f"  [OK] Found {sat_pixels} pixels flagged as SATURATED in the mask.")
    print("PASS: Saturation handling verified.\n")


def test_spectrum_and_lightcurve_json_export():
    """Verify that results serialize cleanly to JSON for Member 1 (Frontend)."""
    print("Test 4: Structured result serialization for Web Frontend...")

    # Spectrum result sample
    spec = SpectrumResult(
        target_name="WISE_0855",
        ra_deg=133.79,
        dec_deg=-7.24,
        wavelengths_um=[0.95, 1.35, 2.05, 3.10, 4.10, 4.70],
        fluxes_uJy=[0.05, 0.12, 0.45, 2.10, 18.5, 42.0],
        flux_errors_uJy=[0.08, 0.09, 0.11, 0.25, 0.80, 1.20],
        detectors=[1, 2, 3, 4, 5, 6],
        snr=[0.6, 1.3, 4.1, 8.4, 23.1, 35.0],
        quality_flags=[QualityFlag.LOW_SNR, QualityFlag.LOW_SNR, QualityFlag.GOOD, QualityFlag.GOOD, QualityFlag.GOOD, QualityFlag.GOOD],
        missing_detectors=[],
        aperture_radius_pix=2.5,
        annulus_radii_pix=(4.0, 6.0),
        metadata={"note": "Faint in NIR, prominent in MIR (Band 5-6)"},
    )
    spec_json = json.dumps(spec.to_dict(), indent=2)
    assert "WISE_0855" in spec_json
    assert "wavelengths_um" in spec_json
    print("  [OK] SpectrumResult exported to valid JSON successfully.")

    # Light curve result sample (RW Aurigae)
    lc = LightCurveResult(
        target_name="RW_Aur",
        ra_deg=77.465,
        dec_deg=30.402,
        detector_id=2,
        central_wavelength_um=1.35,
        mjd=[60800.0, 60810.0, 60820.0, 60830.0],
        timestamps_utc=[
            "2025-06-01T12:00:00",
            "2025-06-11T12:00:00",
            "2025-06-21T12:00:00",
            "2025-07-01T12:00:00",
        ],
        fluxes_uJy=[12500.0, 11800.0, 4200.0, 9500.0],  # Dimming event at epoch 3!
        flux_errors_uJy=[150.0, 140.0, 80.0, 120.0],
        ab_magnitudes=[13.66, 13.72, 14.84, 13.95],
        ab_mag_errors=[0.013, 0.013, 0.021, 0.014],
        is_saturated=[False, False, False, False],
        quality_flags=[QualityFlag.GOOD, QualityFlag.GOOD, QualityFlag.GOOD, QualityFlag.GOOD],
        aperture_radius_pix=2.5,
        annulus_radii_pix=(4.0, 6.0),
        metadata={"target_type": "T Tauri variable with circumstellar dust extinction"},
    )
    lc_json = json.dumps(lc.to_dict(), indent=2)
    assert "RW_Aur" in lc_json
    assert "ab_magnitudes" in lc_json
    print("  [OK] LightCurveResult exported to valid JSON successfully.")
    print("PASS: Serialization verified.\n")


if __name__ == "__main__":
    print("=" * 70)
    print("SPHEREx Sky Viewer - Member 3 Model & Interface Verification")
    print("=" * 70 + "\n")
    test_frame_valid_creation()
    test_frame_validation_guards()
    test_saturation_and_quality_flags()
    test_spectrum_and_lightcurve_json_export()
    print("=" * 70)
    print("ALL STAGE 1 CHECKS PASSED SUCCESSFULLY!")
    print("=" * 70)
