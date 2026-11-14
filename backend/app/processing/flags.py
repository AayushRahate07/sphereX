"""SPHEREx Level 2 Quality Flag Definitions and Processing Policy.

Authoritative source: SPHEREx Explanatory Supplement: Level 2 Data Products
(NASA/IPAC Infrared Science Archive, Caltech/JPL).
Stored in Level 2 MEF HDU 2 ('FLAGS') as 32-bit integers.
"""

from typing import Dict
import numpy as np

# =============================================================================
# SPHEREx Level 2 Image Flag Bitmask Definitions
# =============================================================================
FLAG_TRANSIENT = 1 << 0        # 1: Cosmic ray hit / ramp transient event (Fatal)
FLAG_OVERFLOW = 1 << 1         # 2: Saturated / overflow > ~50% well depth (Fatal)
FLAG_SUR_ERROR = 1 << 2        # 4: Early sample-up-the-ramp readout error (Fatal)
FLAG_NONFUNC = 1 << 6          # 64: Dead / non-functional detector pixel (Fatal)
FLAG_DICHROIC = 1 << 7         # 128: Obscured / masked by dichroic layout (Fatal)
FLAG_MISSING_DATA = 1 << 9     # 512: No readout data available (Fatal)
FLAG_HOT = 1 << 10             # 1024: Hot / excessively noisy pixel (Fatal)
FLAG_COLD = 1 << 11            # 2048: Cold / dead / unresponsive pixel (Fatal)
FLAG_FULLSAMPLE = 1 << 12      # 4096: Full sample-up-the-ramp history available (Informational/High Quality)
FLAG_PHANMISS = 1 << 14        # 16384: Phantom reference pixel missing anomaly (Fatal)
FLAG_NONLINEAR = 1 << 15       # 32768: Severe uncorrectable non-linearity (Fatal)
FLAG_PERSIST = 1 << 17         # 131072: Latent persistent charge contamination (Cautionary)
FLAG_OUTLIER = 1 << 19         # 524288: Statistical outlier across ramps (Cautionary)
FLAG_CROSSTALK = 1 << 20       # 1048576: Electronic crosstalk from another channel (Cautionary)
FLAG_SOURCE = 1 << 21          # 2097152: Coincides with known catalog reference source (Informational/VALID)
FLAG_GHOST = 1 << 22           # 4194304: Optical ghost reflection artifact (Cautionary)
FLAG_GHOST_FPA = 1 << 23       # 8388608: Focal plane assembly reflection ghost (Cautionary)
FLAG_GHOST_EXT = 1 << 24       # 16777216: Extended optical ghost artifact (Cautionary)
FLAG_STREAK = 1 << 25          # 33554432: Satellite, debris, or asteroid streak (Cautionary)
FLAG_BLOOM = 1 << 26           # 67108864: Blooming path from saturated neighbor (Fatal)
FLAG_SNOWBALL = 1 << 27        # 134217728: Energetic particle hit core (Fatal)
FLAG_HALO = 1 << 28            # 268435456: Scattered light halo from bright star (Cautionary)
FLAG_SATELLITE_HALO = 1 << 29  # 536870912: Satellite glint stray light halo (Cautionary)

# Composite mask of all fatal conditions that completely invalidate physical pixel flux
INVALIDATING_MASK: int = (
    FLAG_TRANSIENT
    | FLAG_OVERFLOW
    | FLAG_SUR_ERROR
    | FLAG_NONFUNC
    | FLAG_DICHROIC
    | FLAG_MISSING_DATA
    | FLAG_HOT
    | FLAG_COLD
    | FLAG_PHANMISS
    | FLAG_NONLINEAR
    | FLAG_BLOOM
    | FLAG_SNOWBALL
)

# Human-readable dictionary of documented bit meanings
FLAG_DEFINITIONS: Dict[str, Dict[str, str | int | bool]] = {
    "TRANSIENT": {"bit": 0, "val": FLAG_TRANSIENT, "invalidating": True, "desc": "Cosmic ray / ramp transient event"},
    "OVERFLOW": {"bit": 1, "val": FLAG_OVERFLOW, "invalidating": True, "desc": "Saturation / overflow"},
    "SUR_ERROR": {"bit": 2, "val": FLAG_SUR_ERROR, "invalidating": True, "desc": "Early ramp readout error"},
    "NONFUNC": {"bit": 6, "val": FLAG_NONFUNC, "invalidating": True, "desc": "Dead / non-functional pixel"},
    "DICHROIC": {"bit": 7, "val": FLAG_DICHROIC, "invalidating": True, "desc": "Dichroic layout mask boundary"},
    "MISSING_DATA": {"bit": 9, "val": FLAG_MISSING_DATA, "invalidating": True, "desc": "Missing pixel data"},
    "HOT": {"bit": 10, "val": FLAG_HOT, "invalidating": True, "desc": "Hot / noisy pixel"},
    "COLD": {"bit": 11, "val": FLAG_COLD, "invalidating": True, "desc": "Cold / dead pixel"},
    "FULLSAMPLE": {"bit": 12, "val": FLAG_FULLSAMPLE, "invalidating": False, "desc": "Full sample history available (benign)"},
    "PHANMISS": {"bit": 14, "val": FLAG_PHANMISS, "invalidating": True, "desc": "Phantom pixel missing anomaly"},
    "NONLINEAR": {"bit": 15, "val": FLAG_NONLINEAR, "invalidating": True, "desc": "Severe uncorrectable non-linearity"},
    "PERSIST": {"bit": 17, "val": FLAG_PERSIST, "invalidating": False, "desc": "Latent charge persistence"},
    "OUTLIER": {"bit": 19, "val": FLAG_OUTLIER, "invalidating": False, "desc": "Statistical outlier across ramps"},
    "CROSSTALK": {"bit": 20, "val": FLAG_CROSSTALK, "invalidating": False, "desc": "Electronic crosstalk artifact"},
    "SOURCE": {"bit": 21, "val": FLAG_SOURCE, "invalidating": False, "desc": "Coincides with known catalog source (benign)"},
    "GHOST": {"bit": 22, "val": FLAG_GHOST, "invalidating": False, "desc": "Optical ghost artifact"},
    "GHOST_FPA": {"bit": 23, "val": FLAG_GHOST_FPA, "invalidating": False, "desc": "FPA ghost artifact"},
    "GHOST_EXT": {"bit": 24, "val": FLAG_GHOST_EXT, "invalidating": False, "desc": "Extended ghost artifact"},
    "STREAK": {"bit": 25, "val": FLAG_STREAK, "invalidating": False, "desc": "Satellite / debris streak"},
    "BLOOM": {"bit": 26, "val": FLAG_BLOOM, "invalidating": True, "desc": "Charge blooming from saturated source"},
    "SNOWBALL": {"bit": 27, "val": FLAG_SNOWBALL, "invalidating": True, "desc": "Energetic snowball hit core"},
    "HALO": {"bit": 28, "val": FLAG_HALO, "invalidating": False, "desc": "Stray light halo from bright source"},
    "SATELLITE_HALO": {"bit": 29, "val": FLAG_SATELLITE_HALO, "invalidating": False, "desc": "Satellite glint halo"},
}


def create_binary_quality_mask(
    raw_flags: np.ndarray,
    invalidating_mask: int = INVALIDATING_MASK,
) -> np.ndarray:
    """Convert raw 32-bit SPHEREx Level 2 flags into an 8-bit binary quality mask.

    Strictly complies with the frontend contract `flags?: Uint8Array; // Bad pixel flags (0 = good)`.
    Never casts raw 32-bit integers directly to uint8 (which would truncate bits > 7 modulo 256).

    Args:
        raw_flags: Integer array (int32/uint32) of SPHEREx Level 2 flags.
        invalidating_mask: Bitmask specifying fatal conditions.

    Returns:
        np.ndarray of uint8 where 0 = clean/valid pixel, 1 = corrupted/invalid pixel.
    """
    # Bitwise check against fatal conditions
    is_invalid = (raw_flags.astype(np.int64) & invalidating_mask) != 0
    return is_invalid.astype(np.uint8)
