"""Pytest configuration and deterministic synthetic FITS fixtures."""

import os
from pathlib import Path
from typing import Any, Dict, List
from astropy.io import fits
from astropy.wcs import WCS
import numpy as np
import pytest

from backend.app.processing.flags import (
    FLAG_COLD,
    FLAG_FULLSAMPLE,
    FLAG_NONFUNC,
    FLAG_OVERFLOW,
    FLAG_SOURCE,
    FLAG_SUR_ERROR,
    FLAG_TRANSIENT,
)


def create_synthetic_level2_fits(
    pointing_ra: float = 133.795129,
    pointing_dec: float = -7.245147,
    roll_deg: float = 0.0,
    width: int = 29,
    height: int = 29,
    obs_id: str = "SYNTH_2025W19_0001_1",
    mjd: float = 60800.5,
    date_obs: str = "2025-05-05T12:00:00.000",
    has_target_peak: bool = True,
    target_offset_x: float = 0.0,
    target_offset_y: float = 0.0,
    include_nans: bool = False,
) -> fits.HDUList:
    """Create a fully compliant in-memory SPHEREx Level 2 Multi-Extension FITS object.

    HDU 0: PRIMARY header
    HDU 1: IMAGE (float32, 2D science array, full astrometric WCS with rotation)
    HDU 2: FLAGS (int32, 2D bitmask array)
    HDU 3: VARIANCE (float32, 2D variance array)
    """
    pri_hdr = fits.Header()
    pri_hdr["TELESCOP"] = "SPHEREx"
    pri_hdr["INSTRUME"] = "SPHEREx"
    pri_hdr["DATE-OBS"] = date_obs
    pri_hdr["MJD-OBS"] = mjd
    pri_hdr["OBSID"] = obs_id
    pri_hdu = fits.PrimaryHDU(header=pri_hdr)

    # 1. Construct Science Array with known background + Gaussian peak
    np.random.seed(int(mjd) % 1000)
    data = np.random.normal(loc=0.5, scale=0.05, size=(height, width)).astype(np.float32)

    # Add reference star at fixed position (x=5, y=5)
    data[5, 5] += 5.0

    if has_target_peak:
        # Target peak near center (14, 14) + offset
        cx = int(round(14 + target_offset_x))
        cy = int(round(14 + target_offset_y))
        if 0 <= cx < width and 0 <= cy < height:
            data[cy, cx] += 10.0

    if include_nans:
        data[0, 0] = np.nan
        data[height - 1, width - 1] = np.nan

    # 2. Construct WCS with specified roll angle
    sci_hdr = fits.Header()
    sci_hdr["BUNIT"] = "MJy/sr"
    sci_hdr["OBSID"] = obs_id
    sci_hdr["DATE-OBS"] = date_obs
    sci_hdr["MJD-OBS"] = mjd
    sci_hdr["CWAVE"] = 4.70

    plate_scale = 0.001712
    sci_hdr["CTYPE1"] = "RA---TAN"
    sci_hdr["CTYPE2"] = "DEC--TAN"
    sci_hdr["CRVAL1"] = pointing_ra
    sci_hdr["CRVAL2"] = pointing_dec
    sci_hdr["CRPIX1"] = (width + 1) / 2.0
    sci_hdr["CRPIX2"] = (height + 1) / 2.0

    # Rotation matrix
    theta = np.radians(roll_deg)
    cos_t = np.cos(theta)
    sin_t = np.sin(theta)
    # CD matrix: CDELT1 = -plate_scale, CDELT2 = +plate_scale
    sci_hdr["CD1_1"] = -plate_scale * cos_t
    sci_hdr["CD1_2"] = plate_scale * sin_t
    sci_hdr["CD2_1"] = -plate_scale * sin_t
    sci_hdr["CD2_2"] = -plate_scale * cos_t

    sci_hdu = fits.ImageHDU(data=data, header=sci_hdr, name="IMAGE")

    # 3. Construct FLAGS array with controlled test bits
    flags_data = np.zeros((height, width), dtype=np.int32)
    # Mark reference star at (5, 5) with SOURCE flag
    flags_data[5, 5] = FLAG_SOURCE
    # Mark target with SOURCE | FULLSAMPLE
    flags_data[14, 14] = FLAG_SOURCE | FLAG_FULLSAMPLE
    # Mark cosmic ray at (20, 20)
    flags_data[20, 20] = FLAG_TRANSIENT | FLAG_SUR_ERROR
    # Mark saturated pixel at (10, 25)
    flags_data[10, 25] = FLAG_OVERFLOW
    # Mark dead pixel at (2, 2)
    flags_data[2, 2] = FLAG_NONFUNC | FLAG_COLD

    flags_hdu = fits.ImageHDU(data=flags_data, name="FLAGS")

    # 4. Construct VARIANCE array
    var_data = np.full((height, width), 0.0025, dtype=np.float32)
    var_hdu = fits.ImageHDU(data=var_data, name="VARIANCE")

    return fits.HDUList([pri_hdu, sci_hdu, flags_hdu, var_hdu])


@pytest.fixture
def synthetic_fits_epoch1() -> fits.HDUList:
    """Fixture providing Synthetic Epoch 1 (unrotated pointing)."""
    return create_synthetic_level2_fits(
        pointing_ra=133.795129,
        pointing_dec=-7.245147,
        roll_deg=0.0,
        obs_id="SYNTH_EPOCH1",
        mjd=60800.1,
        date_obs="2025-05-05T02:24:00.000",
    )


@pytest.fixture
def synthetic_fits_epoch2() -> fits.HDUList:
    """Fixture providing Synthetic Epoch 2 (rotated by 25 deg, pointing dither)."""
    return create_synthetic_level2_fits(
        pointing_ra=133.805129,
        pointing_dec=-7.240147,
        roll_deg=25.0,
        obs_id="SYNTH_EPOCH2",
        mjd=60845.2,
        date_obs="2025-06-19T04:48:00.000",
    )


@pytest.fixture
def mock_tap_candidates() -> List[Dict[str, Any]]:
    """Fixture providing mock TAP records for testing selection service."""
    return [
        {
            "obs_id": "OBS_DR1_001_D6",
            "obs_collection": "spherex_dr1",
            "energy_bandpassname": "SPHEREx-D6",
            "t_min": 60800.5,
            "t_max": 60800.5013,
            "t_exptime": 113.6,
            "s_ra": 133.795,
            "s_dec": -7.245,
            "access_url": "https://irsa.ipac.caltech.edu/datalink/mock1",
            "obs_release_date": "2026-07-25",
        },
        {
            "obs_id": "OBS_DR1_002_D6",
            "obs_collection": "spherex_dr1",
            "energy_bandpassname": "SPHEREx-D6",
            "t_min": 60850.2,
            "t_max": 60850.2013,
            "t_exptime": 113.6,
            "s_ra": 133.796,
            "s_dec": -7.244,
            "access_url": "https://irsa.ipac.caltech.edu/datalink/mock2",
            "obs_release_date": "2026-07-25",
        },
        {
            "obs_id": "OBS_DR1_003_D1",  # Different band
            "obs_collection": "spherex_dr1",
            "energy_bandpassname": "SPHEREx-D1",
            "t_min": 60800.5,
            "t_max": 60800.5013,
            "t_exptime": 113.6,
            "s_ra": 133.795,
            "s_dec": -7.245,
            "access_url": "https://irsa.ipac.caltech.edu/datalink/mock3",
            "obs_release_date": "2026-07-25",
        },
    ]
