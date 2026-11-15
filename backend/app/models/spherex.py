"""Pydantic data models for SPHEREx Sky Viewer API.
Strictly aligned with TypeScript definitions in src/types/spherex.ts.
"""

from typing import Dict, List, Literal, Optional, Tuple
from pydantic import BaseModel, Field

# Valid SPHEREx detector bands
SpherexBand = Literal[
    "SPHEREx-D1",
    "SPHEREx-D2",
    "SPHEREx-D3",
    "SPHEREx-D4",
    "SPHEREx-D5",
    "SPHEREx-D6",
]


class TargetInfo(BaseModel):
    """Target astronomical sky position and optional catalog designation."""
    ra: float = Field(..., description="Target Right Ascension in decimal degrees (ICRS)")
    dec: float = Field(..., description="Target Declination in decimal degrees (ICRS)")
    name: Optional[str] = Field(None, description="Target name or identifier")


class WcsInfo(BaseModel):
    """Astrometric World Coordinate System (WCS) metadata for common grid."""
    crval: Tuple[float, float] = Field(..., description="Reference sky coordinates [RA_deg, Dec_deg]")
    crpix: Tuple[float, float] = Field(..., description="Reference pixel coordinates [X_pix, Y_pix] (1-based convention)")
    cdelt: Tuple[float, float] = Field(..., description="Pixel scale in degrees [deg/pix_x, deg/pix_y]")
    ctype: Tuple[str, str] = Field(..., description="Projection types, e.g. ['RA---TAN', 'DEC--TAN']")


class SpherexFrame(BaseModel):
    """A single observation epoch frame reprojected onto the common sky grid."""
    index: int = Field(..., description="0-based chronological frame index")
    mjd: float = Field(..., description="Observation Modified Julian Date (MJD_OBS)")
    dateUtc: str = Field(..., description="Observation date/time in UTC ISO 8601 format")
    wavelengthMicrons: float = Field(..., description="Central spectral wavelength in microns")
    band: SpherexBand = Field(..., description="SPHEREx detector bandpass identifier")
    width: int = Field(..., description="Image array width in pixels")
    height: int = Field(..., description="Image array height in pixels")
    flux: List[float] = Field(..., description="Flattened 1D array of surface brightness in MJy/sr (row-major order)")
    flags: Optional[List[int]] = Field(None, description="Flattened 1D array of quality flags (0 = good, 1 = invalid)")
    minFlux: float = Field(..., description="Minimum valid flux across clean pixels")
    maxFlux: float = Field(..., description="Maximum valid flux across clean pixels")
    obsId: Optional[str] = Field(None, description="Source SPHEREx observation ID for provenance")


class CatalogMarker(BaseModel):
    """Sky catalog source overlay marker."""
    id: str = Field(..., description="Unique marker identifier")
    ra: float = Field(..., description="Right Ascension in decimal degrees")
    dec: float = Field(..., description="Declination in decimal degrees")
    label: Optional[str] = Field(None, description="Human-readable label for HUD display")


class SpherexApiResponse(BaseModel):
    """Section 7 API Response Contract matching frontend SpherexApiResponse."""
    target: TargetInfo = Field(..., description="Target metadata")
    fovDegrees: float = Field(..., description="Field of view in degrees")
    band: SpherexBand = Field(..., description="Requested detector bandpass")
    dataRelease: str = Field(..., description="SPHEREx data release version (e.g. DR1)")
    wcs: WcsInfo = Field(..., description="Shared common-grid WCS metadata")
    frameCount: int = Field(..., description="Number of returned frames")
    frames: List[SpherexFrame] = Field(..., description="Chronological list of aligned frames")
    markers: Optional[List[CatalogMarker]] = Field(None, description="Catalog overlay markers")
    isSampleData: bool = Field(False, description="Flag indicating synthetic vs real science data")


class RgbChannelInfo(BaseModel):
    """Calibrated science data and robust display limits for a single RGB color channel."""
    band: SpherexBand = Field(..., description="SPHEREx detector bandpass identifier")
    wavelengthMicrons: float = Field(..., description="Central spectral wavelength in microns")
    obsId: str = Field(..., description="Source SPHEREx observation ID")
    mjd: float = Field(..., description="Observation Modified Julian Date")
    dateUtc: str = Field(..., description="Observation timestamp in UTC ISO format")
    flux: List[float] = Field(..., description="Calibrated surface brightness array in MJy/sr (row-major)")
    flags: List[int] = Field(..., description="Binary quality flags (0 = clean, 1 = invalid)")
    minFlux: float = Field(..., description="Minimum valid flux across clean pixels")
    maxFlux: float = Field(..., description="Maximum valid flux across clean pixels")
    p1Flux: float = Field(..., description="1st percentile flux across clean pixels")
    p99Flux: float = Field(..., description="99th percentile flux across clean pixels")


class RgbCompositeResponse(BaseModel):
    """API response model for multi-band false-color infrared RGB composite."""
    target: TargetInfo = Field(..., description="Target metadata")
    fovDegrees: float = Field(..., description="Field of view in degrees")
    dataRelease: str = Field(..., description="SPHEREx data release version")
    wcs: WcsInfo = Field(..., description="Shared common celestial tangent plane WCS")
    width: int = Field(..., description="Composite image width in pixels")
    height: int = Field(..., description="Composite image height in pixels")
    channels: Dict[str, RgbChannelInfo] = Field(..., description="Dictionary mapping 'red', 'green', 'blue' to channel data")
    scientificNotice: str = Field(..., description="Scientific provenance notice clarifying false-color infrared visualization")
    isSampleData: bool = Field(False, description="Strictly False for real observations")
