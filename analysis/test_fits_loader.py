"""
SPHEREx Sky Viewer — Unit Tests for FITS Loader & Astropy WCS Engine
====================================================================
Tests for analysis/fits_loader.py:
1. Real cached SPHEREx Level 2 FITS loading (IMAGE, FLAGS, VARIANCE).
2. Variance-to-uncertainty (sigma = sqrt(variance)) propagation.
3. Negative, NaN, and Inf variance handling with QualityFlag.BAD_PIXEL.
4. Non-finite science flux handling with zero-filling and BAD_PIXEL.
5. Partial / out-of-bounds cutout extraction with EDGE_ARTIFACT and BAD_PIXEL.
6. Backward compatibility with legacy/mock FITS (SCI, UNCERT, MASK).
7. Error handling: missing files, out-of-bounds coordinates, missing science HDUs.
8. Fallback handling when variance HDU is missing.
9. Coordinate parsing: decimal, sexagesimal, target presets, and error handling.
"""

from __future__ import annotations
import os
import shutil
from pathlib import Path
import pytest
import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
import astropy.units as u

import sys
analysis_dir = str(Path(__file__).parent.resolve())
if analysis_dir not in sys.path:
    sys.path.insert(0, analysis_dir)

from data_models import (
    SPHERExFrame,
    QualityFlag,
    SPHEREX_DETECTOR_BANDS,
    NOMINAL_PIXEL_SCALE_ARCSEC,
)
from fits_loader import (
    load_cutout_from_fits,
    create_mock_spherex_fits,
    parse_coordinates,
    build_spherex_wcs,
)

REAL_CACHED_FITS = Path(
    "backend/cache/fits/spherex_dr1_2025W19_1B_0116_1_SPHEREx-D6_133.7613_-7.2423_0.0500.fits"
)
TEST_SCRATCH_DIR = Path("analysis/test_fits_loader_scratch")


@pytest.fixture(autouse=True)
def scratch_dir():
    """Ensure clean scratch space for temporary test fixtures."""
    TEST_SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
    yield TEST_SCRATCH_DIR
    if TEST_SCRATCH_DIR.exists():
        shutil.rmtree(TEST_SCRATCH_DIR)


# =============================================================================
# 1. Real SPHEREx Level 2 FITS Observation Loading
# =============================================================================
def test_real_cached_spherex_fits_loading():
    """
    Validate loading of genuine NASA/IPAC IRSA SPHEREx Level 2 MEF observation:
    - HDU 1 'IMAGE' maps to frame.data
    - HDU 2 'FLAGS' maps to frame.mask (preserves full 32-bit bitmask)
    - HDU 3 'VARIANCE' maps to frame.uncertainty via sigma = sqrt(VARIANCE)
    """
    if not REAL_CACHED_FITS.exists():
        pytest.skip(f"Real cached FITS observation not found at {REAL_CACHED_FITS}")

    target_ra = 133.761337
    target_dec = -7.242345
    cutout_size = 25

    frame = load_cutout_from_fits(
        fits_path=REAL_CACHED_FITS,
        target_ra_deg=target_ra,
        target_dec_deg=target_dec,
        cutout_size=cutout_size,
    )

    # Frame structure and types
    assert isinstance(frame, SPHERExFrame)
    assert frame.data.shape == (cutout_size, cutout_size)
    assert frame.uncertainty.shape == (cutout_size, cutout_size)
    assert frame.mask.shape == (cutout_size, cutout_size)
    assert frame.data.dtype == np.float64
    assert frame.uncertainty.dtype == np.float64
    assert np.issubdtype(frame.mask.dtype, np.integer)

    # Science flux is finite and physical
    assert np.all(np.isfinite(frame.data))
    assert 0.0 < np.mean(frame.data) < 10.0

    # Raw flags preserve 32-bit integer quality flags; mask holds normalized QualityFlags
    assert frame.raw_flags is not None
    unique_raw_flags = np.unique(frame.raw_flags)
    assert 2097152 in unique_raw_flags or 524288 in unique_raw_flags
    unique_mask_values = np.unique(frame.mask)
    assert np.issubdtype(frame.mask.dtype, np.integer)

    # Uncertainty verification against raw FITS VARIANCE HDU
    with fits.open(REAL_CACHED_FITS) as hdul:
        raw_variance = hdul["VARIANCE"].data
        # Center of 25x25 cutout corresponds to detector pixel (14, 14) for this pointing
        center_uncert = frame.uncertainty[12, 12]
        expected_sigma = np.sqrt(raw_variance[14, 14])
        assert np.isclose(center_uncert, expected_sigma, rtol=1e-5)
        # All valid variances give positive 1-sigma uncertainty
        assert np.all(frame.uncertainty > 0.0)

    # Instrument metadata
    assert frame.detector_id == 6
    assert np.isclose(frame.wavelength_um, 5.00108, atol=0.01)
    assert frame.flux_unit == "MJy / sr"
    assert np.isclose(frame.mjd, 60800.700028, atol=1e-3)

    # Provenance metadata
    assert frame.additional_metadata["has_variance_hdu"] is True
    assert frame.additional_metadata["sci_hdu_name"] == "IMAGE"
    assert frame.additional_metadata["flags_hdu_name"] == "FLAGS"
    assert frame.additional_metadata["uncert_hdu_name"] == "VARIANCE"


# =============================================================================
# 2. Variance to Uncertainty Conversion and Edge Cases
# =============================================================================
def test_variance_edge_cases(scratch_dir):
    """
    Verify conversion of VARIANCE to 1-sigma error:
    - sigma = sqrt(variance) for finite, non-negative values
    - Negative variance -> np.nan in uncertainty, QualityFlag.BAD_PIXEL in mask
    - NaN variance -> np.nan in uncertainty, QualityFlag.BAD_PIXEL in mask
    - Inf variance -> np.nan in uncertainty, QualityFlag.BAD_PIXEL in mask
    """
    w = WCS(naxis=2)
    w.wcs.crpix = [16.0, 16.0]
    w.wcs.cdelt = [-0.0017, 0.0017]
    w.wcs.crval = [100.0, 20.0]
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]

    h0 = fits.PrimaryHDU()
    h0.header["DETECTOR"] = 1
    h0.header["WAVELEN"] = 0.95

    h_img = fits.ImageHDU(data=np.full((32, 32), 1.5, dtype=np.float32), header=w.to_header(), name="IMAGE")
    h_flg = fits.ImageHDU(data=np.zeros((32, 32), dtype=np.int32), name="FLAGS")

    var_data = np.full((32, 32), 0.04, dtype=np.float32)  # sqrt(0.04) = 0.20
    var_data[15, 15] = -0.09  # Negative variance
    var_data[15, 16] = np.nan  # NaN variance
    var_data[15, 17] = np.inf  # Infinite variance
    h_var = fits.ImageHDU(data=var_data, name="VARIANCE")

    fits_file = scratch_dir / "edge_case_variance.fits"
    fits.HDUList([h0, h_img, h_flg, h_var]).writeto(str(fits_file), overwrite=True)

    frame = load_cutout_from_fits(fits_file, target_ra_deg=100.0, target_dec_deg=20.0, cutout_size=9)

    cy, cx = 4, 4  # Center of 9x9 cutout maps to pixel (15, 15)

    # Valid pixel (0.04 -> 0.20)
    assert np.isclose(frame.uncertainty[cy, cx - 1], 0.20, atol=1e-5)
    assert frame.mask[cy, cx - 1] == 0

    # Negative variance
    assert np.isnan(frame.uncertainty[cy, cx])
    assert bool(frame.mask[cy, cx] & int(QualityFlag.BAD_PIXEL))

    # NaN variance
    assert np.isnan(frame.uncertainty[cy, cx + 1])
    assert bool(frame.mask[cy, cx + 1] & int(QualityFlag.BAD_PIXEL))

    # Inf variance
    assert np.isnan(frame.uncertainty[cy, cx + 2])
    assert bool(frame.mask[cy, cx + 2] & int(QualityFlag.BAD_PIXEL))


# =============================================================================
# 3. Non-Finite Science Flux Handling
# =============================================================================
def test_non_finite_science_flux(scratch_dir):
    """Verify NaN and Inf values in science flux are replaced with 0.0 and flagged BAD_PIXEL."""
    w = WCS(naxis=2)
    w.wcs.crpix = [16.0, 16.0]
    w.wcs.cdelt = [-0.0017, 0.0017]
    w.wcs.crval = [100.0, 20.0]
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]

    h0 = fits.PrimaryHDU()
    h0.header["DETECTOR"] = 2
    h0.header["WAVELEN"] = 1.35

    img_data = np.full((32, 32), 2.0, dtype=np.float32)
    img_data[15, 15] = np.nan
    img_data[15, 16] = np.inf

    h_img = fits.ImageHDU(data=img_data, header=w.to_header(), name="IMAGE")
    h_flg = fits.ImageHDU(data=np.zeros((32, 32), dtype=np.int32), name="FLAGS")
    h_var = fits.ImageHDU(data=np.full((32, 32), 0.01, dtype=np.float32), name="VARIANCE")

    fits_file = scratch_dir / "nan_science_flux.fits"
    fits.HDUList([h0, h_img, h_flg, h_var]).writeto(str(fits_file), overwrite=True)

    frame = load_cutout_from_fits(fits_file, target_ra_deg=100.0, target_dec_deg=20.0, cutout_size=7)

    cy, cx = 3, 3  # Center of 7x7 cutout maps to pixel (15, 15)

    # NaN flux -> preserved as NaN, flagged BAD_PIXEL
    assert np.isnan(frame.data[cy, cx])
    assert bool(frame.mask[cy, cx] & int(QualityFlag.BAD_PIXEL))

    # Inf flux -> normalized to NaN, flagged BAD_PIXEL
    assert np.isnan(frame.data[cy, cx + 1])
    assert bool(frame.mask[cy, cx + 1] & int(QualityFlag.BAD_PIXEL))

    # Finite flux preserved
    assert np.isclose(frame.data[cy, cx - 1], 2.0)


# =============================================================================
# 4. Partial Out-of-Bounds Cutout Extraction
# =============================================================================
def test_partial_out_of_bounds_cutout(scratch_dir):
    """Verify that pixels extending outside detector bounds receive EDGE_ARTIFACT and BAD_PIXEL."""
    w = WCS(naxis=2)
    w.wcs.crpix = [1.0, 1.0]  # Pixel (0, 0) in 0-indexed is at reference
    w.wcs.cdelt = [-0.0017, 0.0017]
    w.wcs.crval = [100.0, 20.0]
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]

    h0 = fits.PrimaryHDU()
    h0.header["DETECTOR"] = 1
    h0.header["WAVELEN"] = 0.95

    h_img = fits.ImageHDU(data=np.ones((20, 20), dtype=np.float32), header=w.to_header(), name="IMAGE")
    h_flg = fits.ImageHDU(data=np.zeros((20, 20), dtype=np.int32), name="FLAGS")
    h_var = fits.ImageHDU(data=np.full((20, 20), 0.09, dtype=np.float32), name="VARIANCE")

    fits_file = scratch_dir / "partial_cutout.fits"
    fits.HDUList([h0, h_img, h_flg, h_var]).writeto(str(fits_file), overwrite=True)

    # Center cutout at (0, 0) detector coordinate: 7x7 cutout extends into negative indices
    frame = load_cutout_from_fits(fits_file, target_ra_deg=100.0, target_dec_deg=20.0, cutout_size=7)

    # Pixel (0, 0) of the cutout is out of bounds
    assert np.isnan(frame.uncertainty[0, 0])
    assert bool(frame.mask[0, 0] & int(QualityFlag.EDGE_ARTIFACT))
    assert bool(frame.mask[0, 0] & int(QualityFlag.BAD_PIXEL))

    # Center pixel (3, 3) is inside bounds
    assert np.isclose(frame.uncertainty[3, 3], 0.30, atol=1e-5)
    assert frame.mask[3, 3] == 0


# =============================================================================
# 5. Legacy Mock FITS Format Backward Compatibility
# =============================================================================
def test_legacy_mock_fits_compatibility(scratch_dir):
    """Verify backwards compatibility with synthetic MEF FITS containing SCI, UNCERT, MASK."""
    fits_file = scratch_dir / "legacy_mock.fits"
    create_mock_spherex_fits(
        filepath=fits_file,
        target_ra_deg=133.79,
        target_dec_deg=-7.24,
        detector_id=3,
        wavelength_um=2.03,
        flux_ujy=1200.0,
        image_size=40,
        target_name="Mock_Target",
    )

    frame = load_cutout_from_fits(fits_file, target_ra_deg=133.79, target_dec_deg=-7.24, cutout_size=21)

    assert isinstance(frame, SPHERExFrame)
    assert frame.data.shape == (21, 21)
    assert frame.uncertainty.shape == (21, 21)
    assert frame.mask.shape == (21, 21)
    assert frame.detector_id == 3
    assert np.isclose(frame.wavelength_um, 2.03)

    # Legacy UNCERT is already 1-sigma uncertainty, NOT variance
    assert frame.additional_metadata["has_variance_hdu"] is False
    assert frame.additional_metadata["sci_hdu_name"] == "SCI"
    assert frame.additional_metadata["flags_hdu_name"] == "MASK"
    assert frame.additional_metadata["uncert_hdu_name"] == "UNCERT"
    assert np.all(frame.uncertainty > 0.0)


# =============================================================================
# 6. Missing Variance HDU Fallback
# =============================================================================
def test_missing_variance_fallback(scratch_dir):
    """Verify that a FITS file lacking a variance or uncertainty HDU sets CALIBRATION_WARN."""
    w = WCS(naxis=2)
    w.wcs.crpix = [10.0, 10.0]
    w.wcs.cdelt = [-0.0017, 0.0017]
    w.wcs.crval = [50.0, 10.0]
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]

    h0 = fits.PrimaryHDU()
    h0.header["DETECTOR"] = 4
    h0.header["WAVELEN"] = 3.12

    h_img = fits.ImageHDU(data=np.ones((20, 20), dtype=np.float32), header=w.to_header(), name="IMAGE")
    h_flg = fits.ImageHDU(data=np.zeros((20, 20), dtype=np.int32), name="FLAGS")

    fits_file = scratch_dir / "no_variance.fits"
    fits.HDUList([h0, h_img, h_flg]).writeto(str(fits_file), overwrite=True)

    frame = load_cutout_from_fits(fits_file, target_ra_deg=50.0, target_dec_deg=10.0, cutout_size=5)

    assert np.all(np.isnan(frame.uncertainty))
    assert np.all((frame.mask & int(QualityFlag.CALIBRATION_WARN)) > 0)


# =============================================================================
# 7. Error Handling: Missing Files, Out of Bounds, Missing HDUs
# =============================================================================
def test_missing_file_error():
    """Verify FileNotFoundError on non-existent file path."""
    with pytest.raises(FileNotFoundError):
        load_cutout_from_fits("non_existent_fits_file_12345.fits", 133.7, -7.2)


def test_target_out_of_bounds_error(scratch_dir):
    """Verify ValueError when target coordinates lie outside detector boundaries."""
    fits_file = scratch_dir / "bounds_test.fits"
    create_mock_spherex_fits(
        filepath=fits_file,
        target_ra_deg=100.0,
        target_dec_deg=0.0,
        detector_id=1,
        wavelength_um=0.95,
        flux_ujy=100.0,
        image_size=32,
    )

    with pytest.raises(ValueError, match="falls outside detector bounds"):
        load_cutout_from_fits(fits_file, target_ra_deg=150.0, target_dec_deg=50.0, cutout_size=25)


def test_missing_science_hdu_error(scratch_dir):
    """Verify ValueError when FITS file has no 2D science image HDU."""
    h0 = fits.PrimaryHDU()
    h1 = fits.ImageHDU(data=np.zeros(10, dtype=np.int32), name="FLAGS")  # 1D only
    fits_file = scratch_dir / "bad_hdu.fits"
    fits.HDUList([h0, h1]).writeto(str(fits_file), overwrite=True)

    with pytest.raises(ValueError, match="Could not find a valid 2D science image HDU"):
        load_cutout_from_fits(fits_file, 100.0, 0.0)


# =============================================================================
# 8. Celestial Coordinate Parsing
# =============================================================================
def test_coordinate_parsing():
    """Test decimal, sexagesimal, preset, and error coordinate parsing."""
    # Decimal
    ra, dec, name = parse_coordinates(133.790, -7.240)
    assert np.isclose(ra, 133.790, atol=1e-3)
    assert np.isclose(dec, -7.240, atol=1e-3)

    # Combined string
    ra2, dec2, _ = parse_coordinates("269.452 -4.693")
    assert np.isclose(ra2, 269.452, atol=1e-3)
    assert np.isclose(dec2, -4.693, atol=1e-3)

    # Sexagesimal
    ra3, dec3, _ = parse_coordinates("17h57m48.5s", "+04d41m36s")
    assert np.isclose(ra3, 269.452, atol=0.01)
    assert np.isclose(dec3, 4.693, atol=0.01)

    # Challenge Presets
    ra_w, dec_w, name_w = parse_coordinates("WISE_0855")
    assert np.isclose(ra_w, 133.790, atol=1e-3)
    assert "0855" in name_w

    ra_b, dec_b, name_b = parse_coordinates("BARNARD_STAR")
    assert np.isclose(ra_b, 269.452, atol=1e-3)
    assert "Barnard" in name_b

    # Invalid
    with pytest.raises(ValueError):
        parse_coordinates(100.0, 150.0)  # Dec > 90

    with pytest.raises(ValueError):
        parse_coordinates("invalid_unknown_target_xyz_999")
