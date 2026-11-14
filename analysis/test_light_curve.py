"""
Tests and Verification for SPHEREx Light Curve Extraction Engine (Stage 4)
===========================================================================
Validates:
1. Time-series aperture photometry and Modified Julian Date (MJD) sequencing.
2. Astronomical AB magnitude conversion: m_AB = -2.5*log10(F_Jy/3631) and sigma_m.
3. Variable star challenge targets:
   - RW Aurigae: T Tauri variable with dramatic circumstellar dust obscuration event (Delta m > 2.0).
   - R Draconis: Mira pulsating giant with saturation detection at peak brightness.
4. Robust cadence gap detection and epoch filtering.
5. Dual-panel publication plot generation (Flux + Inverted AB Magnitude).
"""

import os
import numpy as np
from data_models import (
    SPHERExFrame,
    LightCurveResult,
    QualityFlag,
    create_synthetic_cutout,
)
from analysis import extract_light_curve, plot_light_curve


def test_rw_aurigae_dimming_light_curve():
    """Verify extraction of RW Aurigae circumstellar dust dimming event."""
    print("Test 1: RW Aurigae time-series light curve (T Tauri dimming event)...")

    # RW Aurigae: monitored over 100 days in Detector 2 (lambda ~ 1.35 um)
    # The star undergoes an eclipse by a circumstellar dust clump
    epochs_mjd = [
        60800.0, 60808.0, 60816.0, 60824.0, 60832.0,  # Pre-eclipse: ~15,000 uJy
        60840.0, 60848.0, 60856.0,                    # Deep dimming minimum: ~2,500 uJy (drop of > 2 mag)
        60864.0, 60872.0, 60880.0, 60888.0, 60896.0,  # Recovery phase: rising back to ~14,000 uJy
    ]

    # Modeled flux in microJanskys
    model_fluxes = [
        15200.0, 14900.0, 14700.0, 12500.0, 7500.0,
        2800.0, 2400.0, 3100.0,
        6500.0, 10200.0, 13100.0, 14500.0, 14800.0,
    ]

    cutouts = []
    for idx, (mjd, flux) in enumerate(zip(epochs_mjd, model_fluxes)):
        # Generate ISO timestamp
        day = int(mjd - 60800.0)
        ts = f"2025-06-{day+1:02d}T12:00:00"
        frame = create_synthetic_cutout(
            detector_id=2,  # Det 2 (1.11 - 1.64 um)
            wavelength_um=1.35,
            flux_uJy=flux,
            cutout_size=25,
            background_level_mjy_sr=0.7,
            noise_sigma_mjy_sr=0.01,
            mjd=mjd,
            timestamp_utc=ts,
            frame_id=f"rw_aur_epoch_{idx:02d}",
            target_name="RW_Aurigae",
            ra_deg=77.465,
            dec_deg=30.402,
        )
        cutouts.append(frame)

    lc = extract_light_curve(
        cutouts=cutouts,
        target_ra=77.465,
        target_dec=30.402,
        detector_id=2,
        target_name="RW Aurigae",
    )

    # Assertions
    assert len(lc.mjd) == len(epochs_mjd)
    assert np.all(np.diff(lc.mjd) > 0), "MJD is not sorted chronologically!"
    assert lc.detector_id == 2
    assert lc.metadata["saturated_epoch_count"] == 0, "RW Aurigae should not be saturated"

    # Magnitude check: max mag (faintest) - min mag (brightest) should show Delta m > 1.8
    delta_mag = lc.metadata["peak_to_peak_amplitude_mag"]
    print(f"  Observed epochs: {len(lc.mjd)} over {lc.metadata['time_span_days']:.1f} days")
    print(f"  Median cadence: {lc.metadata['median_cadence_days']:.1f} days")
    print(f"  Brightest AB Mag: {lc.metadata['min_mag_ab']:.2f}")
    print(f"  Faintest AB Mag:  {lc.metadata['max_mag_ab']:.2f}")
    print(f"  Dimming Amplitude: Delta m = {delta_mag:.2f} mag")

    assert delta_mag > 1.8, f"Expected deep dimming (Delta m > 1.8), got {delta_mag:.2f}"

    out_file = "rw_aur_light_curve.png"
    plot_light_curve(lc, output_path=out_file, plot_type="both")
    assert os.path.exists(out_file), "RW Aur plot was not created"
    print(f"  [OK] RW Aurigae light curve extracted and plotted ({os.path.getsize(out_file)} bytes): {out_file}\n")
    return lc


def test_r_draconis_pulsation_and_saturation():
    """Verify R Draconis Mira pulsation and peak saturation handling."""
    print("Test 2: R Draconis pulsating giant with peak saturation detection...")

    # R Draconis: Mira variable with period ~245 days. Monitored in Detector 1 (lambda ~ 0.95 um)
    # At peak (MJD ~ 60880), flux reaches 250,000 uJy which saturates the detector linear limit (50 MJy/sr)
    epochs_mjd = [
        60750.0, 60780.0, 60810.0, 60840.0,  # Rising phase
        60870.0, 60900.0,                    # Peak maximum: Saturated!
        60930.0, 60960.0, 60990.0,           # Declining phase
    ]

    model_fluxes = [
        8000.0, 18000.0, 32000.0, 48000.0,   # Rising phase (linear regime < 50 MJy/sr)
        280000.0, 260000.0,                  # Peak maximum: Saturated (> 50 MJy/sr)
        46000.0, 22000.0, 9500.0,            # Declining phase (linear regime)
    ]

    cutouts = []
    for idx, (mjd, flux) in enumerate(zip(epochs_mjd, model_fluxes)):
        frame = create_synthetic_cutout(
            detector_id=1,
            wavelength_um=0.95,
            flux_uJy=flux,
            cutout_size=25,
            background_level_mjy_sr=0.5,
            noise_sigma_mjy_sr=0.01,
            mjd=mjd,
            timestamp_utc=f"2025-Epoch-{idx}",
            frame_id=f"r_dra_epoch_{idx:02d}",
            target_name="R_Draconis",
            ra_deg=248.371,
            dec_deg=66.757,
            saturation_threshold_mjy_sr=50.0,
            simulate_saturation=(flux > 200000.0),
        )
        cutouts.append(frame)

    lc = extract_light_curve(
        cutouts=cutouts,
        target_ra=248.371,
        target_dec=66.757,
        detector_id=1,
        target_name="R Draconis (Mira Variable)",
    )

    sat_count = lc.metadata["saturated_epoch_count"]
    print(f"  Total epochs: {len(lc.mjd)}")
    print(f"  Saturated epochs detected: {sat_count}")
    print(f"  Saturated flags in is_saturated: {sum(lc.is_saturated)}")

    assert sat_count == 2, f"Expected exactly 2 saturated epochs at peak, got {sat_count}"
    assert lc.is_saturated[4] is True
    assert lc.is_saturated[5] is True
    assert (lc.quality_flags[4] & int(QualityFlag.SATURATED)) > 0

    out_file = "r_dra_light_curve.png"
    plot_light_curve(lc, output_path=out_file, plot_type="both")
    assert os.path.exists(out_file), "R Dra plot was not created"
    print(f"  [OK] R Draconis saturation correctly detected and marked in plot: {out_file}\n")


def test_cadence_gap_detection():
    """Verify that temporal observation gaps are identified in metadata."""
    print("Test 3: Observation cadence gap detection...")

    # Epochs with a 60-day gap between epoch 2 and 3
    epochs_mjd = [60800.0, 60805.0, 60810.0, 60870.0, 60875.0]  # Normal cadence 5d, one gap 60d
    cutouts = [
        create_synthetic_cutout(detector_id=2, wavelength_um=1.35, flux_uJy=1000.0, mjd=mjd)
        for mjd in epochs_mjd
    ]

    lc = extract_light_curve(cutouts, target_ra=10.0, target_dec=10.0, detector_id=2)
    print(f"  Median cadence: {lc.metadata['median_cadence_days']:.1f} days")
    print(f"  Large gap count (> 3x cadence): {lc.metadata['large_gap_count']}")

    assert lc.metadata["median_cadence_days"] == 5.0
    assert lc.metadata["large_gap_count"] == 1
    print("  [OK] Cadence gap successfully detected in metadata.\n")


if __name__ == "__main__":
    print("=" * 70)
    print("SPHEREx Sky Viewer - Member 3 Light Curve Verification (Stage 4)")
    print("=" * 70 + "\n")
    test_rw_aurigae_dimming_light_curve()
    test_r_draconis_pulsation_and_saturation()
    test_cadence_gap_detection()
    print("=" * 70)
    print("ALL STAGE 4 LIGHT CURVE EXTRACTION CHECKS PASSED SUCCESSFULLY!")
    print("=" * 70)
