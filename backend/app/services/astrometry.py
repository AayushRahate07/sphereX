"""Astrometry and Coordinate Propagation Service.

Handles epoch-dependent proper motion and annual parallax propagation for
high-proper-motion targets (e.g., WISE 0855) to ensure accurate cutout framing
and apparent motion preservation across SPHEREx observation epochs.
"""

import logging
from typing import Optional, Tuple, Union
import numpy as np
from astropy.coordinates import get_body_barycentric
from astropy.time import Time
import astropy.units as u

from backend.app.config import AstrometryConfig, TARGET_PRESETS

logger = logging.getLogger(__name__)


def get_target_astrometry(
    ra: float,
    dec: float,
    name: Optional[str] = None,
    tolerance: float = 0.01,
) -> Optional[AstrometryConfig]:
    """Retrieve verified AstrometryConfig for a target if available.

    Matches by canonical preset name or reference coordinates within tolerance.
    """
    for preset in TARGET_PRESETS:
        preset_astro = preset.get("astrometry")
        if not preset_astro or not isinstance(preset_astro, AstrometryConfig):
            continue

        if name and str(preset.get("name", "")).strip().lower() == name.strip().lower():
            return preset_astro

        preset_ra = float(preset["ra"])
        preset_dec = float(preset["dec"])
        if abs(ra - preset_ra) < tolerance and abs(dec - preset_dec) < tolerance:
            return preset_astro

    return None


def _parse_time_input(epoch: Union[float, str, Time]) -> Time:
    """Normalize input epoch into an Astropy Time object."""
    if isinstance(epoch, Time):
        return epoch
    if isinstance(epoch, (int, float)):
        # Treat numeric floats > 30000 as MJD, otherwise decimal year
        if epoch > 30000.0:
            return Time(float(epoch), format="mjd", scale="utc")
        return Time(float(epoch), format="decimalyear", scale="utc")
    # String input: attempt isot/iso parsing
    return Time(str(epoch), scale="utc")


def propagate_coordinates_to_epoch(
    ra: float,
    dec: float,
    epoch: Union[float, str, Time],
    target_name: Optional[str] = None,
    include_parallax: bool = True,
) -> Tuple[float, float]:
    """Propagate target sky coordinates to a specific observation epoch.

    If the target has verified astrometric metadata (proper motion and parallax),
    propagates position from the reference epoch to the target epoch, accounting for
    both linear proper motion and Earth-orbit parallax reflex motion.

    For arbitrary sky coordinates without verified astrometry, returns the input
    coordinates unchanged.

    Args:
        ra: Reference Right Ascension in decimal degrees.
        dec: Reference Declination in decimal degrees.
        epoch: Target observation epoch (MJD, decimal year, or Time object).
        target_name: Optional preset target name hint (e.g. 'WISE 0855').
        include_parallax: Whether to include annual parallax reflex vector (default: True).

    Returns:
        Tuple of (propagated_ra, propagated_dec) in decimal degrees.
    """
    astro = get_target_astrometry(ra, dec, name=target_name)
    if astro is None:
        return ra, dec

    target_time = _parse_time_input(epoch)
    ref_time = Time(astro.reference_epoch, format="decimalyear", scale="utc")

    # Elapsed time in Julian years
    dt_yr = (target_time - ref_time).to(u.yr).value
    cos_dec = np.cos(np.radians(astro.reference_dec))
    if abs(cos_dec) < 1e-6:
        cos_dec = 1e-6

    # 1. Linear Proper Motion Displacement
    # pm_ra_cosdec is in mas/yr -> convert to degrees
    dra_pm_deg = (astro.pm_ra_cosdec * 1e-3 * dt_yr) / cos_dec / 3600.0
    ddec_pm_deg = (astro.pm_dec * 1e-3 * dt_yr) / 3600.0

    ra_propagated = astro.reference_ra + dra_pm_deg
    dec_propagated = astro.reference_dec + ddec_pm_deg

    # 2. Annual Parallax Reflex Vector from Earth's Barycentric Orbit
    if include_parallax and astro.parallax_mas > 0.0:
        try:
            r_earth = get_body_barycentric("earth", target_time).xyz.to(u.AU).value
            ra_rad = np.radians(astro.reference_ra)
            dec_rad = np.radians(astro.reference_dec)

            # Local celestial unit vectors
            u_east = np.array([-np.sin(ra_rad), np.cos(ra_rad), 0.0])
            u_north = np.array([
                -np.sin(dec_rad) * np.cos(ra_rad),
                -np.sin(dec_rad) * np.sin(ra_rad),
                np.cos(dec_rad),
            ])

            plx_arcsec = astro.parallax_mas * 1e-3
            plx_ra_deg = (-plx_arcsec * np.dot(r_earth, u_east) / 3600.0) / cos_dec
            plx_dec_deg = (-plx_arcsec * np.dot(r_earth, u_north) / 3600.0)

            ra_propagated += plx_ra_deg
            dec_propagated += plx_dec_deg
        except Exception as exc:
            logger.warning("Could not compute barycentric parallax for %s at %s: %s", target_name, epoch, exc)

    return float(ra_propagated), float(dec_propagated)
