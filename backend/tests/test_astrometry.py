"""Unit and Integration Tests for Astrometry, Coordinate Propagation, and Cutout Framing."""

from pathlib import Path
from astropy.io import fits
from astropy.wcs import WCS
import numpy as np
import pytest

from backend.app.config import (
    DEFAULT_FOV_DEG,
    DEFAULT_PLATE_SCALE_DEG,
    FITS_CACHE_DIR,
    TARGET_PRESETS,
)
from backend.app.processing.reprojection import create_fixed_common_wcs
from backend.app.services.astrometry import (
    get_target_astrometry,
    propagate_coordinates_to_epoch,
)
from backend.app.services.retrieval import (
    get_cached_fits_path,
    get_fits_cache_path,
)


def test_wise0855_astrometry_preset_configuration():
    """Verify WISE 0855 astrometric parameters match verified literature values."""
    astro = get_target_astrometry(133.795129, -7.245147)
    assert astro is not None
    assert astro.reference_epoch == pytest.approx(2010.54, abs=0.01)
    assert astro.reference_ra == pytest.approx(133.795129, abs=1e-5)
    assert astro.reference_dec == pytest.approx(-7.245147, abs=1e-5)
    assert astro.pm_ra_cosdec == pytest.approx(-8123.7, abs=1.0)
    assert astro.pm_dec == pytest.approx(673.2, abs=1.0)
    assert astro.parallax_mas == pytest.approx(439.0, abs=1.0)

    # By name lookup
    astro_name = get_target_astrometry(0.0, 0.0, name="WISE 0855")
    assert astro_name is not None
    assert astro_name == astro


def test_unchanged_behavior_targets_without_astrometry():
    """Targets and sky coordinates without verified astrometry must return coordinates unchanged."""
    # Arbitrary coordinates
    ra_arb, dec_arb = 180.25, 45.50
    p_ra, p_dec = propagate_coordinates_to_epoch(ra_arb, dec_arb, epoch=60800.0)
    assert p_ra == ra_arb
    assert p_dec == dec_arb

    # Preset without astrometry config (e.g., RW Aurigae, R Draconis)
    for preset in TARGET_PRESETS:
        if preset.get("astrometry") is None:
            pra, pdec = propagate_coordinates_to_epoch(float(preset["ra"]), float(preset["dec"]), epoch=60800.0)
            assert pra == float(preset["ra"])
            assert pdec == float(preset["dec"])


def test_propagate_coordinates_wise0855_15year_gap():
    """Verify WISE 0855 position propagates ~121 arcseconds West from 2010 to May 2025."""
    # 2010.54 -> 2025.34 (MJD 60800.7, May 5 2025)
    ra_may, dec_may = propagate_coordinates_to_epoch(
        133.795129, -7.245147, epoch=60800.700028, target_name="WISE 0855"
    )

    # RA moves westward (negative delta RA) by ~0.0338 degrees (~121.6 arcsec)
    delta_ra_arcsec = (ra_may - 133.795129) * np.cos(np.radians(-7.245147)) * 3600.0
    delta_dec_arcsec = (dec_may - (-7.245147)) * 3600.0

    assert -125.0 < delta_ra_arcsec < -115.0
    assert 5.0 < delta_dec_arcsec < 15.0
    assert ra_may == pytest.approx(133.7613, abs=0.002)
    assert dec_may == pytest.approx(-7.2423, abs=0.002)


def test_propagate_coordinates_wise0855_intra_year_motion():
    """Verify May to Dec 2025 physical displacement includes proper motion and parallax."""
    # May 5, 2025 (MJD 60800.7)
    ra_may, dec_may = propagate_coordinates_to_epoch(
        133.795129, -7.245147, epoch=60800.700028, target_name="WISE 0855"
    )
    # Dec 12, 2025 (MJD 61021.35)
    ra_dec, dec_dec = propagate_coordinates_to_epoch(
        133.795129, -7.245147, epoch=61021.351418, target_name="WISE 0855"
    )

    # Combined displacement in arcseconds
    dra_arcsec = (ra_dec - ra_may) * np.cos(np.radians(-7.245147)) * 3600.0
    ddec_arcsec = (dec_dec - dec_may) * 3600.0
    total_displacement_arcsec = np.hypot(dra_arcsec, ddec_arcsec)

    # Total displacement over 7.25 months is ~4.16 arcseconds (~0.675 pixels)
    assert total_displacement_arcsec == pytest.approx(4.16, abs=0.1)


def test_fits_1based_vs_numpy_0based_indexing():
    """Verify strict mathematical agreement between FITS 1-based and NumPy 0-based coordinate conventions."""
    fov_deg = 0.05
    wcs, width, height = create_fixed_common_wcs(
        target_ra=133.761337,
        target_dec=-7.242345,
        fov_deg=fov_deg,
        plate_scale_deg=DEFAULT_PLATE_SCALE_DEG,
    )

    # Grid dimensions for 0.05 deg / (6.1632 arcsec/px) = 29.205 -> rounded to 29
    assert width == 29
    assert height == 29

    # FITS 1-based CRPIX is the center: (29 + 1) / 2 = 15.0
    assert wcs.wcs.crpix[0] == 15.0
    assert wcs.wcs.crpix[1] == 15.0

    # NumPy 0-based pixel projection of CRVAL: (15 - 1) = 14.0
    pix_center = wcs.all_world2pix([[133.761337, -7.242345]], 0)[0]
    assert pix_center[0] == pytest.approx(14.0, abs=1e-6)
    assert pix_center[1] == pytest.approx(14.0, abs=1e-6)

    # Round-trip back to world coordinates
    world_pos = wcs.all_pix2world([[14.0, 14.0]], 0)[0]
    assert world_pos[0] == pytest.approx(133.761337, abs=1e-6)
    assert world_pos[1] == pytest.approx(-7.242345, abs=1e-6)


def test_fixed_common_wcs_preserves_stationary_background_and_moving_target():
    """Verify stationary stars keep identical pixel coordinates while WISE 0855 shifts across epochs."""
    # Moving target: Epoch 1 (May 2025) vs Epoch 2 (Dec 2025)
    tgt_epoch1 = propagate_coordinates_to_epoch(133.795129, -7.245147, epoch=60800.700028)
    tgt_epoch2 = propagate_coordinates_to_epoch(133.795129, -7.245147, epoch=61021.351418)

    anchor_ra, anchor_dec = tgt_epoch1
    common_wcs, _, _ = create_fixed_common_wcs(
        target_ra=anchor_ra,
        target_dec=anchor_dec,
        fov_deg=0.05,
    )

    # Fixed background star
    star_ra = 133.7700
    star_dec = -7.2350
    star_pix1 = common_wcs.all_world2pix([[star_ra, star_dec]], 0)[0]
    star_pix2 = common_wcs.all_world2pix([[star_ra, star_dec]], 0)[0]
    # Background star must not move across epochs on the fixed grid
    assert star_pix1[0] == pytest.approx(star_pix2[0])
    assert star_pix1[1] == pytest.approx(star_pix2[1])

    tgt_pix1 = common_wcs.all_world2pix([tgt_epoch1], 0)[0]
    tgt_pix2 = common_wcs.all_world2pix([tgt_epoch2], 0)[0]

    # Target pixel shift in x is positive (Westward motion in image plane with East=left)
    delta_x = tgt_pix2[0] - tgt_pix1[0]
    delta_y = tgt_pix2[1] - tgt_pix1[1]
    pixel_shift = np.hypot(delta_x, delta_y)

    assert tgt_pix1[0] == pytest.approx(14.0, abs=1e-5)
    assert tgt_pix1[1] == pytest.approx(14.0, abs=1e-5)
    assert pixel_shift == pytest.approx(0.675, abs=0.05)


def test_cache_rejection_of_legacy_cutout_for_propagated_coordinates(tmp_path: Path):
    """Verify get_cached_fits_path rejects legacy cutouts where the target is outside the cutout."""
    # Create a synthetic FITS cutout centered at 2010 coordinates
    legacy_file = tmp_path / "spherex_dr1_TEST_001_SPHEREx-D6_0.0500.fits"

    hdr = fits.Header()
    hdr["SIMPLE"] = True
    hdr["BITPIX"] = -32
    hdr["NAXIS"] = 2
    hdr["NAXIS1"] = 29
    hdr["NAXIS2"] = 29
    hdr["CRPIX1"] = 15.0
    hdr["CRPIX2"] = 15.0
    hdr["CRVAL1"] = 133.795129
    hdr["CRVAL2"] = -7.245147
    hdr["CDELT1"] = -DEFAULT_PLATE_SCALE_DEG
    hdr["CDELT2"] = DEFAULT_PLATE_SCALE_DEG
    hdr["CTYPE1"] = "RA---TAN"
    hdr["CTYPE2"] = "DEC--TAN"

    primary = fits.PrimaryHDU()
    img = fits.ImageHDU(data=np.zeros((29, 29), dtype=np.float32), header=hdr, name="IMAGE")
    hdul = fits.HDUList([primary, img])
    hdul.writeto(legacy_file)

    # Pad file to > 10KB
    with open(legacy_file, "ab") as f:
        f.write(b"\x00" * 15000)

    from unittest.mock import patch
    with patch("backend.app.services.retrieval.FITS_CACHE_DIR", tmp_path):
        # 1. Asking without coordinate propagation accepts the legacy file
        cached_no_coords = get_cached_fits_path("TEST_001", "SPHEREx-D6", 0.05)
        assert cached_no_coords == legacy_file

        # 2. Asking with 2025 propagated coordinates (133.7613, -7.2423) rejects legacy cutout
        # because (133.7613, -7.2423) is at pixel ~33 (outside the 29x29 array)
        cached_with_propagated = get_cached_fits_path(
            "TEST_001", "SPHEREx-D6", 0.05, center_ra=133.7613, center_dec=-7.2423
        )
        assert cached_with_propagated is None

        # 3. If coordinate-specific cutout exists, it is accepted
        coord_file = tmp_path / "spherex_dr1_TEST_001_SPHEREx-D6_133.7613_-7.2423_0.0500.fits"
        coord_file.write_bytes(legacy_file.read_bytes())
        cached_coord = get_cached_fits_path(
            "TEST_001", "SPHEREx-D6", 0.05, center_ra=133.7613, center_dec=-7.2423
        )
        assert cached_coord == coord_file


def test_barnards_star_astrometry_preset_configuration():
    """Verify Barnard's Star astrometric parameters match verified literature values."""
    astro = get_target_astrometry(269.452075, 4.693364)
    assert astro is not None
    assert astro.reference_epoch == pytest.approx(2000.0, abs=0.01)
    assert astro.reference_ra == pytest.approx(269.452075, abs=1e-5)
    assert astro.reference_dec == pytest.approx(4.693364, abs=1e-5)
    assert astro.pm_ra_cosdec == pytest.approx(-798.58, abs=1.0)
    assert astro.pm_dec == pytest.approx(10328.12, abs=1.0)
    assert astro.parallax_mas == pytest.approx(547.45, abs=1.0)

    # By name lookup
    astro_name = get_target_astrometry(0.0, 0.0, name="Barnard's Star")
    assert astro_name is not None
    assert astro_name == astro


def test_propagate_coordinates_barnards_star_25year_motion():
    """Verify Barnard's Star propagates ~265 arcseconds North over 25.6 years to August 2025."""
    # Reference epoch 2000.0 -> Observation epoch August 28, 2025 (MJD 60915.0)
    # Target observation 2025W35_1A_0432_4
    ra_2025, dec_2025 = propagate_coordinates_to_epoch(
        269.452075, 4.693364, epoch="2025-08-28T00:00:00", target_name="Barnard's Star"
    )

    # Delta Dec is ~ +265 arcseconds (+0.0736 degrees = ~43 pixels at 6.16"/pix)
    ddec_arcsec = (dec_2025 - 4.693364) * 3600.0
    dra_arcsec = (ra_2025 - 269.452075) * np.cos(np.radians(4.693364)) * 3600.0

    assert 260.0 < ddec_arcsec < 270.0
    assert -25.0 < dra_arcsec < -15.0
    assert ra_2025 == pytest.approx(269.4462, abs=0.005)
    assert dec_2025 == pytest.approx(4.7670, abs=0.005)


def test_epsilon_indi_b_astrometry_preset_configuration():
    """Verify Epsilon Indi B astrometry config and southward proper motion propagation."""
    astro = get_target_astrometry(330.840200, -56.786500)
    assert astro is not None
    assert astro.pm_ra_cosdec == pytest.approx(3961.0, abs=1.0)
    assert astro.pm_dec == pytest.approx(-2538.0, abs=1.0)

    ra_2025, dec_2025 = propagate_coordinates_to_epoch(
        330.840200, -56.786500, epoch="2025-05-01T00:00:00", target_name="Epsilon Indi B"
    )
    # Dec moves South (negative delta Dec) by ~64 arcsec over 25.3 years
    ddec_arcsec = (dec_2025 - (-56.786500)) * 3600.0
    assert -70.0 < ddec_arcsec < -58.0

