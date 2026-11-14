"""FITS Parsing and Validation Module for SPHEREx Level 2 Spectral Cutouts.

Extracts science image, astrometric WCS, 32-bit quality flags, variance,
and observation timing metadata.
"""

from dataclasses import dataclass
import io
from pathlib import Path
from typing import Optional, Union
from astropy.io import fits
from astropy.wcs import WCS
import numpy as np

from backend.app.config import BAND_NOMINAL_WAVELENGTHS


class InvalidFitsStructureError(ValueError):
    """Raised when a FITS file does not contain the required Level 2 HDUs or metadata."""
    pass


@dataclass
class ParsedFitsObservation:
    """Parsed in-memory representation of a SPHEREx Level 2 cutout observation."""
    obs_id: str
    date_obs: str
    mjd_obs: float
    band: str
    wavelength_microns: float
    flux: np.ndarray          # 2D float32 array in MJy/sr
    raw_flags: np.ndarray     # 2D int32 array of 32-bit bitmasks
    variance: Optional[np.ndarray]  # 2D float32 array in (MJy/sr)^2
    wcs: WCS                  # Astropy WCS instance with SIP distortion
    bunit: str = "MJy/sr"


def parse_fits_cutout(
    source: Union[bytes, str, Path],
    band: str = "SPHEREx-D1",
    fallback_obs_id: Optional[str] = None,
    fallback_mjd: Optional[float] = None,
) -> ParsedFitsObservation:
    """Parse a SPHEREx Level 2 Multi-Extension FITS (MEF) cutout.

    Args:
        source: Raw FITS bytes, file path string, or Path object.
        band: Associated detector bandpass.
        fallback_obs_id: Optional fallback observation ID.
        fallback_mjd: Optional fallback MJD.

    Returns:
        ParsedFitsObservation containing validated arrays, WCS, and timing.

    Raises:
        InvalidFitsStructureError: If required HDUs or cards are missing or corrupted.
    """
    try:
        if isinstance(source, (str, Path)):
            hdul = fits.open(source)
            close_on_exit = True
        else:
            hdul = fits.open(io.BytesIO(source))
            close_on_exit = False
    except Exception as exc:
        raise InvalidFitsStructureError(f"Failed to open FITS source: {exc}") from exc

    try:
        if len(hdul) < 2:
            raise InvalidFitsStructureError(
                f"FITS HDU list contains only {len(hdul)} HDUs. At least 2 HDUs (Primary + IMAGE) are required."
            )

        # 1. Locate science image HDU
        if "IMAGE" in hdul:
            sci_hdu = hdul["IMAGE"]
        elif len(hdul) > 1 and hdul[1].data is not None:
            sci_hdu = hdul[1]
        else:
            raise InvalidFitsStructureError("No valid science IMAGE HDU found in FITS structure.")

        if sci_hdu.data is None or sci_hdu.data.ndim != 2:
            raise InvalidFitsStructureError(
                f"Science IMAGE HDU data is missing or not 2-dimensional (ndim={getattr(sci_hdu.data, 'ndim', None)})."
            )

        sci_hdr = sci_hdu.header
        flux_array = sci_hdu.data.astype(np.float32)

        # 2. Extract WCS
        try:
            wcs = WCS(sci_hdr)
            if not wcs.is_celestial:
                raise InvalidFitsStructureError("Extracted WCS does not represent celestial coordinates.")
        except Exception as exc:
            raise InvalidFitsStructureError(f"Failed to construct astrometric WCS from science header: {exc}") from exc

        # 3. Locate FLAGS HDU
        if "FLAGS" in hdul:
            raw_flags = hdul["FLAGS"].data.astype(np.int32)
        elif len(hdul) > 2 and hdul[2].data is not None and hdul[2].data.shape == flux_array.shape:
            raw_flags = hdul[2].data.astype(np.int32)
        else:
            # If flags HDU is missing, default to zero (clean)
            raw_flags = np.zeros(flux_array.shape, dtype=np.int32)

        # 4. Locate VARIANCE HDU
        variance: Optional[np.ndarray] = None
        if "VARIANCE" in hdul and hdul["VARIANCE"].data is not None:
            variance = hdul["VARIANCE"].data.astype(np.float32)
        elif len(hdul) > 3 and hdul[3].data is not None and hdul[3].data.shape == flux_array.shape:
            variance = hdul[3].data.astype(np.float32)

        # 5. Extract Timing & Metadata
        pri_hdr = hdul[0].header if len(hdul) > 0 else {}
        obs_id = (
            sci_hdr.get("OBSID")
            or pri_hdr.get("OBSID")
            or fallback_obs_id
            or "UNKNOWN_OBS_ID"
        )
        date_obs = (
            sci_hdr.get("DATE-OBS")
            or pri_hdr.get("DATE-OBS")
            or sci_hdr.get("DATE")
            or pri_hdr.get("DATE")
            or "2025-01-01T00:00:00"
        )
        mjd_obs = (
            sci_hdr.get("MJD-OBS")
            or pri_hdr.get("MJD-OBS")
            or sci_hdr.get("MJD_OBS")
            or pri_hdr.get("MJD_OBS")
            or fallback_mjd
            or 60800.0
        )
        bunit = sci_hdr.get("BUNIT", "MJy/sr").strip()

        # 6. Extract or estimate central wavelength
        cwave = (
            sci_hdr.get("CWAVE")
            or pri_hdr.get("CWAVE")
        )
        if cwave is None and "EPSF" in hdul and getattr(hdul["EPSF"], "data", None) is not None:
            epsf_data = hdul["EPSF"].data
            if hasattr(epsf_data, "names") and "CWAVE" in epsf_data.names:
                cwave = float(epsf_data["CWAVE"][0])

        if cwave is None:
            cwave = BAND_NOMINAL_WAVELENGTHS.get(band, 1.0)

        return ParsedFitsObservation(
            obs_id=str(obs_id),
            date_obs=str(date_obs),
            mjd_obs=float(mjd_obs),
            band=band,
            wavelength_microns=float(cwave),
            flux=flux_array,
            raw_flags=raw_flags,
            variance=variance,
            wcs=wcs,
            bunit=bunit,
        )

    finally:
        if close_on_exit:
            hdul.close()
