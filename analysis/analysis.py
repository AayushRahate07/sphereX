"""
SPHEREx Sky Viewer — Member 3 Core Analysis Module
==================================================
Implements:
1. `extract_spectrum`: Multi-detector aperture photometry, cross-calibration checks,
   missing-detector handling, and 1D spectrum synthesis across 0.75 to 5.0 um.
2. `plot_spectrum`: Publication-grade spectrum visualization with 6-detector band
   shading, error bars, and quality flag indicators.
3. `extract_light_curve`: Time-series photometry (interface ready for Stage 4).

Astrophysical Principles:
-------------------------
- SPHEREx synthesizes spectra across 6 distinct Linear Variable Filter detector arrays.
- Never combine measurements across different detectors without verifying photometric
  calibration compatibility and unit consistency.
- Missing detector bands must be cleanly documented, never interpolated without flags.
"""

from __future__ import annotations
from typing import Dict, List, Optional, Tuple, Union
import numpy as np
import matplotlib
matplotlib.use("Agg")  # Headless rendering for web and server environments
import matplotlib.pyplot as plt

from data_models import (
    SPHERExFrame,
    SpectrumResult,
    LightCurveResult,
    QualityFlag,
    SPHEREX_DETECTOR_BANDS,
    NOMINAL_PIXEL_SCALE_ARCSEC,
)
from photometry import measure_aperture_photometry, PhotometryMeasurement


# Subtle pastel colors for shading each of the 6 SPHEREx detector bands
DETECTOR_PALETTE: Dict[int, str] = {
    1: "#4a90e2",  # Det 1 (0.75 - 1.11 um): Blue
    2: "#50e3c2",  # Det 2 (1.11 - 1.64 um): Teal
    3: "#b8e986",  # Det 3 (1.64 - 2.42 um): Light Green
    4: "#f5a623",  # Det 4 (2.42 - 3.82 um): Amber
    5: "#e96443",  # Det 5 (3.82 - 4.42 um): Coral
    6: "#9013fe",  # Det 6 (4.42 - 5.00 um): Violet
}


def extract_spectrum(
    cutouts: List[SPHERExFrame],
    target_ra: float,
    target_dec: float,
    aperture_radius_pix: float = 2.5,
    annulus_inner_pix: float = 4.0,
    annulus_outer_pix: float = 6.0,
    enforce_calibration_consistency: bool = True,
    target_name: str = "Unknown_Target",
) -> SpectrumResult:
    """
    Extract a calibrated 1D spectrum across all 6 SPHEREx detectors.

    Parameters:
    -----------
    cutouts : List[SPHERExFrame]
        Collection of standardized cutout frames covering the target.
    target_ra : float
        Target Right Ascension in J2000 degrees.
    target_dec : float
        Target Declination in J2000 degrees.
    aperture_radius_pix : float, default 2.5
        Radius of circular aperture in pixels.
    annulus_inner_pix : float, default 4.0
        Inner radius of the background annulus in pixels.
    annulus_outer_pix : float, default 6.0
        Outer radius of the background annulus in pixels.
    enforce_calibration_consistency : bool, default True
        If True, validates that flux units and calibration scales are consistent
        before combining across different detector arrays.
    target_name : str, default "Unknown_Target"
        Identifier for the target (e.g., 'WISE_0855', 'Barnards_Star').

    Returns:
    --------
    SpectrumResult
        Structured dataclass containing sorted wavelengths, fluxes (uJy),
        uncertainties, detector IDs, SNR, bitwise flags, and missing detectors.
    """
    if not cutouts:
        raise ValueError("Cannot extract spectrum: 'cutouts' list is empty.")

    # 1. Cross-Detector Calibration & Compatibility Verification
    # SPHEREx rule: Never combine measurements from different detectors without checking
    # their calibration and compatibility!
    units = {f.flux_unit for f in cutouts}
    if len(units) > 1:
        msg = (
            f"Cross-detector calibration mismatch: Found conflicting flux units {units} "
            f"across cutouts for target '{target_name}'. Cannot combine without calibration standardisation."
        )
        if enforce_calibration_consistency:
            raise ValueError(msg)

    releases = {f.data_release for f in cutouts}
    has_mixed_releases = len(releases) > 1

    # 2. Photometric Extraction per Frame
    wavelengths: List[float] = []
    fluxes_uJy: List[float] = []
    flux_errors_uJy: List[float] = []
    detector_ids: List[int] = []
    snrs: List[float] = []
    quality_flags: List[int] = []

    for frame in cutouts:
        meas = measure_aperture_photometry(
            frame=frame,
            center_xy=None,  # Use cutout center
            aperture_radius_pix=aperture_radius_pix,
            annulus_inner_pix=annulus_inner_pix,
            annulus_outer_pix=annulus_outer_pix,
        )

        pt_flag = meas.quality_flags
        if has_mixed_releases:
            pt_flag |= int(QualityFlag.CALIBRATION_WARN)

        wavelengths.append(float(frame.wavelength_um))
        fluxes_uJy.append(float(meas.flux_uJy))
        flux_errors_uJy.append(float(meas.flux_err_uJy))
        detector_ids.append(int(frame.detector_id))
        snrs.append(float(meas.snr))
        quality_flags.append(int(pt_flag))

    # 3. Sort Chronologically by Wavelength (lambda_0)
    sort_order = np.argsort(wavelengths)
    sorted_wl = [wavelengths[i] for i in sort_order]
    sorted_fluxes = [fluxes_uJy[i] for i in sort_order]
    sorted_errors = [flux_errors_uJy[i] for i in sort_order]
    sorted_dets = [detector_ids[i] for i in sort_order]
    sorted_snr = [snrs[i] for i in sort_order]
    sorted_flags = [quality_flags[i] for i in sort_order]

    # 4. Identify Missing Detectors (1 through 6)
    all_detectors = set(SPHEREX_DETECTOR_BANDS.keys())
    observed_detectors = set(sorted_dets)
    missing_detectors = sorted(list(all_detectors - observed_detectors))

    # 5. Compile Rich Metadata
    det_counts = {det: sorted_dets.count(det) for det in all_detectors}
    valid_snr = [s for s, fl in zip(sorted_snr, sorted_fluxes) if np.isfinite(fl) and np.isfinite(s)]
    mean_snr = float(np.mean(valid_snr)) if valid_snr else 0.0

    metadata = {
        "total_channels": len(sorted_wl),
        "valid_channels": len(valid_snr),
        "rejected_channels": len(sorted_wl) - len(valid_snr),
        "observed_detectors": sorted(list(observed_detectors)),
        "detector_channel_counts": det_counts,
        "mean_snr": mean_snr,
        "flux_unit": list(units)[0] if units else "unknown",
        "data_releases": list(releases),
        "calibration_consistent": not has_mixed_releases and (len(units) == 1),
    }

    return SpectrumResult(
        target_name=target_name,
        ra_deg=target_ra,
        dec_deg=target_dec,
        wavelengths_um=sorted_wl,
        fluxes_uJy=sorted_fluxes,
        flux_errors_uJy=sorted_errors,
        detectors=sorted_dets,
        snr=sorted_snr,
        quality_flags=sorted_flags,
        missing_detectors=missing_detectors,
        aperture_radius_pix=aperture_radius_pix,
        annulus_radii_pix=(annulus_inner_pix, annulus_outer_pix),
        metadata=metadata,
    )


def plot_spectrum(
    spectrum: SpectrumResult,
    output_path: Optional[str] = None,
    show_bands: bool = True,
    title: Optional[str] = None,
) -> plt.Figure:
    """
    Generate a publication-grade scientific plot of the extracted SPHEREx spectrum.

    Features:
    ---------
    - Error bars for each spectral channel.
    - Shaded background regions for all 6 SPHEREx detector bands.
    - Visual markers distinguishing standard points from saturated / low-SNR channels.
    - Prominent banner alerting users if any detectors are missing.
    - IRSA / SPHEREx acknowledgement formatting.
    """
    fig, ax = plt.subplots(figsize=(10, 6), dpi=150)

    wl = np.array(spectrum.wavelengths_um)
    fl = np.array(spectrum.fluxes_uJy)
    err = np.array(spectrum.flux_errors_uJy)
    dets = np.array(spectrum.detectors)
    flags = np.array(spectrum.quality_flags)

    # 1. Shade the 6 SPHEREx detector bands along the x-axis
    if show_bands:
        for det_id, (min_l, max_l) in SPHEREX_DETECTOR_BANDS.items():
            color = DETECTOR_PALETTE.get(det_id, "#e0e0e0")
            is_observed = det_id not in spectrum.missing_detectors
            alpha = 0.12 if is_observed else 0.03
            ax.axvspan(min_l, max_l, color=color, alpha=alpha, label=f"Det {det_id} [{min_l}-{max_l} um]" if is_observed else None)
            
            # Label detector at top of band
            mid_l = (min_l + max_l) / 2.0
            status_text = f"Det {det_id}" if is_observed else f"Det {det_id}\n(Missing)"
            text_color = "#333333" if is_observed else "#999999"
            ax.text(mid_l, 0.94, status_text, transform=ax.get_xaxis_transform(),
                    ha="center", va="top", fontsize=8, color=text_color, weight="bold" if is_observed else "normal")

    # 2. Plot data points color-coded by detector
    for det_id in range(1, 7):
        mask = dets == det_id
        if not np.any(mask):
            continue

        color = DETECTOR_PALETTE.get(det_id, "#333333")
        # Standard good points (finite flux, no saturation, low SNR, or fatal defect)
        fatal_bits = int(QualityFlag.SATURATED | QualityFlag.LOW_SNR | QualityFlag.BAD_PIXEL | QualityFlag.COSMIC_RAY)
        good_mask = mask & np.isfinite(fl) & ((flags & fatal_bits) == 0)
        if np.any(good_mask):
            ax.errorbar(
                wl[good_mask],
                fl[good_mask],
                yerr=err[good_mask],
                fmt="o",
                color=color,
                ecolor=color,
                capsize=3,
                elinewidth=1.2,
                markersize=6,
                label=f"Detector {det_id} Data",
            )

        # Flagged points (e.g. Saturated or Low SNR) with finite flux
        flagged_mask = mask & np.isfinite(fl) & (~good_mask)
        if np.any(flagged_mask):
            ax.errorbar(
                wl[flagged_mask],
                fl[flagged_mask],
                yerr=err[flagged_mask],
                fmt="s",
                markerfacecolor="none",
                markeredgecolor="red",
                ecolor="red",
                capsize=3,
                elinewidth=1.0,
                markersize=7,
                label=f"Det {det_id} (Flagged)",
            )

    # 3. Connect spectrum with dashed line
    if len(wl) > 1:
        ax.plot(wl, fl, linestyle="--", color="#666666", alpha=0.5, linewidth=1.0, zorder=1)

    # 4. Labels and Title
    ax.set_xlabel(r"Central Wavelength $\lambda_0$ [$\mu\mathrm{m}$]", fontsize=11, fontweight="bold")
    ax.set_ylabel(r"Calibrated Flux Density $F_\nu$ [$\mu\mathrm{Jy}$]", fontsize=11, fontweight="bold")

    plot_title = title or f"SPHEREx Extracted Spectrum: {spectrum.target_name}"
    ax.set_title(plot_title, fontsize=13, fontweight="bold", pad=12)

    # Subtitle with coordinates and missing detector notice
    coord_text = f"RA: {spectrum.ra_deg:.3f} deg, Dec: {spectrum.dec_deg:.3f} deg | Aperture: r={spectrum.aperture_radius_pix} pix"
    if spectrum.missing_detectors:
        miss_str = ", ".join(f"Det {d}" for d in spectrum.missing_detectors)
        coord_text += f" | WARNING: Missing {miss_str}"
    ax.text(0.5, 1.01, coord_text, transform=ax.transAxes, ha="center", va="bottom", fontsize=8.5, color="#555555")

    ax.set_xlim(0.70, 5.05)
    ax.grid(True, linestyle=":", alpha=0.5)

    # 5. Clean Legend (avoid duplicates)
    handles, labels = ax.get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    ax.legend(by_label.values(), by_label.keys(), loc="upper right", fontsize=8, framealpha=0.9)

    plt.tight_layout()

    # 6. Save if output path requested
    if output_path:
        fig.savefig(output_path, dpi=200, bbox_inches="tight")
        print(f"Saved spectrum plot to: {output_path}")

    return fig


def extract_light_curve(
    cutouts: List[SPHERExFrame],
    target_ra: float,
    target_dec: float,
    detector_id: Optional[int] = None,
    wavelength_tolerance_um: float = 0.05,
    aperture_radius_pix: float = 2.5,
    annulus_inner_pix: float = 4.0,
    annulus_outer_pix: float = 6.0,
    target_name: str = "Unknown_Target",
) -> LightCurveResult:
    """
    Extract a time-series photometric light curve for variable or moving sources.

    Scientific Principle:
    ---------------------
    1. Filter cutouts by detector/bandpass to ensure identical central wavelength,
       preventing chromatic color-difference from masquerading as temporal variability.
    2. Chronologically sort mid-exposure timestamps by Modified Julian Date (MJD).
    3. Measure aperture flux and background per epoch.
    4. Compute astronomical AB magnitudes:
           m_AB = -2.5 * log10(F_uJy * 1e-6 / 3631.0)
           sigma_m = 1.08574 * (sigma_F / F)
    5. Detect saturated sources (peak pixel > linear limit) and flag them so
       analysts do not confuse detector clipping with true stellar maxima.
    6. Identify observation cadence gaps.

    Parameters:
    -----------
    cutouts : List[SPHERExFrame]
        Collection of time-series cutouts of the target across different epochs.
    target_ra : float
        Target Right Ascension in J2000 degrees.
    target_dec : float
        Target Declination in J2000 degrees.
    detector_id : Optional[int], default None
        Specific detector array (1..6) to isolate for the light curve.
        If None, the detector with the highest number of epochs is selected automatically.
    wavelength_tolerance_um : float, default 0.05
        Maximum permitted wavelength deviation between epochs in microns.
    aperture_radius_pix : float, default 2.5
        Radius of circular aperture in pixels.
    annulus_inner_pix : float, default 4.0
        Inner radius of the background annulus in pixels.
    annulus_outer_pix : float, default 6.0
        Outer radius of the background annulus in pixels.
    target_name : str, default "Unknown_Target"
        Identifier for the target (e.g., 'RW_Aur', 'R_Dra').

    Returns:
    --------
    LightCurveResult
        Structured dataclass containing MJD timestamps, fluxes, AB magnitudes,
        saturation flags, and quality masks.
    """
    if not cutouts:
        raise ValueError("Cannot extract light curve: 'cutouts' list is empty.")

    # 1. Select Detector / Band
    if detector_id is None:
        det_counts = {det: sum(1 for f in cutouts if f.detector_id == det) for det in range(1, 7)}
        detector_id = max(det_counts, key=det_counts.get)
        if det_counts[detector_id] == 0:
            raise ValueError("No valid detector observations found in cutouts.")

    # Filter frames for the selected detector
    det_cutouts = [f for f in cutouts if f.detector_id == detector_id]
    if not det_cutouts:
        raise ValueError(f"No cutouts found matching detector_id={detector_id} for target '{target_name}'.")

    # 2. Filter for consistent central wavelength within tolerance
    median_wl = float(np.median([f.wavelength_um for f in det_cutouts]))
    consistent_cutouts = [
        f for f in det_cutouts if abs(f.wavelength_um - median_wl) <= wavelength_tolerance_um
    ]
    if not consistent_cutouts:
        raise ValueError(
            f"No cutouts within wavelength tolerance {wavelength_tolerance_um} um of {median_wl:.3f} um."
        )

    # 3. Sort Chronologically by MJD
    sorted_cutouts = sorted(consistent_cutouts, key=lambda f: f.mjd)

    # 4. Measure Photometry per Epoch
    mjds: List[float] = []
    timestamps: List[str] = []
    fluxes: List[float] = []
    flux_errors: List[float] = []
    ab_mags: List[float] = []
    ab_mag_errs: List[float] = []
    is_saturated_list: List[bool] = []
    quality_flags: List[int] = []

    for frame in sorted_cutouts:
        meas = measure_aperture_photometry(
            frame=frame,
            center_xy=None,
            aperture_radius_pix=aperture_radius_pix,
            annulus_inner_pix=annulus_inner_pix,
            annulus_outer_pix=annulus_outer_pix,
        )

        f_uJy = float(meas.flux_uJy)
        f_err = float(meas.flux_err_uJy)
        flag = int(meas.quality_flags)
        is_sat = bool(meas.is_saturated)

        # Convert to AB magnitude: m_AB = -2.5 * log10(F_Jy / 3631.0)
        # F_Jy = f_uJy * 1e-6
        if not np.isfinite(f_uJy):
            # Measurement was rejected (e.g. bad pixels, missing data, edge artifact)
            ab_mag = float("nan")
            ab_err = float("nan")
            # Do NOT tag LOW_SNR on a rejected measurement; retain existing rejection flags
        elif f_uJy > 0:
            flux_jy = f_uJy * 1e-6
            ab_mag = float(-2.5 * np.log10(flux_jy / 3631.0))
            if np.isfinite(f_err) and f_err > 0:
                ab_err = float(1.08574 * (f_err / f_uJy))
            else:
                ab_err = float("nan")
        else:
            # Valid measurement with zero or negative flux after sky background subtraction
            ab_mag = float("nan")
            ab_err = float("nan")
            flag |= int(QualityFlag.LOW_SNR)

        if is_sat:
            flag |= int(QualityFlag.SATURATED)

        mjds.append(float(frame.mjd))
        timestamps.append(str(frame.timestamp_utc))
        fluxes.append(f_uJy)
        flux_errors.append(f_err)
        ab_mags.append(ab_mag)
        ab_mag_errs.append(ab_err)
        is_saturated_list.append(is_sat)
        quality_flags.append(flag)

    # 5. Temporal Cadence and Gap Analysis
    mjd_arr = np.array(mjds)
    diffs = np.diff(mjd_arr) if len(mjd_arr) > 1 else np.array([0.0])
    median_cadence = float(np.median(diffs)) if len(diffs) > 0 and len(mjd_arr) > 1 else 0.0

    # Flag large gaps (gap > 3x median cadence)
    gap_count = int(np.sum(diffs > (3.0 * median_cadence))) if median_cadence > 0 else 0

    valid_fluxes = [f for f in fluxes if np.isfinite(f)]
    valid_mags = [m for m in ab_mags if not np.isnan(m)]
    min_mag = float(np.min(valid_mags)) if valid_mags else float("nan")
    max_mag = float(np.max(valid_mags)) if valid_mags else float("nan")
    amplitude = float(max_mag - min_mag) if valid_mags else 0.0

    metadata = {
        "total_epochs": len(mjds),
        "valid_epoch_count": len(valid_fluxes),
        "rejected_epoch_count": len(fluxes) - len(valid_fluxes),
        "detector_id": detector_id,
        "central_wavelength_um": median_wl,
        "wavelength_tolerance_um": wavelength_tolerance_um,
        "time_span_days": float(mjd_arr[-1] - mjd_arr[0]) if len(mjd_arr) > 1 else 0.0,
        "median_cadence_days": median_cadence,
        "large_gap_count": gap_count,
        "saturated_epoch_count": sum(is_saturated_list),
        "min_mag_ab": min_mag,
        "max_mag_ab": max_mag,
        "peak_to_peak_amplitude_mag": amplitude,
    }

    return LightCurveResult(
        target_name=target_name,
        ra_deg=target_ra,
        dec_deg=target_dec,
        detector_id=detector_id,
        central_wavelength_um=median_wl,
        mjd=mjds,
        timestamps_utc=timestamps,
        fluxes_uJy=fluxes,
        flux_errors_uJy=flux_errors,
        ab_magnitudes=ab_mags,
        ab_mag_errors=ab_mag_errs,
        is_saturated=is_saturated_list,
        quality_flags=quality_flags,
        aperture_radius_pix=aperture_radius_pix,
        annulus_radii_pix=(annulus_inner_pix, annulus_outer_pix),
        metadata=metadata,
    )


def plot_light_curve(
    light_curve: LightCurveResult,
    output_path: Optional[str] = None,
    plot_type: str = "both",
    title: Optional[str] = None,
) -> plt.Figure:
    """
    Generate a publication-grade scientific plot of the extracted time-series light curve.

    Parameters:
    -----------
    light_curve : LightCurveResult
        The extracted light curve object.
    output_path : Optional[str]
        File path where the generated PNG should be saved.
    plot_type : str, default 'both'
        'both' for dual flux + magnitude panels, 'flux' for flux only, 'magnitude' for magnitude only.
    title : Optional[str]
        Custom title for the figure.
    """
    mjd = np.array(light_curve.mjd)
    fl = np.array(light_curve.fluxes_uJy)
    fl_err = np.array(light_curve.flux_errors_uJy)
    mag = np.array(light_curve.ab_magnitudes)
    mag_err = np.array(light_curve.ab_mag_errors)
    is_sat = np.array(light_curve.is_saturated)

    det_id = light_curve.detector_id
    color = DETECTOR_PALETTE.get(det_id, "#4a90e2")

    if plot_type == "both":
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True, dpi=150)
    else:
        fig, ax1 = plt.subplots(figsize=(10, 5), dpi=150)
        ax2 = None

    # Plot Flux Panel
    if plot_type in ["both", "flux"]:
        # Standard unflagged epochs
        good = ~is_sat
        if np.any(good):
            ax1.errorbar(
                mjd[good],
                fl[good],
                yerr=fl_err[good],
                fmt="o-",
                color=color,
                ecolor=color,
                capsize=3,
                elinewidth=1.2,
                markersize=6,
                label=f"Det {det_id} ({light_curve.central_wavelength_um:.2f} um)",
            )
        # Saturated epochs
        if np.any(is_sat):
            ax1.errorbar(
                mjd[is_sat],
                fl[is_sat],
                yerr=fl_err[is_sat],
                fmt="v",
                color="red",
                ecolor="red",
                capsize=3,
                markersize=8,
                label="Saturated (Lower Limit)",
            )

        ax1.set_ylabel(r"Flux Density $F_\nu$ [$\mu\mathrm{Jy}$]", fontsize=11, fontweight="bold")
        ax1.grid(True, linestyle=":", alpha=0.5)
        ax1.legend(loc="upper right", fontsize=8.5, framealpha=0.9)

        plot_title = title or f"SPHEREx Light Curve: {light_curve.target_name}"
        ax1.set_title(plot_title, fontsize=13, fontweight="bold", pad=12)

        subtitle = (
            f"Detector {det_id} | lambda_0 = {light_curve.central_wavelength_um:.2f} um | "
            f"Epochs: {len(mjd)} | Span: {light_curve.metadata.get('time_span_days', 0):.1f} days"
        )
        ax1.text(0.5, 1.01, subtitle, transform=ax1.transAxes, ha="center", va="bottom", fontsize=8.5, color="#555555")

    # Plot Magnitude Panel (Astronomical standard: inverted Y-axis so brighter is up!)
    mag_ax = ax2 if plot_type == "both" else (ax1 if plot_type == "magnitude" else None)
    if mag_ax is not None:
        valid = ~np.isnan(mag) & ~is_sat
        if np.any(valid):
            mag_ax.errorbar(
                mjd[valid],
                mag[valid],
                yerr=mag_err[valid],
                fmt="s-",
                color="#2c3e50",
                ecolor="#2c3e50",
                capsize=3,
                elinewidth=1.2,
                markersize=5,
                label="AB Magnitude",
            )
        if np.any(is_sat):
            sat_valid = ~np.isnan(mag) & is_sat
            if np.any(sat_valid):
                mag_ax.errorbar(
                    mjd[sat_valid],
                    mag[sat_valid],
                    yerr=mag_err[sat_valid],
                    fmt="v",
                    color="red",
                    ecolor="red",
                    capsize=3,
                    markersize=8,
                    label="Saturated (Upper limit on brightness)",
                )

        mag_ax.set_ylabel(r"Apparent AB Magnitude", fontsize=11, fontweight="bold")
        # Invert Y-axis for astronomical magnitude convention:
        mag_ax.invert_yaxis()
        mag_ax.grid(True, linestyle=":", alpha=0.5)
        mag_ax.legend(loc="upper right", fontsize=8.5, framealpha=0.9)

    bottom_ax = ax2 if plot_type == "both" else ax1
    bottom_ax.set_xlabel("Time [Modified Julian Date - MJD]", fontsize=11, fontweight="bold")

    plt.tight_layout()

    if output_path:
        fig.savefig(output_path, dpi=200, bbox_inches="tight")
        print(f"Saved light curve plot to: {output_path}")

    return fig


# -----------------------------------------------------------------------------
# Phase-Folding & Period Analysis
# -----------------------------------------------------------------------------
def phase_fold_light_curve(
    mjds: List[float],
    fluxes: List[float],
    errors: List[float],
    period_days: float,
    t0: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Phase-fold time-series astronomical observations using a specified variability period.

    Mathematical Formulation:
    --------------------------
    phi = ((t - t0) / period) mod 1.0

    To ensure visual continuity for periodic astrophysical phenomena (e.g., pulsating
    Mira variables, eclipsing binaries, stellar rotation), data are repeated across two
    complete cycles: phi in [0.0, 2.0).

    Parameters:
    -----------
    mjds : List[float]
        Observation epochs in Modified Julian Date.
    fluxes : List[float]
        Calibrated flux densities in microJanskys (uJy).
    errors : List[float]
        1-sigma photometric uncertainties.
    period_days : float
        Variability period in days (must be > 0).
    t0 : float, optional
        Reference epoch for zero phase (default: minimum MJD).

    Returns:
    --------
    Dict[str, Any] containing 1-cycle and 2-cycle phase-folded arrays.
    """
    if period_days <= 0:
        raise ValueError(f"period_days must be positive, got {period_days}")

    mjd_arr = np.asarray(mjds, dtype=np.float64)
    flx_arr = np.asarray(fluxes, dtype=np.float64)
    err_arr = np.asarray(errors, dtype=np.float64)

    ref_t0 = float(np.min(mjd_arr)) if t0 is None else float(t0)

    # 1. Compute normalized phase in [0, 1)
    phases_1cyc = np.mod((mjd_arr - ref_t0) / period_days, 1.0)

    # 2. Duplicate across 2 cycles [0, 2) for standard astronomical visual continuity
    phases_2cyc = np.concatenate([phases_1cyc, phases_1cyc + 1.0])
    fluxes_2cyc = np.concatenate([flx_arr, flx_arr])
    errors_2cyc = np.concatenate([err_arr, err_arr])

    # 3. Sort by phase
    sort_idx = np.argsort(phases_2cyc)
    phases_2cyc = phases_2cyc[sort_idx]
    fluxes_2cyc = fluxes_2cyc[sort_idx]
    errors_2cyc = errors_2cyc[sort_idx]

    return {
        "period_days": float(period_days),
        "t0_mjd": ref_t0,
        "phases_1cyc": phases_1cyc.tolist(),
        "phases_2cyc": phases_2cyc.tolist(),
        "fluxes_2cyc": fluxes_2cyc.tolist(),
        "errors_2cyc": errors_2cyc.tolist(),
    }


def plot_phase_folded_light_curve(
    light_curve: LightCurveResult,
    period_days: float,
    output_path: Optional[str] = None,
    title: Optional[str] = None,
) -> plt.Figure:
    """
    Generate a publication-grade diagnostic plot displaying both:
    1. Raw observed light curve vs MJD (top panel).
    2. Phase-folded light curve over 2 full cycles (phi in [0, 2)) with smooth model curve (bottom panel).
    """
    fold_data = phase_fold_light_curve(
        mjds=light_curve.mjd,
        fluxes=light_curve.fluxes_uJy,
        errors=light_curve.flux_errors_uJy,
        period_days=period_days,
    )

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), dpi=150, facecolor="#0e1117")

    fig_title = title or f"SPHEREx Time-Series & Phase-Folded Light Curve — {light_curve.target_name}"
    fig.suptitle(fig_title, fontsize=13, fontweight="bold", color="white", y=0.98)

    # Top Panel: Raw Time-Series
    ax1.set_facecolor("#161b22")
    ax1.errorbar(
        light_curve.mjd,
        light_curve.fluxes_uJy,
        yerr=light_curve.flux_errors_uJy,
        fmt="o",
        color="#50e3c2",
        ecolor="#50e3c2",
        elinewidth=1.2,
        capsize=3,
        markersize=6,
        label=f"Observed Flux ({light_curve.central_wavelength_um:.2f} um)",
    )
    ax1.set_ylabel(r"Flux Density $F_\nu$ [$\mu$Jy]", color="white", fontsize=11)
    ax1.set_xlabel("Time [Modified Julian Date - MJD]", color="white", fontsize=10)
    ax1.tick_params(colors="white")
    ax1.grid(True, linestyle=":", alpha=0.3, color="#8b949e")
    ax1.legend(loc="upper right", facecolor="#1e222d", edgecolor="none", labelcolor="white", fontsize=9)
    ax1.set_title("Observed Time-Series Photometry", color="#50e3c2", fontsize=11)

    # Bottom Panel: Phase-Folded Light Curve (2 cycles: 0 to 2)
    ax2.set_facecolor("#161b22")
    ph = np.array(fold_data["phases_2cyc"])
    fl = np.array(fold_data["fluxes_2cyc"])
    er = np.array(fold_data["errors_2cyc"])

    # Cycle 1 points
    c1 = ph < 1.0
    ax2.errorbar(
        ph[c1],
        fl[c1],
        yerr=er[c1],
        fmt="o",
        color="#f5a623",
        ecolor="#f5a623",
        elinewidth=1.4,
        capsize=3,
        markersize=7,
        label="Phase Cycle 1 (0.0 - 1.0)",
    )
    # Cycle 2 points (duplicate for visual continuity)
    c2 = ph >= 1.0
    ax2.errorbar(
        ph[c2],
        fl[c2],
        yerr=er[c2],
        fmt="s",
        color="#b8e986",
        ecolor="#b8e986",
        elinewidth=1.2,
        capsize=3,
        markersize=6,
        alpha=0.75,
        label="Phase Cycle 2 (1.0 - 2.0 repeated)",
    )

    # Smooth sinusoidal guide curve
    phase_grid = np.linspace(0.0, 2.0, 200)
    mean_f = np.mean(light_curve.fluxes_uJy)
    amp_f = (np.max(light_curve.fluxes_uJy) - np.min(light_curve.fluxes_uJy)) / 2.0
    smooth_curve = mean_f + amp_f * np.sin(2 * np.pi * phase_grid)
    ax2.plot(phase_grid, smooth_curve, "--", color="#ff79c6", lw=1.5, alpha=0.7, label=f"Periodic Model (P = {period_days:.2f} d)")

    # Vertical cycle separator line at phase 1.0
    ax2.axvline(1.0, color="#8b949e", linestyle=":", lw=1.2, alpha=0.7)

    ax2.set_ylabel(r"Flux Density $F_\nu$ [$\mu$Jy]", color="white", fontsize=11)
    ax2.set_xlabel(f"Orbital / Pulsational Phase [Cycle 0 to 2, Period = {period_days:.2f} days]", color="white", fontsize=10)
    ax2.set_xlim(-0.05, 2.05)
    ax2.tick_params(colors="white")
    ax2.grid(True, linestyle=":", alpha=0.3, color="#8b949e")
    ax2.legend(loc="upper right", facecolor="#1e222d", edgecolor="none", labelcolor="white", fontsize=9)
    ax2.set_title(f"Phase-Folded Light Curve (Period P = {period_days:.2f} days, T0 = {fold_data['t0_mjd']:.1f} MJD)", color="#f5a623", fontsize=11)

    plt.tight_layout()
    if output_path:
        fig.savefig(str(output_path), dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
        print(f"Saved phase-folded light curve plot to: {output_path}")

    return fig

