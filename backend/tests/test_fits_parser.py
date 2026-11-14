"""Unit tests for SPHEREx Level 2 FITS Parser and validation error handling."""

import io
from astropy.io import fits
import numpy as np
import pytest

from backend.app.processing.fits_parser import (
    InvalidFitsStructureError,
    ParsedFitsObservation,
    parse_fits_cutout,
)


def test_parse_valid_synthetic_fits(synthetic_fits_epoch1: fits.HDUList):
    """Successfully parse valid Level 2 synthetic FITS."""
    buf = io.BytesIO()
    synthetic_fits_epoch1.writeto(buf)
    fits_bytes = buf.getvalue()

    parsed = parse_fits_cutout(fits_bytes, band="SPHEREx-D6")
    assert isinstance(parsed, ParsedFitsObservation)
    assert parsed.obs_id == "SYNTH_EPOCH1"
    assert parsed.mjd_obs == pytest.approx(60800.1)
    assert parsed.date_obs == "2025-05-05T02:24:00.000"
    assert parsed.band == "SPHEREx-D6"
    assert parsed.wavelength_microns == pytest.approx(4.70)
    assert parsed.flux.shape == (29, 29)
    assert parsed.raw_flags.shape == (29, 29)
    assert parsed.variance is not None
    assert parsed.variance.shape == (29, 29)
    assert parsed.wcs.is_celestial


def test_missing_image_hdu_raises_error():
    """FITS missing science IMAGE HDU must raise InvalidFitsStructureError."""
    pri = fits.PrimaryHDU()
    hdul = fits.HDUList([pri])
    buf = io.BytesIO()
    hdul.writeto(buf)

    with pytest.raises(InvalidFitsStructureError, match="contains only 1 HDUs"):
        parse_fits_cutout(buf.getvalue())


def test_empty_or_1d_image_data_raises_error():
    """Science image with 1D data or None must raise InvalidFitsStructureError."""
    pri = fits.PrimaryHDU()
    sci = fits.ImageHDU(data=np.array([1.0, 2.0, 3.0]), name="IMAGE")
    hdul = fits.HDUList([pri, sci])
    buf = io.BytesIO()
    hdul.writeto(buf)

    with pytest.raises(InvalidFitsStructureError, match="not 2-dimensional"):
        parse_fits_cutout(buf.getvalue())


def test_corrupted_fits_bytes_raises_error():
    """Random garbage bytes must raise InvalidFitsStructureError."""
    garbage = b"NOT_A_FITS_FILE_JUST_RANDOM_CORRUPT_BYTES_123456789"
    with pytest.raises(InvalidFitsStructureError, match="Failed to open FITS source"):
        parse_fits_cutout(garbage)


def test_fallback_metadata_applied():
    """If OBSID and MJD header cards are missing, fallbacks should be applied."""
    pri = fits.PrimaryHDU()
    # Construct minimal valid WCS
    sci_hdr = fits.Header()
    sci_hdr["CTYPE1"] = "RA---TAN"
    sci_hdr["CTYPE2"] = "DEC--TAN"
    sci_hdr["CRVAL1"] = 100.0
    sci_hdr["CRVAL2"] = 20.0
    sci_hdr["CRPIX1"] = 5.0
    sci_hdr["CRPIX2"] = 5.0
    sci_hdr["CDELT1"] = -0.0017
    sci_hdr["CDELT2"] = 0.0017
    sci = fits.ImageHDU(data=np.ones((10, 10), dtype=np.float32), header=sci_hdr, name="IMAGE")

    hdul = fits.HDUList([pri, sci])
    buf = io.BytesIO()
    hdul.writeto(buf)

    parsed = parse_fits_cutout(
        buf.getvalue(),
        band="SPHEREx-D1",
        fallback_obs_id="FALLBACK_001",
        fallback_mjd=61000.0,
    )
    assert parsed.obs_id == "FALLBACK_001"
    assert parsed.mjd_obs == pytest.approx(61000.0)
    assert parsed.wavelength_microns == pytest.approx(0.93)  # D1 nominal fallback
