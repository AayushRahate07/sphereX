"""
SPHEREx Sky Viewer — Member 3 Data Models and Analysis Interfaces
==================================================================
This module defines the shared astronomical data structures, validation rules,
and function contracts between Member 2 (Backend / Pipeline) and Member 3
(Spectrum, Checks and Release), as well as the JSON-compatible outputs consumed
by Member 1 (Frontend UI).

Astrophysical Context:
----------------------
SPHEREx surveys the sky in 102 spectral bands using six 2048x2048 HgCdTe
detector arrays with Linear Variable Filters (LVF).
- Detectors 1-3: 0.75 - 2.42 um (R ~ 41)
- Detector 4: 2.42 - 3.82 um (R ~ 35)
- Detector 5: 3.82 - 4.42 um (R ~ 110)
- Detector 6: 4.42 - 5.00 um (R ~ 130)
- Pixel scale: ~6.2 arcsec/pixel
- PSF FWHM: ~5-6 arcsec (~1 pixel FWHM)
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import IntFlag
from typing import Any, Dict, List, Optional, Tuple
import numpy as np


# -----------------------------------------------------------------------------
# SPHEREx Instrument Constants & Bandpasses
# -----------------------------------------------------------------------------
SPHEREX_DETECTOR_BANDS: Dict[int, Tuple[float, float]] = {
    1: (0.75, 1.11),  # Band 1: Near-IR (R ~ 41)
    2: (1.11, 1.64),  # Band 2: Near-IR (R ~ 41)
    3: (1.64, 2.42),  # Band 3: Near-IR (R ~ 41)
    4: (2.42, 3.82),  # Band 4: Mid-IR (R ~ 35)
    5: (3.82, 4.42),  # Band 5: Mid-IR (R ~ 110)
    6: (4.42, 5.00),  # Band 6: Mid-IR (R ~ 130)
}

NOMINAL_PIXEL_SCALE_ARCSEC: float = 6.2
AB_ZEROPOINT_JY: float = 3631.0  # Definition of AB magnitude zero point (3631 Jansky)


# -----------------------------------------------------------------------------
# Quality Flags (Bitmask)
# -----------------------------------------------------------------------------
class QualityFlag(IntFlag):
    """
    Standardized bitwise quality flags for SPHEREx pixel and frame processing.
    Multiple flags can be combined using bitwise OR (|).
    """
    GOOD = 0
    BAD_PIXEL = 1 << 0          # Bit 0 (1): Dead, hot, or defective pixel
    SATURATED = 1 << 1          # Bit 1 (2): Signal exceeds detector full-well linear limit
    COSMIC_RAY = 1 << 2         # Bit 2 (4): Cosmic ray or transient artifact
    EDGE_ARTIFACT = 1 << 3      # Bit 3 (8): Aperture/annulus truncated by cutout border
    LOW_SNR = 1 << 4            # Bit 4 (16): Signal-to-noise ratio below threshold (< 3.0)
    CALIBRATION_WARN = 1 << 5   # Bit 5 (32): Unreliable flux conversion or uncalibrated band
    MISSING_FRAME = 1 << 6      # Bit 6 (64): Expected observation epoch or band unavailable


# =============================================================================
# SPHEREx Level 2 Official Mission Flag Bitmask Definitions (NASA/IPAC IRSA)
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


def normalize_quality_flags(
    raw_flags: np.ndarray,
    is_mission_flags: bool = True,
) -> np.ndarray:
    """
    Normalize raw FITS quality bitmasks into analysis-quality QualityFlag bitmasks.

    Distinguishes:
    - Official 32-bit SPHEREx Level 2 flags (HDU 2 'FLAGS')
    - Legacy / Mock 7-bit analysis flags (HDU 3 'MASK')

    Guarantees:
    - FLAG_SOURCE (2097152) and FLAG_FULLSAMPLE (4096) are preserved in raw_flags
      and NEVER mapped to fatal QualityFlag defects.
    - True fatal pixel conditions (OVERFLOW, BLOOM, TRANSIENT, SNOWBALL, NONFUNC,
      SUR_ERROR, DICHROIC, HOT, COLD, etc.) map to SATURATED, COSMIC_RAY, or BAD_PIXEL.
    - Cautionary conditions map to CALIBRATION_WARN.
    """
    if not is_mission_flags:
        return raw_flags.copy().astype(np.int32)

    norm_mask = np.zeros(raw_flags.shape, dtype=np.int32)

    # 1. Saturated pixels: overflow or blooming
    sat_bits = FLAG_OVERFLOW | FLAG_BLOOM
    norm_mask[(raw_flags & sat_bits) > 0] |= int(QualityFlag.SATURATED)

    # 2. Cosmic ray hits & energetic particle cores (transients)
    cr_bits = FLAG_TRANSIENT | FLAG_SNOWBALL
    norm_mask[(raw_flags & cr_bits) > 0] |= int(QualityFlag.COSMIC_RAY)

    # 3. Fatal detector defects
    fatal_defect_bits = (
        FLAG_SUR_ERROR
        | FLAG_NONFUNC
        | FLAG_DICHROIC
        | FLAG_MISSING_DATA
        | FLAG_HOT
        | FLAG_COLD
        | FLAG_PHANMISS
        | FLAG_NONLINEAR
    )
    norm_mask[(raw_flags & fatal_defect_bits) > 0] |= int(QualityFlag.BAD_PIXEL)

    # 4. Cautionary artifacts: mark with CALIBRATION_WARN
    caution_bits = (
        FLAG_PERSIST
        | FLAG_OUTLIER
        | FLAG_CROSSTALK
        | FLAG_GHOST
        | FLAG_GHOST_FPA
        | FLAG_GHOST_EXT
        | FLAG_STREAK
        | FLAG_HALO
        | FLAG_SATELLITE_HALO
    )
    norm_mask[(raw_flags & caution_bits) > 0] |= int(QualityFlag.CALIBRATION_WARN)

    return norm_mask


# -----------------------------------------------------------------------------
# Shared Input Model: SPHERExFrame (Member 2 -> Member 3)
# -----------------------------------------------------------------------------
@dataclass
class SPHERExFrame:
    """
    A single localized image cutout and associated metadata from SPHEREx.
    This is the core data format provided by the Member 2 (Backend) data pipeline.

    Scientific Units & Contracts:
    -----------------------------
    - `data`: 2D float array in physical units (typically 'MJy/sr' for surface
              brightness or 'uJy/pixel' for calibrated flux density).
    - `uncertainty`: 2D float array representing 1-sigma Gaussian error per pixel
              (standard deviation sigma, NOT variance sigma^2). Unavailable or
              uncalibrated uncertainty is represented as NaN.
    - `mask`: 2D integer bitmask representing normalized pixel-level quality flags
              conforming to the QualityFlag enum.
    - `raw_flags`: Optional 2D integer array preserving the original, unmodified
              32-bit SPHEREx Level 2 mission flag bitmask from FITS 'FLAGS' extension.
    - `wavelength_um`: Central wavelength in micrometers (microns).
    - `pixel_scale_arcsec`: Pixel angular scale in arcseconds (nominal 6.2).
    """
    data: np.ndarray
    uncertainty: np.ndarray
    mask: np.ndarray
    frame_id: str
    mjd: float
    timestamp_utc: str
    detector_id: int
    band_name: str
    wavelength_um: float
    wavelength_fwhm_um: float
    ra_deg: float
    dec_deg: float
    pixel_scale_arcsec: float = NOMINAL_PIXEL_SCALE_ARCSEC
    flux_unit: str = "MJy/sr"
    exposure_time_s: float = 120.0
    data_release: str = "DR1"
    frame_quality_flags: int = QualityFlag.GOOD
    additional_metadata: Dict[str, Any] = field(default_factory=dict)
    raw_flags: Optional[np.ndarray] = None

    def __post_init__(self) -> None:
        """Validate array dimensions, types, and physical limits."""
        self.validate()

    def validate(self) -> None:
        """
        Ensures the frame meets rigorous scientific and structural integrity rules.
        Raises ValueError if any contract rule is violated.
        """
        # 1. Check array types and dimensions
        for name, arr in [("data", self.data), ("uncertainty", self.uncertainty), ("mask", self.mask)]:
            if not isinstance(arr, np.ndarray):
                raise TypeError(f"Frame {self.frame_id}: '{name}' must be a numpy.ndarray, got {type(arr)}")
            if arr.ndim != 2:
                raise ValueError(f"Frame {self.frame_id}: '{name}' must be a 2D array, got shape {arr.shape}")

        # Validate raw_flags if present
        if self.raw_flags is not None:
            if not isinstance(self.raw_flags, np.ndarray):
                raise TypeError(f"Frame {self.frame_id}: 'raw_flags' must be a numpy.ndarray, got {type(self.raw_flags)}")
            if self.raw_flags.shape != self.data.shape:
                raise ValueError(
                    f"Shape mismatch: 'data' is {self.data.shape} but 'raw_flags' is {self.raw_flags.shape}"
                )

        # 2. Check shape consistency across data, uncertainty, and mask
        if self.data.shape != self.uncertainty.shape:
            raise ValueError(
                f"Shape mismatch: 'data' is {self.data.shape} but 'uncertainty' is {self.uncertainty.shape}"
            )
        if self.data.shape != self.mask.shape:
            raise ValueError(
                f"Shape mismatch: 'data' is {self.data.shape} but 'mask' is {self.mask.shape}"
            )

        # 3. Check detector ID validity (SPHEREx has exactly 6 detectors)
        if self.detector_id not in SPHEREX_DETECTOR_BANDS:
            raise ValueError(
                f"Invalid detector_id={self.detector_id}. SPHEREx has detectors 1 through 6."
            )

        # 4. Check wavelength validity against detector physical bandpass
        min_wl, max_wl = SPHEREX_DETECTOR_BANDS[self.detector_id]
        tolerance = 0.10  # Allow 100nm margin for filter edge transitions
        if not ((min_wl - tolerance) <= self.wavelength_um <= (max_wl + tolerance)):
            raise ValueError(
                f"Wavelength {self.wavelength_um:.3f} um is incompatible with "
                f"Detector {self.detector_id} nominal range [{min_wl}, {max_wl}] um"
            )

        # 5. Check coordinates
        if not (0.0 <= self.ra_deg <= 360.0):
            raise ValueError(f"RA must be in [0, 360] degrees, got {self.ra_deg}")
        if not (-90.0 <= self.dec_deg <= 90.0):
            raise ValueError(f"Dec must be in [-90, 90] degrees, got {self.dec_deg}")

    @property
    def shape(self) -> Tuple[int, int]:
        """Return (ny, nx) pixel dimensions of cutout."""
        return self.data.shape

    @property
    def pixel_solid_angle_sr(self) -> float:
        """
        Compute pixel solid angle in steradians:
        Omega_pix = (theta_arcsec * (pi / (180 * 3600)))^2
        For 6.2 arcsec, Omega_pix ~ 9.043e-10 steradians.
        """
        rad_per_arcsec = np.pi / (180.0 * 3600.0)
        pixel_scale_rad = self.pixel_scale_arcsec * rad_per_arcsec
        return float(pixel_scale_rad ** 2)


# -----------------------------------------------------------------------------
# Structured Output Model: SpectrumResult (Member 3 -> Member 1 / Frontend)
# -----------------------------------------------------------------------------
@dataclass
class SpectrumResult:
    """
    Extracted 1D spectrum across SPHEREx detectors and wavelengths.
    This structured object is JSON-serializable for the web frontend.

    Astrophysical Definitions:
    --------------------------
    - `wavelengths_um`: Central wavelengths for each spectral channel.
    - `fluxes_uJy`: Extracted aperture flux density in microJanskys (1 uJy = 1e-29 erg/s/cm^2/Hz).
    - `flux_errors_uJy`: 1-sigma photometric uncertainty including background variance.
    - `detectors`: Detector index (1-6) corresponding to each measurement.
    - `snr`: Signal-to-Noise Ratio (fluxes_uJy / flux_errors_uJy).
    - `quality_flags`: Array of integer bitwise flags for each point.
    - `missing_detectors`: List of detector IDs (1-6) without valid data.
    """
    target_name: str
    ra_deg: float
    dec_deg: float
    wavelengths_um: List[float]
    fluxes_uJy: List[float]
    flux_errors_uJy: List[float]
    detectors: List[int]
    snr: List[float]
    quality_flags: List[int]
    missing_detectors: List[int]
    aperture_radius_pix: float
    annulus_radii_pix: Tuple[float, float]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to clean JSON-serializable dictionary for frontend consumption."""
        return asdict(self)


# -----------------------------------------------------------------------------
# Structured Output Model: LightCurveResult (Member 3 -> Member 1 / Frontend)
# -----------------------------------------------------------------------------
@dataclass
class LightCurveResult:
    """
    Extracted time-domain photometric light curve for a single astronomical source.
    Supports monitoring variable stars (e.g., RW Aurigae, R Draconis) over time.

    Astrophysical Definitions:
    --------------------------
    - `mjd`: Modified Julian Date of mid-exposure (chronologically sorted).
    - `timestamps_utc`: Human-readable ISO-8601 observation date/time.
    - `fluxes_uJy`: Aperture-extracted flux density in microJanskys.
    - `flux_errors_uJy`: 1-sigma photometric uncertainty.
    - `ab_magnitudes`: AB magnitude: m_AB = -2.5 * log10(F_Jy / 3631.0)
    - `ab_mag_errors`: 1-sigma magnitude error: sigma_m = 2.5 / ln(10) * (sigma_F / F)
    - `is_saturated`: True if source peak pixel triggered detector saturation limit.
    - `quality_flags`: Quality bitmask per epoch.
    """
    target_name: str
    ra_deg: float
    dec_deg: float
    detector_id: int
    central_wavelength_um: float
    mjd: List[float]
    timestamps_utc: List[str]
    fluxes_uJy: List[float]
    flux_errors_uJy: List[float]
    ab_magnitudes: List[float]
    ab_mag_errors: List[float]
    is_saturated: List[bool]
    quality_flags: List[int]
    aperture_radius_pix: float
    annulus_radii_pix: Tuple[float, float]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to clean JSON-serializable dictionary for frontend consumption."""
        return asdict(self)


# -----------------------------------------------------------------------------
# Synthetic Cutout Generator (For Testing & Validation)
# -----------------------------------------------------------------------------
def create_synthetic_cutout(
    detector_id: int,
    wavelength_um: float,
    flux_uJy: float,
    cutout_size: int = 21,
    background_level_mjy_sr: float = 0.5,
    noise_sigma_mjy_sr: float = 0.05,
    source_offset_pix: Tuple[float, float] = (0.0, 0.0),
    psf_fwhm_pix: float = 1.0,
    mjd: float = 60800.0,
    timestamp_utc: str = "2025-06-01T00:00:00.000",
    frame_id: str = "synth_001",
    target_name: str = "SYNTH_SRC",
    ra_deg: float = 120.0,
    dec_deg: float = 30.0,
    simulate_saturation: bool = False,
    saturation_threshold_mjy_sr: float = 50.0,
    random_seed: Optional[int] = None,
) -> SPHERExFrame:
    """
    Creates a mathematically realistic synthetic SPHEREx 2D image cutout containing:
    1. A 2D Gaussian Point Spread Function (PSF) representing a stellar or point source.
    2. Uniform background sky emission.
    3. Poisson and Gaussian readout noise.
    4. Bitwise quality flags (saturation, bad pixels).

    Teaching Note on PSF Mathematics:
    ---------------------------------
    A 2D circular Gaussian PSF is given by:
        G(x, y) = A * exp( - ( (x - x0)^2 + (y - y0)^2 ) / (2 * sigma^2) )
    where:
        sigma = FWHM / (2 * sqrt(2 * ln(2))) ~ FWHM / 2.35482
    The total volume of the Gaussian is 2 * pi * A * sigma^2, which equals the total
    integrated source flux.
    """
    if detector_id not in SPHEREX_DETECTOR_BANDS:
        raise ValueError(f"detector_id must be 1-6, got {detector_id}")

    # Pixel coordinate grid
    y, x = np.mgrid[0:cutout_size, 0:cutout_size]
    x_center = (cutout_size - 1) / 2.0 + source_offset_pix[0]
    y_center = (cutout_size - 1) / 2.0 + source_offset_pix[1]

    # Convert FWHM to Gaussian standard deviation sigma
    sigma_pix = psf_fwhm_pix / (2.0 * np.sqrt(2.0 * np.log(2.0)))

    # Solid angle of one SPHEREx pixel (6.2 arcsec x 6.2 arcsec)
    rad_per_arcsec = np.pi / (180.0 * 3600.0)
    omega_pix_sr = (NOMINAL_PIXEL_SCALE_ARCSEC * rad_per_arcsec) ** 2

    # Convert source flux (uJy) to total flux in MJy:
    # 1 uJy = 1e-12 MJy
    total_flux_mjy = flux_uJy * 1e-12

    # Convert total flux in MJy to surface brightness in MJy/sr:
    # Surface brightness integral over solid angle equals total flux.
    # Total sum of pixels * omega_pix_sr = total_flux_mjy
    # Therefore, sum of pixel values = total_flux_mjy / omega_pix_sr
    total_pixel_sum = total_flux_mjy / omega_pix_sr

    # Generate source 2D Gaussian profile
    r_sq = (x - x_center) ** 2 + (y - y_center) ** 2
    raw_profile = np.exp(-0.5 * r_sq / (sigma_pix ** 2))

    # Normalize discrete pixel sum to match total_pixel_sum exactly
    profile_sum = np.sum(raw_profile)
    if profile_sum > 0:
        source_profile = (raw_profile / profile_sum) * total_pixel_sum
    else:
        source_profile = raw_profile

    # Add background emission and Gaussian random noise
    seed = random_seed if random_seed is not None else (int(abs(flux_uJy) * 100) % 2**32)
    rng = np.random.default_rng(seed=seed)
    noise = rng.normal(loc=0.0, scale=noise_sigma_mjy_sr, size=(cutout_size, cutout_size))
    data = source_profile + background_level_mjy_sr + noise

    # Uncertainty map (1-sigma error per pixel)
    uncertainty = np.full((cutout_size, cutout_size), noise_sigma_mjy_sr, dtype=np.float64)

    # Pixel bitmask (using int32 for standard FITS/astropy bitflag compatibility)
    mask = np.zeros((cutout_size, cutout_size), dtype=np.int32)

    # Simulate saturation if peak pixel exceeds linear threshold
    if simulate_saturation or np.max(data) >= saturation_threshold_mjy_sr:
        sat_indices = data >= saturation_threshold_mjy_sr
        mask[sat_indices] |= int(QualityFlag.SATURATED)
        data[sat_indices] = saturation_threshold_mjy_sr

    min_wl, max_wl = SPHEREX_DETECTOR_BANDS[detector_id]
    fwhm_wl = (max_wl - min_wl) / 17.0  # ~17 spectral steps per band

    return SPHERExFrame(
        data=data,
        uncertainty=uncertainty,
        mask=mask,
        frame_id=frame_id,
        mjd=mjd,
        timestamp_utc=timestamp_utc,
        detector_id=detector_id,
        band_name=f"SPHEREx_Det{detector_id}",
        wavelength_um=wavelength_um,
        wavelength_fwhm_um=fwhm_wl,
        ra_deg=ra_deg,
        dec_deg=dec_deg,
        pixel_scale_arcsec=NOMINAL_PIXEL_SCALE_ARCSEC,
        flux_unit="MJy/sr",
        exposure_time_s=120.0,
        data_release="SIMULATED_2026",
        frame_quality_flags=QualityFlag.GOOD,
        additional_metadata={"simulated": True, "true_flux_uJy": flux_uJy},
    )
