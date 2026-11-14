"""Configuration and constants for SPHEREx Sky Viewer backend."""

import os
from pathlib import Path
from typing import Dict, List, Tuple

# Base directories
BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent
CACHE_DIR = BACKEND_DIR / "cache"
FITS_CACHE_DIR = CACHE_DIR / "fits"
TAP_CACHE_DIR = CACHE_DIR / "tap"

# Known scratch directory from verification milestones (fallback for pre-cached data)
SCRATCH_DIR = Path(r"C:\Users\gunja\.gemini\antigravity\brain\cab8a4a9-12ce-4bdc-a372-9dc9c7443cb6\scratch")

# IRSA service endpoints
IRSA_TAP_URL = "https://irsa.ipac.caltech.edu/TAP/sync"
IRSA_DATALINK_URL = "https://irsa.ipac.caltech.edu/datalink/links/spherex"

# Optical & Astrometric defaults
DEFAULT_FOV_DEG = 0.05
DEFAULT_PLATE_SCALE_DEG = 0.001712  # ~6.1632 arcsec/pixel
DEFAULT_BAND = "SPHEREx-D6"
DEFAULT_RELEASE = "DR1"
DEFAULT_MAX_FRAMES = 10
ABSOLUTE_MAX_FRAMES = 50

# Supported detector bands strictly aligned with src/types/spherex.ts
SUPPORTED_BANDS: Tuple[str, ...] = (
    "SPHEREx-D1",
    "SPHEREx-D2",
    "SPHEREx-D3",
    "SPHEREx-D4",
    "SPHEREx-D5",
    "SPHEREx-D6",
)

# Nominal central wavelength per detector band in microns
# (Used when FITS HDU 5/6 CWAVE header is unavailable)
BAND_NOMINAL_WAVELENGTHS: Dict[str, float] = {
    "SPHEREx-D1": 0.93,
    "SPHEREx-D2": 1.38,
    "SPHEREx-D3": 2.03,
    "SPHEREx-D4": 2.92,
    "SPHEREx-D5": 3.93,
    "SPHEREx-D6": 4.71,
}

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class AstrometryConfig:
    """Verified astrometric parameters for high-proper-motion targets."""
    reference_ra: float      # Right Ascension in degrees at reference_epoch
    reference_dec: float     # Declination in degrees at reference_epoch
    reference_epoch: float   # Decimal year (e.g. 2010.54 for Luhman 2014)
    pm_ra_cosdec: float      # Proper motion in RA * cos(dec) in mas/yr
    pm_dec: float            # Proper motion in Dec in mas/yr
    parallax_mas: float      # Trigonometric parallax in mas


# Supported challenge target presets strictly aligned with src/types/spherex.ts
TARGET_PRESETS: List[Dict[str, Any]] = [
    {
        "name": "WISE 0855",
        "ra": 133.795129,
        "dec": -7.245147,
        "defaultFov": 0.05,
        "astrometry": AstrometryConfig(
            reference_ra=133.795129,
            reference_dec=-7.245147,
            reference_epoch=2010.54,
            pm_ra_cosdec=-8123.7,
            pm_dec=673.2,
            parallax_mas=439.0,
        ),
    },
    {"name": "Barnard's Star", "ra": 269.452075, "dec": 4.693364, "defaultFov": 0.05, "astrometry": None},
    {"name": "Epsilon Indi B", "ra": 330.840200, "dec": -56.786500, "defaultFov": 0.05, "astrometry": None},
    {"name": "RW Aurigae", "ra": 77.108200, "dec": 30.401400, "defaultFov": 0.05, "astrometry": None},
    {"name": "R Draconis", "ra": 247.554400, "dec": 66.702900, "defaultFov": 0.05, "astrometry": None},
]
