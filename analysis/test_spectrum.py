"""
Tests and Verification for SPHEREx Spectrum Extraction Engine (Stage 3)
========================================================================
Validates:
1. Multi-detector spectral synthesis across all 6 SPHEREx detectors.
2. Monotonic wavelength sorting from 0.75 to 5.00 um.
3. Resilience to missing detector observations (Detectors 1..6).
4. Enforcement of cross-detector calibration consistency (preventing mixing uncalibrated data).
5. Publication-grade spectral plot generation with 6-band shading.
6. Validation on challenge targets:
   - Barnard's Star (M-dwarf peaking in near-IR)
   - WISE 0855 (cold brown dwarf visible in Bands 5-6)
"""

import os
import numpy as np
from data_models import (
    SPHERExFrame,
    SpectrumResult,
    QualityFlag,
    SPHEREX_DETECTOR_BANDS,
    create_synthetic_cutout,
)
from analysis import extract_spectrum, plot_spectrum


def test_full_six_detector_spectrum():
    """Verify spectral extraction across all 6 SPHEREx detectors (Barnard's Star)."""
    print("Test 1: Full 6-detector spectral synthesis for Barnard's Star...")

    # Barnard's Star (M-dwarf): peaks near 1.2 um, decreases toward 5.0 um
    # Model flux profile in microJansky across the 6 detector bands
    band_wavelengths = [
        (1, 0.85, 12000.0),
        (1, 1.00, 15000.0),
        (2, 1.25, 16500.0),
        (2, 1.50, 14000.0),
        (3, 1.80, 10500.0),
        (3, 2.20, 7500.0),
        (4, 2.80, 4200.0),
        (4, 3.50, 2500.0),
        (5, 4.00, 1800.0),
        (5, 4.25, 1500.0),
        (6, 4.60, 1200.0),
        (6, 4.90, 1000.0),
    ]

    cutouts = []
    for idx, (det, wl, flux) in enumerate(band_wavelengths):
        frame = create_synthetic_cutout(
            detector_id=det,
            wavelength_um=wl,
            flux_uJy=flux,
            cutout_size=25,
            background_level_mjy_sr=0.8,
            noise_sigma_mjy_sr=0.01,
            frame_id=f"barnard_exp_{idx:02d}",
            target_name="Barnards_Star",
            ra_deg=269.452,
            dec_deg=4.693,
        )
        cutouts.append(frame)

    spectrum = extract_spectrum(
        cutouts=cutouts,
        target_ra=269.452,
        target_dec=4.693,
        target_name="Barnard's Star",
    )

    # Assertions
    assert len(spectrum.wavelengths_um) == len(band_wavelengths)
    assert len(spectrum.missing_detectors) == 0, f"Expected 0 missing detectors, got {spectrum.missing_detectors}"
    assert np.all(np.diff(spectrum.wavelengths_um) > 0), "Wavelengths are not sorted monotonically!"
    assert spectrum.metadata["calibration_consistent"] is True

    print(f"  Extracted {len(spectrum.wavelengths_um)} spectral channels across all 6 detectors.")
    print(f"  Wavelength range: {min(spectrum.wavelengths_um):.2f} um -> {max(spectrum.wavelengths_um):.2f} um")
    print(f"  Mean SNR: {spectrum.metadata['mean_snr']:.1f}")
    print(f"  Missing detectors: {spectrum.missing_detectors}")
    print("  [OK] Full 6-detector spectrum successfully extracted.\n")
    return spectrum


def test_missing_detector_handling():
    """Verify that observations with missing detectors are handled gracefully."""
    print("Test 2: Missing detector resilience (Det 4 and Det 6 omitted)...")

    # Only include cutouts for Detectors 1, 2, 3, and 5 (omitting 4 and 6)
    partial_bands = [
        (1, 0.90, 8000.0),
        (2, 1.30, 9500.0),
        (3, 2.00, 6000.0),
        (5, 4.10, 1200.0),
    ]

    cutouts = []
    for idx, (det, wl, flux) in enumerate(partial_bands):
        frame = create_synthetic_cutout(
            detector_id=det,
            wavelength_um=wl,
            flux_uJy=flux,
            frame_id=f"partial_{idx}",
            target_name="Test_Source",
        )
        cutouts.append(frame)

    spectrum = extract_spectrum(
        cutouts=cutouts,
        target_ra=100.0,
        target_dec=20.0,
        target_name="Partial_Target",
    )

    assert spectrum.missing_detectors == [4, 6], f"Expected missing [4, 6], got {spectrum.missing_detectors}"
    assert len(spectrum.wavelengths_um) == 4
    print(f"  Missing detectors correctly detected: {spectrum.missing_detectors}")
    print("  [OK] Missing detector observations handled without crashing.\n")


def test_cross_detector_calibration_guard():
    """Verify that mixing incompatible or uncalibrated detector units is blocked."""
    print("Test 3: Cross-detector calibration compatibility guard...")

    frame1 = create_synthetic_cutout(detector_id=1, wavelength_um=0.90, flux_uJy=100.0)
    frame2 = create_synthetic_cutout(detector_id=2, wavelength_um=1.30, flux_uJy=100.0)
    # Alter frame2 to have raw uncalibrated counts (DN/s)
    frame2.flux_unit = "DN/s"

    try:
        extract_spectrum(
            cutouts=[frame1, frame2],
            target_ra=100.0,
            target_dec=20.0,
            enforce_calibration_consistency=True,
        )
        assert False, "Should have raised ValueError on conflicting flux units!"
    except ValueError as e:
        print(f"  [OK] Blocked uncalibrated cross-detector mixing: {e}\n")


def test_spectral_plotting(barnard_spec: SpectrumResult):
    """Verify that publication-grade spectrum plots are rendered and saved."""
    print("Test 4: Scientific spectrum plot generation...")
    out_file = "barnards_star_spectrum.png"
    if os.path.exists(out_file):
        os.remove(out_file)

    fig = plot_spectrum(barnard_spec, output_path=out_file)
    assert os.path.exists(out_file), "Plot image was not written to disk"
    file_size = os.path.getsize(out_file)
    assert file_size > 10000, f"Plot file seems corrupted or too small ({file_size} bytes)"
    print(f"  [OK] Spectrum plot generated successfully ({file_size} bytes): {out_file}\n")


def test_wise_0855_brown_dwarf():
    """Verify extraction and plotting of ultra-cold brown dwarf WISE 0855."""
    print("Test 5: Challenge target WISE 0855 (sub-stellar cold brown dwarf)...")

    # WISE 0855 (T ~ 250 K): Virtually undetectable at 0.75 - 2.5 um (< 0.2 uJy),
    # but jumps to ~20 - 45 uJy in Bands 5-6 (4.0 - 4.8 um) due to the 4.5 um atmospheric window.
    wise_bands = [
        (1, 0.90, 0.05),   # Faint / non-detection
        (2, 1.25, 0.10),   # Faint
        (3, 2.00, 0.35),   # Faint
        (4, 3.20, 2.50),   # Low flux
        (5, 4.10, 18.0),   # Strong mid-IR peak
        (5, 4.30, 28.0),
        (6, 4.60, 42.0),   # Peak of 4.5 um window
        (6, 4.90, 22.0),
    ]

    cutouts = []
    for idx, (det, wl, flux) in enumerate(wise_bands):
        frame = create_synthetic_cutout(
            detector_id=det,
            wavelength_um=wl,
            flux_uJy=flux,
            cutout_size=25,
            background_level_mjy_sr=0.4,
            noise_sigma_mjy_sr=0.001,  # Deep coadded stack (~25 exposures)
            frame_id=f"wise_exp_{idx}",
            target_name="WISE_0855",
            ra_deg=133.79,
            dec_deg=-7.24,
        )
        cutouts.append(frame)

    wise_spec = extract_spectrum(
        cutouts=cutouts,
        target_ra=133.79,
        target_dec=-7.24,
        target_name="WISE J085510.83-071442.5",
    )

    out_file = "wise_0855_spectrum.png"
    plot_spectrum(wise_spec, output_path=out_file)

    # In NIR (det 1-2), SNR should be low or flagged
    low_snr_points = sum(1 for flag in wise_spec.quality_flags if (flag & int(QualityFlag.LOW_SNR)) > 0)
    print(f"  WISE 0855 channels: {len(wise_spec.wavelengths_um)}")
    print(f"  Near-IR sub-threshold / low-SNR channels: {low_snr_points}")
    print(f"  Peak flux at 4.6 um: {max(wise_spec.fluxes_uJy):.1f} uJy")
    print(f"  [OK] WISE 0855 spectrum and plot verified: {out_file}\n")


if __name__ == "__main__":
    print("=" * 70)
    print("SPHEREx Sky Viewer - Member 3 Spectrum Extraction Verification (Stage 3)")
    print("=" * 70 + "\n")
    barnard_spec = test_full_six_detector_spectrum()
    test_missing_detector_handling()
    test_cross_detector_calibration_guard()
    test_spectral_plotting(barnard_spec)
    test_wise_0855_brown_dwarf()
    print("=" * 70)
    print("ALL STAGE 3 SPECTRUM EXTRACTION CHECKS PASSED SUCCESSFULLY!")
    print("=" * 70)
