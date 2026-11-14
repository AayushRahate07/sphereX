"""Processing package initialization."""

from .fits_parser import InvalidFitsStructureError, ParsedFitsObservation, parse_fits_cutout
from .flags import (
    FLAG_SOURCE,
    FLAG_TRANSIENT,
    INVALIDATING_MASK,
    create_binary_quality_mask,
)
from .reprojection import (
    ReprojectedFrameResult,
    create_fixed_common_wcs,
    reproject_observation_to_grid,
)

__all__ = [
    "FLAG_SOURCE",
    "FLAG_TRANSIENT",
    "INVALIDATING_MASK",
    "InvalidFitsStructureError",
    "ParsedFitsObservation",
    "ReprojectedFrameResult",
    "create_binary_quality_mask",
    "create_fixed_common_wcs",
    "parse_fits_cutout",
    "reproject_observation_to_grid",
]
