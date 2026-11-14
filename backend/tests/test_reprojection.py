"""Unit tests for Fixed Common-Grid WCS, Axis Orientation, and Reprojection."""

import io
from astropy.io import fits
from astropy.wcs import WCS
import numpy as np
import pytest

from backend.app.config import DEFAULT_PLATE_SCALE_DEG
from backend.app.processing.fits_parser import parse_fits_cutout
from backend.app.processing.reprojection import (
    create_fixed_common_wcs,
    reproject_observation_to_grid,
)


def test_fixed_common_wcs_properties():
    """Verify common-grid dimensions, plate scale, center pixel, and axis orientation."""
    target_ra = 133.795129
    target_dec = -7.245147
    fov_deg = 0.05

    wcs, width, height = create_fixed_common_wcs(target_ra, target_dec, fov_deg)

    # 0.05 / 0.001712 = 29.2056 -> 29 pixels
    assert width == 29
    assert height == 29

    # Center pixel in 1-based FITS is (15.0, 15.0)
    assert wcs.wcs.crpix[0] == pytest.approx(15.0)
    assert wcs.wcs.crpix[1] == pytest.approx(15.0)

    # Center pixel in 0-based NumPy index is (14, 14)
    cx, cy = wcs.all_world2pix(target_ra, target_dec, 0)
    assert cx == pytest.approx(14.0)
    assert cy == pytest.approx(14.0)

    # Axis Orientation: North is Up, East is Left
    # 1) Increasing Dec (North) should INCREASE Y coordinate
    _, north_y = wcs.all_world2pix(target_ra, target_dec + 0.01, 0)
    assert north_y > cy, "North is not aligned with positive Y (+Dec)!"

    # 2) Increasing RA (East) should DECREASE X coordinate (East is Left in astronomical convention)
    east_x, _ = wcs.all_world2pix(target_ra + 0.01, target_dec, 0)
    assert east_x < cx, "East is not aligned with negative X (+RA to the left)!"


def test_fixed_grid_consistency_across_differing_pointings(
    synthetic_fits_epoch1: fits.HDUList,
    synthetic_fits_epoch2: fits.HDUList,
):
    """Verify that two epochs with DIFFERENT pointing centers and roll angles

    are reprojected onto the EXACT SAME shared grid with identical geometry.
    """
    target_ra = 133.795129
    target_dec = -7.245147
    common_wcs, width, height = create_fixed_common_wcs(target_ra, target_dec, 0.05)

    buf1 = io.BytesIO()
    synthetic_fits_epoch1.writeto(buf1)
    obs1 = parse_fits_cutout(buf1.getvalue())

    buf2 = io.BytesIO()
    synthetic_fits_epoch2.writeto(buf2)
    obs2 = parse_fits_cutout(buf2.getvalue())

    # Epoch 2 has a 25-degree roll angle and shifted pointing
    res1 = reproject_observation_to_grid(obs1, target_ra, target_dec, common_wcs, width, height)
    res2 = reproject_observation_to_grid(obs2, target_ra, target_dec, common_wcs, width, height)

    assert res1.flux.shape == (29, 29)
    assert res2.flux.shape == (29, 29)
    assert res1.flags.shape == (29, 29)
    assert res2.flags.shape == (29, 29)

    # In both frames, target position in the shared grid must be identically (14.0, 14.0)
    assert res1.target_pixel_x == pytest.approx(14.0)
    assert res1.target_pixel_y == pytest.approx(14.0)
    assert res2.target_pixel_x == pytest.approx(14.0)
    assert res2.target_pixel_y == pytest.approx(14.0)


def test_target_motion_is_preserved():
    """Verify that a moving object's coordinate shift relative to background stars

    is preserved on the fixed grid, rather than cancelled by recentering.
    """
    target_ra = 133.795129
    target_dec = -7.245147
    common_wcs, width, height = create_fixed_common_wcs(target_ra, target_dec, 0.05)

    # Hypothesized moving target at Epoch 2 displaced by +0.005 deg Dec (~18 arcsec)
    moving_ra = target_ra
    moving_dec = target_dec + 0.005

    x1, y1 = common_wcs.all_world2pix(target_ra, target_dec, 0)
    x2, y2 = common_wcs.all_world2pix(moving_ra, moving_dec, 0)

    # Physical displacement appears as a pixel shift on the output grid
    assert x1 == pytest.approx(14.0)
    assert y1 == pytest.approx(14.0)
    # Dec displacement = +0.005 deg / 0.001712 deg/pix = ~2.92 pixels
    assert y2 > y1
    assert (y2 - y1) == pytest.approx(0.005 / DEFAULT_PLATE_SCALE_DEG, rel=1e-3)


def test_nan_sanitization_and_invalid_pixel_propagation(synthetic_fits_epoch1: fits.HDUList):
    """Input NaNs and out-of-bounds boundary pixels must be flagged as invalid (1)

    and sanitized to finite 0.0 in the flux array (preventing non-standard JSON NaNs).
    """
    target_ra = 133.795129
    target_dec = -7.245147
    # Request a large FOV (0.15 deg) so input cutout (0.05 deg) does not cover the entire grid
    common_wcs, width, height = create_fixed_common_wcs(target_ra, target_dec, 0.15)

    buf = io.BytesIO()
    # Inject NaN into synthetic fits
    synthetic_fits_epoch1[1].data[0, 0] = np.nan
    synthetic_fits_epoch1.writeto(buf)
    obs = parse_fits_cutout(buf.getvalue())

    res = reproject_observation_to_grid(obs, target_ra, target_dec, common_wcs, width, height)

    # 1. Flux must be completely finite (no NaNs or Infs)
    assert not np.any(np.isnan(res.flux))
    assert not np.any(np.isinf(res.flux))

    # 2. Out-of-bounds boundary pixels must be flagged as invalid (1)
    # The edges of the 0.15 deg grid are outside the 0.05 deg input cutout
    assert res.flags[0, 0] == 1
    assert res.flags[height - 1, width - 1] == 1

    # 3. Inside the coverage area, clean pixels must be 0
    center_y, center_x = height // 2, width // 2
    assert res.flags[center_y, center_x] == 0


def test_variance_reprojection(synthetic_fits_epoch1: fits.HDUList):
    """If variance plane is present, it must be reprojected and sanitized."""
    target_ra = 133.795129
    target_dec = -7.245147
    common_wcs, width, height = create_fixed_common_wcs(target_ra, target_dec, 0.05)

    buf = io.BytesIO()
    synthetic_fits_epoch1.writeto(buf)
    obs = parse_fits_cutout(buf.getvalue())

    res = reproject_observation_to_grid(obs, target_ra, target_dec, common_wcs, width, height)
    assert res.variance is not None
    assert res.variance.shape == (29, 29)
    assert not np.any(np.isnan(res.variance))
    assert np.all(res.variance >= 0.0)
