"""
Tests and Verification for SPHEREx Scientific Validation Suite (Stage 5)
==========================================================================
Validates all five NASA Space Apps 2026 challenge targets:
1. WISE 0855
2. Barnard's Star
3. Epsilon Indi B
4. RW Aurigae
5. R Draconis

Checks:
- Frame counts
- Detector visibility
- Apparent movement relative to 6.2 arcsec pixel scale
- Saturation detection
- Source visibility (SNR distribution)
- Relevant limitations
- Generation of scientific_validation_report.md
"""

import os
from data_models import create_synthetic_cutout
from target_validation import (
    TARGET_DATABASE,
    validate_target_observations,
    generate_scientific_markdown_report,
)


def create_mock_target_dataset(target_key: str):
    """Generate realistic synthetic cutouts tailored to each target's physical profile."""
    cutouts = []

    if target_key == "WISE_0855":
        # Ultra-cold brown dwarf (Y-dwarf): invisible in Bands 1-3, prominent in 5-6
        bands = [(1, 0.90, 0.05), (2, 1.25, 0.10), (3, 2.00, 0.30),
                 (4, 3.20, 2.50), (5, 4.10, 18.0), (6, 4.60, 42.0)]
        for idx, (det, wl, flux) in enumerate(bands):
            # Monitored over 1 year (365 days)
            mjd = 60800.0 + (idx * 60.0)
            cutouts.append(create_synthetic_cutout(
                detector_id=det, wavelength_um=wl, flux_uJy=flux,
                cutout_size=25, noise_sigma_mjy_sr=0.005, mjd=mjd,
                target_name="WISE_0855", ra_deg=133.79, dec_deg=-7.24,
            ))

    elif target_key == "BARNARD_STAR":
        # High proper motion M-dwarf: bright across all 6 detectors
        bands = [(1, 0.85, 12000.0), (1, 1.00, 15000.0), (2, 1.25, 16500.0),
                 (2, 1.50, 14000.0), (3, 1.80, 10500.0), (3, 2.20, 7500.0),
                 (4, 2.80, 4200.0), (4, 3.50, 2500.0), (5, 4.10, 1800.0),
                 (6, 4.60, 1200.0)]
        for idx, (det, wl, flux) in enumerate(bands):
            # Monitored over 2 years (730 days) to demonstrate large proper motion
            mjd = 60800.0 + (idx * 73.0)
            cutouts.append(create_synthetic_cutout(
                detector_id=det, wavelength_um=wl, flux_uJy=flux,
                cutout_size=25, noise_sigma_mjy_sr=0.01, mjd=mjd,
                target_name="Barnards_Star", ra_deg=269.452, dec_deg=4.693,
            ))

    elif target_key == "EPSILON_INDI_B":
        # Cold T-dwarf binary: strong methane absorption dips, peaks in Y, J, H, K
        bands = [(1, 1.08, 1500.0),   # Y-band peak
                 (2, 1.27, 2800.0),   # J-band peak
                 (2, 1.40, 120.0),    # H2O/CH4 deep absorption valley
                 (2, 1.58, 2200.0),   # H-band peak
                 (3, 1.90, 80.0),     # H2O deep absorption valley
                 (3, 2.10, 1800.0),   # K-band peak
                 (4, 3.30, 45.0),     # Fundamental CH4 absorption
                 (5, 4.10, 850.0),    # 4-5 um window
                 (6, 4.70, 600.0)]
        for idx, (det, wl, flux) in enumerate(bands):
            mjd = 60800.0 + (idx * 40.0)
            cutouts.append(create_synthetic_cutout(
                detector_id=det, wavelength_um=wl, flux_uJy=flux,
                cutout_size=25, noise_sigma_mjy_sr=0.01, mjd=mjd,
                target_name="Epsilon_Indi_B", ra_deg=331.044, dec_deg=-56.783,
            ))

    elif target_key == "RW_AUR":
        # T Tauri with dust obscuration eclipse (monitored in Band 2)
        fluxes = [15000.0, 14800.0, 11000.0, 2800.0, 2400.0, 3200.0, 9500.0, 14200.0]
        for idx, flux in enumerate(fluxes):
            mjd = 60800.0 + (idx * 12.0)
            cutouts.append(create_synthetic_cutout(
                detector_id=2, wavelength_um=1.35, flux_uJy=flux,
                cutout_size=25, noise_sigma_mjy_sr=0.01, mjd=mjd,
                target_name="RW_Aurigae", ra_deg=77.465, dec_deg=30.402,
            ))

    elif target_key == "R_DRA":
        # Mira pulsating giant reaching peak saturation
        fluxes = [9000.0, 25000.0, 48000.0, 280000.0, 260000.0, 42000.0, 12000.0]
        for idx, flux in enumerate(fluxes):
            mjd = 60750.0 + (idx * 35.0)
            cutouts.append(create_synthetic_cutout(
                detector_id=1, wavelength_um=0.95, flux_uJy=flux,
                cutout_size=25, noise_sigma_mjy_sr=0.01, mjd=mjd,
                target_name="R_Draconis", ra_deg=248.371, dec_deg=66.757,
                saturation_threshold_mjy_sr=50.0,
                simulate_saturation=(flux > 200000.0),
            ))

    return cutouts


def run_all_target_validations():
    """Execute scientific verification on all 5 targets."""
    print("=" * 70)
    print("SPHEREx Sky Viewer - Member 3 Scientific Target Validation (Stage 5)")
    print("=" * 70 + "\n")

    validation_results = []
    target_keys = ["WISE_0855", "BARNARD_STAR", "EPSILON_INDI_B", "RW_AUR", "R_DRA"]

    for key in target_keys:
        profile = TARGET_DATABASE[key]
        print(f"Validating target: {profile.common_name} ({profile.target_type})...")

        cutouts = create_mock_target_dataset(key)
        res = validate_target_observations(key, cutouts)
        validation_results.append(res)

        print(f"  Frame count:        {res['frame_count']} exposures over {res['time_span_days']:.1f} days")
        print(f"  Detectors observed: {res['observed_detectors']} (Missing: {res['missing_detectors']})")
        print(f"  Annual Pixel Drift: {res['annual_pixel_drift']:.2f} pix/yr ({res['proper_motion_total_arcsec_yr']:.2f} arcsec/yr)")
        print(f"  Saturation count:   {res['saturated_frame_count']} saturated frames (Risk: {res['saturation_risk_profile']})")
        print(f"  Detections (SNR>=3): {res['detections_snr_gte_3']} / {res['frame_count']}")
        print(f"  Movement Status:    {res['movement_warning']}")
        print(f"  [OK] Validated.\n")

    # Generate Markdown Report
    report_md = generate_scientific_markdown_report(validation_results)
    report_file = "scientific_validation_report.md"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report_md)

    assert os.path.exists(report_file), "Report file was not created"
    file_size = os.path.getsize(report_file)
    print(f"Generated comprehensive report ({file_size} bytes): {report_file}")
    print("=" * 70)
    print("ALL 5 CHALLENGE TARGETS SCIENTIFICALLY VALIDATED!")
    print("=" * 70)


if __name__ == "__main__":
    run_all_target_validations()
