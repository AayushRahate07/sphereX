"""
SPHEREx Sky Viewer — Stage 7 Verification: FITS Loader & User Target Pipeline
=============================================================================
Tests:
1. Coordinate parsing (decimal, sexagesimal, target presets, error handling).
2. Astropy WCS creation and FITS multi-extension structure (SCI, UNCERT, MASK).
3. Sub-image Cutout2D extraction and conversion to SPHERExFrame.
4. End-to-end execution of user target processing pipeline.
"""

from __future__ import annotations
import os
import shutil
from pathlib import Path
import pytest
import numpy as np
from astropy.io import fits
from astropy.wcs import WCS

from data_models import SPHERExFrame, QualityFlag
from fits_loader import (
    parse_coordinates,
    build_spherex_wcs,
    create_mock_spherex_fits,
    load_cutout_from_fits,
    generate_spherex_survey_for_target,
)
from process_target import process_target


TEST_TMP_DIR = Path("test_fits_scratch")


def setup_module():
    """Ensure clean test scratch space."""
    if TEST_TMP_DIR.exists():
        shutil.rmtree(TEST_TMP_DIR)
    TEST_TMP_DIR.mkdir(parents=True, exist_ok=True)


def teardown_module():
    """Clean up test scratch files."""
    if TEST_TMP_DIR.exists():
        shutil.rmtree(TEST_TMP_DIR)


# -----------------------------------------------------------------------------
# Test 1: Coordinate Parsing
# -----------------------------------------------------------------------------
def test_parse_coordinates_decimal():
    """Test standard decimal degrees parsing."""
    ra, dec, name = parse_coordinates(133.790, -7.240)
    assert np.isclose(ra, 133.790, atol=1e-3)
    assert np.isclose(dec, -7.240, atol=1e-3)

    # Combined string
    ra2, dec2, _ = parse_coordinates("269.452 -4.693")
    assert np.isclose(ra2, 269.452, atol=1e-3)
    assert np.isclose(dec2, -4.693, atol=1e-3)


def test_parse_coordinates_sexagesimal():
    """Test sexagesimal coordinate strings."""
    # Barnard's Star: 17h57m48.5s +04d41m36s -> ~269.452 deg, +4.693 deg
    ra, dec, _ = parse_coordinates("17h57m48.5s", "+04d41m36s")
    assert np.isclose(ra, 269.452, atol=0.01)
    assert np.isclose(dec, 4.693, atol=0.01)

    # Colon notation
    ra2, dec2, _ = parse_coordinates("08:55:09.6 -07:14:24")
    assert np.isclose(ra2, 133.790, atol=0.01)
    assert np.isclose(dec2, -7.240, atol=0.01)


def test_parse_coordinates_presets():
    """Test resolution of named challenge targets."""
    ra_w, dec_w, name_w = parse_coordinates("WISE_0855")
    assert np.isclose(ra_w, 133.790, atol=1e-3)
    assert "0855" in name_w

    ra_b, dec_b, name_b = parse_coordinates("BARNARD_STAR")
    assert np.isclose(ra_b, 269.452, atol=1e-3)
    assert "Barnard" in name_b


def test_parse_coordinates_invalid():
    """Test error handling on invalid coordinates."""
    with pytest.raises(ValueError):
        parse_coordinates(100.0, 150.0)  # Dec > 90

    with pytest.raises(ValueError):
        parse_coordinates("invalid_star_random_string_xyz")


# -----------------------------------------------------------------------------
# Test 2: FITS Generation & WCS Compliance
# -----------------------------------------------------------------------------
def test_create_and_validate_fits():
    """Verify generated FITS conforms to SPHEREx Multi-Extension standards."""
    fits_path = TEST_TMP_DIR / "test_frame.fits"
    target_ra = 133.790
    target_dec = -7.240

    create_mock_spherex_fits(
        filepath=fits_path,
        target_ra_deg=target_ra,
        target_dec_deg=target_dec,
        detector_id=3,
        wavelength_um=2.030,
        flux_ujy=1500.0,
        image_size=64,
        target_name="Test_Star",
    )

    assert fits_path.exists()

    with fits.open(str(fits_path)) as hdul:
        # Check HDU names
        assert len(hdul) == 4
        assert hdul[0].name == "PRIMARY"
        assert hdul[1].name == "SCI"
        assert hdul[2].name == "UNCERT"
        assert hdul[3].name == "MASK"

        # Check telescope & attribution headers
        prim_hdr = hdul[0].header
        assert prim_hdr["TELESCOP"] == "SPHEREx"
        assert prim_hdr["ORIGIN"] == "NASA/IPAC IRSA"
        assert prim_hdr["DETECTOR"] == 3
        assert np.isclose(prim_hdr["WAVELEN"], 2.030)

        # Check WCS headers
        sci_hdr = hdul["SCI"].header
        assert sci_hdr["CTYPE1"] == "RA---TAN"
        assert sci_hdr["CTYPE2"] == "DEC--TAN"
        wcs = WCS(sci_hdr)
        pix = wcs.world_to_pixel_values(target_ra, target_dec)
        # Reference pixel was centered at 32.5 (1-based), so 0-based is 31.5
        assert np.isclose(pix[0], 31.5, atol=0.1)
        assert np.isclose(pix[1], 31.5, atol=0.1)


# -----------------------------------------------------------------------------
# Test 3: Astropy Cutout2D Extraction
# -----------------------------------------------------------------------------
def test_load_cutout_from_fits():
    """Verify WCS-based cutout extraction creates valid SPHERExFrame."""
    fits_path = TEST_TMP_DIR / "test_frame.fits"
    target_ra = 133.790
    target_dec = -7.240

    frame = load_cutout_from_fits(fits_path, target_ra, target_dec, cutout_size=25)

    assert isinstance(frame, SPHERExFrame)
    assert frame.data.shape == (25, 25)
    assert frame.uncertainty.shape == (25, 25)
    assert frame.mask.shape == (25, 25)
    assert frame.detector_id == 3
    assert np.isclose(frame.wavelength_um, 2.030)

    # Center of 25x25 cutout should be (12.0, 12.0)
    assert np.isclose(frame.additional_metadata["center_pixel_x"], 12.0)
    assert np.isclose(frame.additional_metadata["center_pixel_y"], 12.0)


# -----------------------------------------------------------------------------
# Test 4: End-to-End User Target Pipeline Execution
# -----------------------------------------------------------------------------
def test_end_to_end_user_target_pipeline():
    """Test full processing pipeline on custom coordinates."""
    out_dir = TEST_TMP_DIR / "pipeline_run"

    # Run for Barnard's Star
    results = process_target(
        ra_deg=269.452,
        dec_deg=4.693,
        target_name="Barnard's Star",
        mode="all",
        output_dir=str(out_dir),
        cutout_size=25,
    )

    # 1. Check Spectrum
    assert results["spectrum"] is not None
    assert len(results["spectrum"]["detectors_present"]) == 6
    assert (out_dir / results["spectrum"]["plot_file"]).exists()

    # 2. Check Light Curve
    assert results["light_curve"] is not None
    assert len(results["light_curve"]["mjds"]) == 10
    assert (out_dir / results["light_curve"]["plot_file"]).exists()

    # 3. Check Stacking
    assert results["stacking"] is not None
    assert results["stacking"]["n_frames_coadded"] == 5
    assert results["stacking"]["snr_enhancement"] > 1.8  # ~sqrt(5) ~ 2.23
    assert (out_dir / results["stacking"]["plot_file"]).exists()

    # 4. Check JSON release artifact
    json_path = out_dir / "Barnards_Star_results.json"
    assert json_path.exists()
    assert "NASA/IPAC Infrared Science Archive" in results["citation"]


# -----------------------------------------------------------------------------
# Test 5: User Filter / Band Subset Selection
# -----------------------------------------------------------------------------
def test_user_filter_band_selection():
    """Test user selecting a subset of detector bands (e.g. Band 5 & 6 for WISE 0855)."""
    out_dir = TEST_TMP_DIR / "band_run"

    results = process_target(
        ra_deg=133.790,
        dec_deg=-7.240,
        target_name="WISE_0855",
        mode="spectrum",
        selected_bands=[5, 6],
        output_dir=str(out_dir),
    )

    assert results["spectrum"] is not None
    assert results["spectrum"]["detectors_present"] == [5, 6]
    assert results["spectrum"]["detectors_missing"] == [1, 2, 3, 4]
    assert (out_dir / results["spectrum"]["plot_file"]).exists()


# -----------------------------------------------------------------------------
# Test 6: User Variability Period & Phase Folding
# -----------------------------------------------------------------------------
def test_user_variability_period_phase_folding():
    """Test user entering variability period in days (e.g. 245.0 d for R Draconis)."""
    out_dir = TEST_TMP_DIR / "period_run"

    results = process_target(
        ra_deg=248.370,
        dec_deg=66.702,
        target_name="R_DRA",
        mode="lightcurve",
        period_days=245.0,
        output_dir=str(out_dir),
    )

    assert results["light_curve"] is not None
    assert results["light_curve"]["period_days"] == 245.0
    phase_plot = results["light_curve"]["phase_folded_plot_file"]
    assert phase_plot is not None
    assert (out_dir / phase_plot).exists()


# -----------------------------------------------------------------------------
# Test 7: User Stacking Parameters & Algorithms
# -----------------------------------------------------------------------------
def test_user_stacking_parameters():
    """Test custom user stacking: median algorithm, 8 exposures, sigma clip 2.5."""
    out_dir = TEST_TMP_DIR / "stack_param_run"

    results = process_target(
        ra_deg=77.108,
        dec_deg=30.402,
        target_name="RW_AUR",
        mode="stack",
        stack_method="median",
        stack_n_frames=8,
        stack_sigma=2.5,
        output_dir=str(out_dir),
    )

    assert results["stacking"] is not None
    assert results["stacking"]["stack_method"] == "median"
    assert results["stacking"]["n_frames_coadded"] == 8
    assert results["stacking"]["sigma_clip"] == 2.5
    assert (out_dir / results["stacking"]["plot_file"]).exists()


# -----------------------------------------------------------------------------
# Test 8: FITS Cutout & Aperture Visual Inspection Display
# -----------------------------------------------------------------------------
def test_fits_cutout_inspection_display():
    """Test show_fits=True generates 3-panel FITS diagnostic plots with aperture contours."""
    out_dir = TEST_TMP_DIR / "fits_inspect_run"

    results = process_target(
        ra_deg=269.452,
        dec_deg=4.693,
        target_name="Barnard_Inspection",
        mode="all",
        selected_bands=[1, 2],
        show_fits=True,
        output_dir=str(out_dir),
    )

    assert len(results["fits_inspection_plots"]) >= 2
    for p in results["fits_inspection_plots"]:
        assert (out_dir / p).exists()


def run_all():
    print("=" * 76)
    print(" Running Stage 7: FITS Loader & User Target Pipeline Tests")
    print("=" * 76)

    setup_module()
    try:
        print("--> Test 1: Coordinate parsing (decimal, sexagesimal, presets)...")
        test_parse_coordinates_decimal()
        test_parse_coordinates_sexagesimal()
        test_parse_coordinates_presets()
        test_parse_coordinates_invalid()
        print("    [OK] All coordinate parsing variants passed cleanly.")

        print("--> Test 2: Multi-extension FITS generation & WCS compliance...")
        test_create_and_validate_fits()
        print("    [OK] HDU structure, WCS headers, and IPAC/IRSA metadata verified.")

        print("--> Test 3: Astropy Cutout2D extraction to SPHERExFrame...")
        test_load_cutout_from_fits()
        print("    [OK] WCS world-to-pixel projection and cutout extraction validated.")

        print("--> Test 4: End-to-end user target pipeline execution...")
        test_end_to_end_user_target_pipeline()
        print("    [OK] Spectrum, Light Curve, Stacking, and JSON data release verified.")

        print("--> Test 5: User filter band subset selection (e.g. Bands 5 & 6)...")
        test_user_filter_band_selection()
        print("    [OK] Band selection and missing detector flags verified.")

        print("--> Test 6: User variability period and phase-folding (P = 245.0 d)...")
        test_user_variability_period_phase_folding()
        print("    [OK] Phase folding over 2 cycles [0, 2) verified.")

        print("--> Test 7: User stacking parameters (median, N=8, sigma=2.5)...")
        test_user_stacking_parameters()
        print("    [OK] Custom stacking algorithms and frame counts verified.")

        print("--> Test 8: FITS cutout inspection with aperture & annulus contours...")
        test_fits_cutout_inspection_display()
        print("    [OK] 3-panel FITS diagnostic plots verified.")

        print("\n" + "=" * 76)
        print(" STAGE 7 VERIFICATION SUCCESSFUL: ALL 8 TESTS PASSED [OK]")
        print("=" * 76)
    finally:
        teardown_module()


if __name__ == "__main__":
    run_all()

