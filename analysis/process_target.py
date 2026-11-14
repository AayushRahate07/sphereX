"""
SPHEREx Sky Viewer — Member 3 User Target Processing Pipeline
============================================================
Allows the user to enter celestial coordinates (RA, Dec in decimal degrees or
sexagesimal notation) or choose from NASA Space Apps 2026 challenge targets,
extract cutouts from SPHEREx FITS observations using Astropy WCS and Cutout2D,
and execute the full scientific analysis suite with user-customizable parameters:

Custom User Inputs:
-------------------
1. Celestial Coordinates: (RA, Dec) in decimal degrees or sexagesimal notation.
2. Filter / Band Selection: Any combination of the 6 SPHEREx detector bands (0.75 - 5.0 um).
3. FITS Inspection Display: Multi-panel visual diagnostic with aperture & sky annulus contours.
4. Frame Stacking Parameters: Stacking method (weighted_mean/median/mean), frame count, sigma clipping, alignment.
5. Variability Period: Pulsation/rotation period in days for light curve phase folding.

Mandatory Attribution:
----------------------
This research has made use of data products from the SPHEREx mission, distributed
by the NASA/IPAC Infrared Science Archive (IRSA).
"""

from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from data_models import (
    SPHERExFrame,
    SpectrumResult,
    LightCurveResult,
    QualityFlag,
    SPHEREX_DETECTOR_BANDS,
    NOMINAL_PIXEL_SCALE_ARCSEC,
)
from fits_loader import (
    parse_coordinates,
    load_cutout_from_fits,
    generate_spherex_survey_for_target,
    plot_fits_inspection,
)
from analysis import (
    extract_spectrum,
    plot_spectrum,
    extract_light_curve,
    plot_light_curve,
    phase_fold_light_curve,
    plot_phase_folded_light_curve,
)
from stacking import stack_frames
from photometry import measure_aperture_photometry
from target_validation import TARGET_DATABASE


# -----------------------------------------------------------------------------
# Interactive User Configuration Wizard
# -----------------------------------------------------------------------------
def prompt_user_for_target() -> Dict[str, Any]:
    """
    Interactively prompt the user for target coordinates, detector bands,
    FITS inspection, stacking settings, and variability period.

    Returns:
    --------
    Dict[str, Any] containing all user-configured parameters.
    """
    print("\n" + "=" * 76)
    print("  SPHEREx Sky Viewer — Target Selection & Analysis Wizard")
    print("=" * 76)
    print("Step 1: Select a target preset or enter custom celestial coordinates (J2000):")
    print("-" * 76)
    print("  [1] WISE 0855        (RA=133.790 deg, Dec=-7.240 deg)  - Cold Brown Dwarf")
    print("  [2] Barnard's Star   (RA=269.452 deg, Dec=+4.693 deg)  - High Proper Motion")
    print("  [3] Epsilon Indi B   (RA=330.840 deg, Dec=-56.790 deg) - T-dwarf Binary")
    print("  [4] RW Aurigae       (RA=77.108 deg,  Dec=+30.402 deg) - Variable Young Star")
    print("  [5] R Draconis       (RA=248.370 deg, Dec=+66.702 deg) - Mira Pulsating Giant")
    print("  [C] Custom Coordinates (Enter decimal degrees or sexagesimal)")
    print("-" * 76)

    choice = input("Enter choice [1-5 or C, default: 1]: ").strip()
    if not choice:
        choice = "1"

    preset_map = {
        "1": ("WISE_0855", "WISE J085510.83-071442.5", None),
        "2": ("BARNARD_STAR", "Barnard's Star", None),
        "3": ("EPSILON_INDI_B", "Epsilon Indi B", None),
        "4": ("RW_AUR", "RW Aurigae", 2.77),
        "5": ("R_DRA", "R Draconis", 245.0),
    }

    default_period = None
    if choice in preset_map:
        key, name, default_period = preset_map[choice]
        prof = TARGET_DATABASE[key]
        ra_deg, dec_deg = prof.ra_deg, prof.dec_deg
        target_name = name
    else:
        coord_input = input("Enter coordinates (e.g., '133.790 -7.240' or '08h55m09.6s -07d14m24s'): ").strip()
        custom_name = input("Enter target name [default: Custom_Target]: ").strip()
        if not custom_name:
            custom_name = "Custom_Target"
        ra_deg, dec_deg, _ = parse_coordinates(coord_input)
        target_name = custom_name

    # Step 2: Processing Mode
    print("\nStep 2: Select Processing Mode:")
    print("  [1] Full Spectrum (Extract across Detectors 1-6)")
    print("  [2] Time-Series Light Curve (Variable photometry & period phase-folding)")
    print("  [3] Frame Stacking & Coaddition (SNR Enhancement)")
    print("  [4] Complete Pipeline (All modes)")
    mode_choice = input("Enter mode [1-4, default: 4]: ").strip()
    mode_map = {"1": "spectrum", "2": "lightcurve", "3": "stack", "4": "all"}
    mode = mode_map.get(mode_choice, "all")

    # Step 3: Detector Bands / Filters
    print("\nStep 3: SPHEREx Detector Band Selection:")
    print("  Detectors: 1 (0.75-1.11 um), 2 (1.11-1.64 um), 3 (1.64-2.42 um)")
    print("             4 (2.42-3.82 um), 5 (3.82-4.42 um), 6 (4.42-5.00 um)")
    bands_input = input("Enter bands to analyze (e.g., '1,2,3,4,5,6' or '5,6' [default: all]): ").strip()
    if bands_input and bands_input.lower() != "all":
        try:
            selected_bands = [int(b.strip()) for b in bands_input.split(",") if b.strip().isdigit()]
            selected_bands = [b for b in selected_bands if 1 <= b <= 6]
            if not selected_bands:
                selected_bands = [1, 2, 3, 4, 5, 6]
        except Exception:
            selected_bands = [1, 2, 3, 4, 5, 6]
    else:
        selected_bands = [1, 2, 3, 4, 5, 6]

    # Step 4: Show FITS Cutouts & Inspection Plot
    print("\nStep 4: FITS Cutout & Aperture Visual Inspection:")
    show_fits_input = input("Generate FITS multi-extension diagnostic plots with aperture contours? [y/N, default: y]: ").strip().lower()
    show_fits = (show_fits_input in ["y", "yes", "true", ""])

    # Step 5: Stacking Settings
    stack_method = "weighted_mean"
    stack_n_frames = 5
    stack_sigma = 3.0
    align_centroids = True
    if mode in ["all", "stack"]:
        print("\nStep 5: Frame Stacking Coaddition Parameters:")
        print("  Stacking Methods: [1] Weighted Mean (Inverse-Variance), [2] Median, [3] Straight Mean")
        method_choice = input("Select method [1-3, default: 1]: ").strip()
        stack_method = {"1": "weighted_mean", "2": "median", "3": "mean"}.get(method_choice, "weighted_mean")

        n_frames_input = input("Number of frames to stack [default: 5]: ").strip()
        if n_frames_input.isdigit():
            stack_n_frames = max(2, int(n_frames_input))

        sigma_input = input("Sigma clipping outlier rejection threshold [default: 3.0]: ").strip()
        try:
            stack_sigma = float(sigma_input) if sigma_input else 3.0
        except ValueError:
            stack_sigma = 3.0

        align_input = input("Enable sub-pixel centroid shift-and-add alignment? [Y/n, default: y]: ").strip().lower()
        align_centroids = (align_input not in ["n", "no", "false"])

    # Step 6: Variability Period
    period_days = None
    if mode in ["all", "lightcurve"]:
        period_prompt = f"Enter variability period in days [default: {default_period or 'skip'}]: " if default_period else "Enter variability period in days (e.g. 245 for R Dra, 2.77 for RW Aur, or press Enter to skip): "
        period_input = input(f"\nStep 6: {period_prompt}").strip()
        if period_input:
            try:
                period_days = float(period_input)
            except ValueError:
                period_days = default_period
        else:
            period_days = default_period

    # Step 7: Open Folder in Explorer
    open_folder_input = input("\nOpen output folder in Windows File Explorer when finished? [y/N, default: y]: ").strip().lower()
    open_folder = (open_folder_input in ["y", "yes", "true", ""])

    return {
        "ra_deg": ra_deg,
        "dec_deg": dec_deg,
        "target_name": target_name,
        "mode": mode,
        "selected_bands": selected_bands,
        "show_fits": show_fits,
        "stack_method": stack_method,
        "stack_n_frames": stack_n_frames,
        "stack_sigma": stack_sigma,
        "align_centroids": align_centroids,
        "period_days": period_days,
        "open_folder": open_folder,
    }


# -----------------------------------------------------------------------------
# Stacking Diagnostic Plot Generator
# -----------------------------------------------------------------------------
def plot_target_stacking(
    raw_frame: SPHERExFrame,
    stacked_frame: SPHERExFrame,
    target_name: str,
    output_path: Path,
    snr_before: float,
    snr_after: float,
    method: str = "weighted_mean",
    n_frames: int = 5,
) -> None:
    """Generate a side-by-side diagnostic plot of single exposure vs stacked coaddition."""
    fig, axes = plt.subplots(1, 2, figsize=(11, 5), facecolor="#0e1117")
    fig.suptitle(
        f"SPHEREx Frame Stacking Coaddition — {target_name} ({stacked_frame.wavelength_um:.2f} um)",
        fontsize=13,
        fontweight="bold",
        color="white",
        y=0.98,
    )

    from astropy.visualization import PercentileInterval
    interval = PercentileInterval(99.0)
    vmin_raw, vmax_raw = interval.get_limits(raw_frame.data)
    vmin_stk, vmax_stk = interval.get_limits(stacked_frame.data)
    norm_min = min(vmin_raw, vmin_stk)
    norm_max = max(vmax_raw, vmax_stk)

    im0 = axes[0].imshow(raw_frame.data, origin="lower", cmap="inferno", vmin=norm_min, vmax=norm_max)
    axes[0].set_title(f"Single Exposure\nSNR = {snr_before:.1f}", color="#f5a623", fontsize=11)
    axes[0].set_facecolor("#0e1117")
    axes[0].tick_params(colors="white")

    im1 = axes[1].imshow(stacked_frame.data, origin="lower", cmap="inferno", vmin=norm_min, vmax=norm_max)
    boost = snr_after / max(snr_before, 0.01)
    axes[1].set_title(
        f"Coadded Stack ({n_frames} Frames, {method})\nSNR = {snr_after:.1f} ({boost:.1f}x Boost)",
        color="#50e3c2",
        fontsize=11,
    )
    axes[1].set_facecolor("#0e1117")
    axes[1].tick_params(colors="white")

    cbar = fig.colorbar(im1, ax=axes.ravel().tolist(), orientation="horizontal", pad=0.15, aspect=35)
    cbar.set_label("Surface Brightness (MJy/sr)", color="white", fontsize=10)
    cbar.ax.xaxis.set_tick_params(color="white")
    plt.setp(plt.getp(cbar.ax.axes, "xticklabels"), color="white")

    plt.savefig(str(output_path), dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


# -----------------------------------------------------------------------------
# Main Processing Pipeline Function
# -----------------------------------------------------------------------------
def process_target(
    ra_deg: float,
    dec_deg: float,
    target_name: str,
    mode: str = "all",
    selected_bands: Optional[List[int]] = None,
    show_fits: bool = False,
    period_days: Optional[float] = None,
    stack_method: str = "weighted_mean",
    stack_n_frames: int = 5,
    stack_sigma: float = 3.0,
    align_centroids: bool = True,
    open_folder: bool = False,
    fits_dir: Optional[str] = None,
    output_dir: str = "output",
    cutout_size: int = 25,
) -> Dict[str, Any]:
    """
    Execute end-to-end SPHEREx data processing for a user target with customizable inputs:
    - selected_bands: Subset or all 6 detector bands.
    - show_fits: Multi-panel FITS cutout diagnostic plots.
    - period_days: Variability period for phase folding.
    - stack_method, stack_n_frames, stack_sigma, align_centroids: Stacking coaddition controls.
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    if selected_bands is None:
        selected_bands = [1, 2, 3, 4, 5, 6]

    print("\n" + "=" * 76)
    print(f" PROCESSING TARGET: {target_name}")
    print("=" * 76)
    print(f"Coordinates (J2000) : RA = {ra_deg:.5f} deg, Dec = {dec_deg:+.5f} deg")
    print(f"Processing Mode     : {mode.upper()}")
    print(f"Selected Bands      : Detectors {selected_bands}")
    print(f"Show FITS Plots     : {show_fits}")
    if period_days:
        print(f"Variability Period  : {period_days:.2f} days")
    if mode in ["all", "stack"]:
        print(f"Stacking Parameters : {stack_method} | N={stack_n_frames} | sigma={stack_sigma} | align={align_centroids}")
    print(f"Output Directory    : {out_path.resolve()}\n")

    # 1. Obtain FITS Data
    if fits_dir is not None and Path(fits_dir).exists():
        fits_root = Path(fits_dir)
        print(f"--> Using existing FITS directory: {fits_root}")
        survey_files = {
            "spectrum": sorted(list(fits_root.glob("*det*.fits")) + list(fits_root.glob("spectrum/*.fits"))),
            "lightcurve": sorted(list(fits_root.glob("*epoch*.fits")) + list(fits_root.glob("lightcurve/*.fits"))),
            "stack": sorted(list(fits_root.glob("*stack*.fits")) + list(fits_root.glob("stack/*.fits"))),
        }
    else:
        fits_root = out_path / "fits_survey"
        print(f"--> Synthesizing calibrated SPHEREx Level-2 FITS survey in: {fits_root}...")
        survey_files = generate_spherex_survey_for_target(
            target_ra_deg=ra_deg,
            target_dec_deg=dec_deg,
            target_name=target_name,
            output_dir=fits_root,
            mode=mode,
            selected_bands=selected_bands,
            n_stack_frames=stack_n_frames,
            period_days=period_days,
        )

    safe_name = target_name.replace(" ", "_").replace("'", "").replace(".", "")

    results_summary: Dict[str, Any] = {
        "target_name": target_name,
        "ra_deg": ra_deg,
        "dec_deg": dec_deg,
        "selected_bands": selected_bands,
        "period_days": period_days,
        "citation": "NASA/IPAC Infrared Science Archive (IRSA) / SPHEREx Mission",
        "fits_inspection_plots": [],
        "spectrum": None,
        "light_curve": None,
        "stacking": None,
    }

    # -------------------------------------------------------------------------
    # Stage A: Spectrum Extraction across Selected Detectors
    # -------------------------------------------------------------------------
    if mode in ["all", "spectrum"] and survey_files["spectrum"]:
        print("-" * 76)
        print(f" [STAGE A] Multi-Detector 1D Spectrum Extraction (Bands: {selected_bands})")
        print("-" * 76)

        spec_cutouts = []
        for fpath in survey_files["spectrum"]:
            frame = load_cutout_from_fits(fpath, ra_deg, dec_deg, cutout_size=cutout_size)
            spec_cutouts.append(frame)

            # Generate FITS visual inspection plot if requested
            if show_fits:
                fits_plot_path = out_path / f"{safe_name}_fits_inspection_det{frame.detector_id}.png"
                plot_fits_inspection(frame, fits_plot_path)
                results_summary["fits_inspection_plots"].append(fits_plot_path.name)

        if show_fits:
            print(f"    Generated {len(results_summary['fits_inspection_plots'])} FITS inspection diagnostic plots.")

        # Run extraction
        spec_result = extract_spectrum(
            cutouts=spec_cutouts,
            target_ra=ra_deg,
            target_dec=dec_deg,
            target_name=target_name,
        )

        # Generate spectrum plot
        spec_plot_path = out_path / f"{safe_name}_spectrum.png"
        plot_spectrum(
            spectrum=spec_result,
            output_path=str(spec_plot_path),
            title=f"SPHEREx Calibrated Spectrum — {target_name}",
        )
        print(f"    Saved spectrum plot to: {spec_plot_path.name}")

        # Compute AB magnitudes for spectrum
        spec_ab_mags = []
        for flx in spec_result.fluxes_uJy:
            if flx > 0:
                ab_val = float(-2.5 * np.log10(flx * 1e-6 / 3631.0))
            else:
                ab_val = None
            spec_ab_mags.append(ab_val)

        # Console Scorecard
        print(f"    {'Detector':<10} | {'Wavelength':<12} | {'Flux (uJy)':<12} | {'Error (uJy)':<12} | {'SNR':<8} | {'AB Mag':<8}")
        print("    " + "-" * 70)
        for i, det_id in enumerate(spec_result.detectors):
            wl = spec_result.wavelengths_um[i]
            flx = spec_result.fluxes_uJy[i]
            err = spec_result.flux_errors_uJy[i]
            snr = spec_result.snr[i]
            ab = spec_ab_mags[i]
            ab_str = f"{ab:.2f}" if ab is not None else "N/A"
            print(f"    Det {det_id:<6} | {wl:6.3f} um     | {flx:10.2f}   | {err:10.2f}   | {snr:6.1f}   | {ab_str:<8}")

        results_summary["spectrum"] = {
            "plot_file": str(spec_plot_path.name),
            "detectors_present": spec_result.detectors,
            "detectors_missing": spec_result.missing_detectors,
            "wavelengths_um": spec_result.wavelengths_um,
            "fluxes_ujy": spec_result.fluxes_uJy,
            "uncertainties_ujy": spec_result.flux_errors_uJy,
            "ab_magnitudes": spec_ab_mags,
            "quality_flags": [int(f) for f in spec_result.quality_flags],
        }

    # -------------------------------------------------------------------------
    # Stage B: Time-Series Light Curve & Phase-Folding
    # -------------------------------------------------------------------------
    if mode in ["all", "lightcurve"] and survey_files["lightcurve"]:
        print("\n" + "-" * 76)
        print(" [STAGE B] Time-Series Light Curve Extraction & Saturation Checks")
        print("-" * 76)

        lc_cutouts = []
        for fpath in survey_files["lightcurve"]:
            frame = load_cutout_from_fits(fpath, ra_deg, dec_deg, cutout_size=cutout_size)
            lc_cutouts.append(frame)

        # Run light curve extraction
        lc_result = extract_light_curve(
            cutouts=lc_cutouts,
            target_ra=ra_deg,
            target_dec=dec_deg,
            target_name=target_name,
        )

        # Generate standard light curve plot
        lc_plot_path = out_path / f"{safe_name}_light_curve.png"
        plot_light_curve(
            light_curve=lc_result,
            output_path=str(lc_plot_path),
            title=f"SPHEREx Light Curve — {target_name} (Det {lc_result.detector_id})",
        )
        print(f"    Saved light curve plot to: {lc_plot_path.name}")
        n_sat = sum(1 for s in lc_result.is_saturated if s)
        mean_flx = float(np.mean(lc_result.fluxes_uJy))
        print(f"    Total Epochs: {len(lc_result.mjd)} | Mean Flux: {mean_flx:.2f} uJy | Saturation Count: {n_sat}")

        # If variability period is specified, generate phase-folded light curve
        phase_plot_name = None
        if period_days is not None and period_days > 0:
            phase_plot_path = out_path / f"{safe_name}_phase_folded.png"
            plot_phase_folded_light_curve(
                light_curve=lc_result,
                period_days=period_days,
                output_path=str(phase_plot_path),
                title=f"Phase-Folded Light Curve — {target_name} (P = {period_days:.2f} d)",
            )
            phase_plot_name = phase_plot_path.name
            print(f"    Saved phase-folded light curve (P = {period_days:.2f} d) to: {phase_plot_name}")

        results_summary["light_curve"] = {
            "plot_file": str(lc_plot_path.name),
            "phase_folded_plot_file": phase_plot_name,
            "period_days": period_days,
            "detector_id": lc_result.detector_id,
            "wavelength_um": lc_result.central_wavelength_um,
            "mjds": lc_result.mjd,
            "fluxes_ujy": lc_result.fluxes_uJy,
            "uncertainties_ujy": lc_result.flux_errors_uJy,
            "ab_magnitudes": lc_result.ab_magnitudes,
            "mean_flux_ujy": mean_flx,
            "n_saturated": n_sat,
        }

    # -------------------------------------------------------------------------
    # Stage C: Frame Stacking & Sub-pixel Coaddition
    # -------------------------------------------------------------------------
    if mode in ["all", "stack"] and survey_files["stack"]:
        print("\n" + "-" * 76)
        print(f" [STAGE C] Astronomical Frame Stacking ({stack_method.upper()}, N={len(survey_files['stack'])})")
        print("-" * 76)

        stack_cutouts = []
        for fpath in survey_files["stack"]:
            frame = load_cutout_from_fits(fpath, ra_deg, dec_deg, cutout_size=cutout_size)
            stack_cutouts.append(frame)

        # Single frame SNR
        phot_single = measure_aperture_photometry(stack_cutouts[0], center_xy=(12.0, 12.0))
        snr_single = phot_single.snr

        # Coadd frames with user parameters
        stacked_frame = stack_frames(
            stack_cutouts,
            method=stack_method,
            align_centroids=align_centroids,
            sigma_clip=stack_sigma,
        )

        phot_stacked = measure_aperture_photometry(stacked_frame, center_xy=(12.0, 12.0))
        snr_stacked = phot_stacked.snr

        # Plot stacking comparison
        stack_plot_path = out_path / f"{safe_name}_stacked.png"
        plot_target_stacking(
            raw_frame=stack_cutouts[0],
            stacked_frame=stacked_frame,
            target_name=target_name,
            output_path=stack_plot_path,
            snr_before=snr_single,
            snr_after=snr_stacked,
            method=stack_method,
            n_frames=len(stack_cutouts),
        )
        print(f"    Saved stacking comparison plot to: {stack_plot_path.name}")
        print(f"    Single Frame SNR : {snr_single:.2f}")
        print(f"    Coadded Stack SNR: {snr_stacked:.2f} ({snr_stacked / max(snr_single, 0.01):.2f}x enhancement)")

        if show_fits:
            stacked_fits_plot = out_path / f"{safe_name}_fits_inspection_stacked.png"
            plot_fits_inspection(
                stacked_frame,
                stacked_fits_plot,
                title=f"SPHEREx Coadded Stack Inspection — {target_name} ({stack_method})",
            )
            results_summary["fits_inspection_plots"].append(stacked_fits_plot.name)

        results_summary["stacking"] = {
            "plot_file": str(stack_plot_path.name),
            "stack_method": stack_method,
            "sigma_clip": stack_sigma,
            "align_centroids": align_centroids,
            "n_frames_coadded": len(stack_cutouts),
            "snr_single": float(snr_single),
            "snr_coadded": float(snr_stacked),
            "snr_enhancement": float(snr_stacked / max(snr_single, 0.01)),
        }

    # -------------------------------------------------------------------------
    # Stage D: Structured JSON Data Release
    # -------------------------------------------------------------------------
    json_path = out_path / f"{safe_name}_results.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results_summary, f, indent=2)

    abs_out_dir = out_path.resolve()

    print("\n" + "=" * 76)
    print(" TARGET PROCESSING COMPLETE — GENERATED IMAGE FILES:")
    print("=" * 76)
    print(f"Directory Location: {abs_out_dir}\n")

    file_idx = 1
    if results_summary.get("spectrum"):
        spec_file = out_path / results_summary["spectrum"]["plot_file"]
        print(f"  [{file_idx}] Spectrum Plot        : {spec_file.resolve()}")
        file_idx += 1

    if results_summary.get("light_curve"):
        lc_file = out_path / results_summary["light_curve"]["plot_file"]
        print(f"  [{file_idx}] Light Curve Plot     : {lc_file.resolve()}")
        file_idx += 1
        if results_summary["light_curve"].get("phase_folded_plot_file"):
            pf_file = out_path / results_summary["light_curve"]["phase_folded_plot_file"]
            print(f"  [{file_idx}] Phase-Folded Plot    : {pf_file.resolve()}")
            file_idx += 1

    if results_summary.get("stacking"):
        st_file = out_path / results_summary["stacking"]["plot_file"]
        print(f"  [{file_idx}] Stacking Comparison  : {st_file.resolve()}")
        file_idx += 1

    if results_summary.get("fits_inspection_plots"):
        print(f"\n  FITS Cutout & Aperture Diagnostic Plots ({len(results_summary['fits_inspection_plots'])}):")
        for p in results_summary["fits_inspection_plots"]:
            p_file = out_path / p
            print(f"    - {p_file.resolve()}")

    print(f"\n  Data Release JSON     : {json_path.resolve()}")
    print("-" * 76)
    print("  To open this folder in Windows File Explorer, run:")
    print(f"  explorer.exe \"{abs_out_dir}\"")
    print("\n[Mandatory Citation / Attribution]")
    print(results_summary["citation"])
    print("=" * 76 + "\n")

    if open_folder:
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(abs_out_dir))
                print(f">> Opened output folder in Windows File Explorer: {abs_out_dir}")
        except Exception as e:
            print(f">> Note: Could not auto-open folder ({e})")

    return results_summary


# -----------------------------------------------------------------------------
# CLI Entry Point
# -----------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="SPHEREx Sky Viewer — Target Selection and Analysis Pipeline"
    )
    # Target identifiers & coordinates
    parser.add_argument("--ra", type=str, default=None, help="Right Ascension in deg or sexagesimal")
    parser.add_argument("--dec", type=str, default=None, help="Declination in deg or sexagesimal")
    parser.add_argument("--target", type=str, default=None, help="Named target preset (e.g. WISE_0855, R_DRA, RW_AUR)")
    parser.add_argument("--name", type=str, default=None, help="Custom target name")

    # Workflow controls
    parser.add_argument("--mode", type=str, choices=["all", "spectrum", "lightcurve", "stack"], default="all")
    parser.add_argument("--bands", type=str, default="all", help="Comma-separated bands (e.g. '1,2,3' or 'all')")
    parser.add_argument("--show-fits", action="store_true", help="Generate multi-panel FITS cutout inspection plots")
    parser.add_argument("--period", type=float, default=None, help="Variability period in days for light curve phase folding")

    # Stacking parameters
    parser.add_argument("--stack-method", type=str, choices=["weighted_mean", "median", "mean"], default="weighted_mean")
    parser.add_argument("--stack-n-frames", type=int, default=5, help="Number of dithered exposures to stack (default 5)")
    parser.add_argument("--stack-sigma", type=float, default=3.0, help="Sigma clipping outlier rejection threshold")
    parser.add_argument("--no-align", action="store_true", help="Disable centroid shift-and-add alignment")

    # I/O controls
    parser.add_argument("--fits-dir", type=str, default=None, help="Directory containing SPHEREx FITS observations")
    parser.add_argument("--output-dir", type=str, default="output", help="Directory for generated plots and JSON")
    parser.add_argument("--cutout-size", type=int, default=25, help="Cutout size in pixels (default 25)")
    parser.add_argument("--open", action="store_true", help="Automatically open output directory in Windows File Explorer")
    parser.add_argument("--interactive", action="store_true", help="Launch interactive configuration wizard")

    args = parser.parse_args()

    # Determine if interactive mode is requested or required
    if args.interactive or (args.ra is None and args.target is None and len(sys.argv) == 1):
        cfg = prompt_user_for_target()
        ra_deg = cfg["ra_deg"]
        dec_deg = cfg["dec_deg"]
        target_name = cfg["target_name"]
        mode = cfg["mode"]
        selected_bands = cfg["selected_bands"]
        show_fits = cfg["show_fits"]
        stack_method = cfg["stack_method"]
        stack_n_frames = cfg["stack_n_frames"]
        stack_sigma = cfg["stack_sigma"]
        align_centroids = cfg["align_centroids"]
        period_days = cfg["period_days"]
        open_folder = cfg.get("open_folder", True)
    else:
        if args.target is not None:
            target_key = args.target.strip().upper().replace(" ", "_").replace("'", "")
            if target_key in TARGET_DATABASE:
                prof = TARGET_DATABASE[target_key]
                ra_deg, dec_deg = prof.ra_deg, prof.dec_deg
                target_name = args.name if args.name else prof.common_name
            else:
                raise ValueError(f"Unknown preset target '{args.target}'. Available: {list(TARGET_DATABASE.keys())}")
        elif args.ra is not None:
            ra_deg, dec_deg, auto_name = parse_coordinates(args.ra, args.dec)
            target_name = args.name if args.name else auto_name
        else:
            raise ValueError("Must provide either --ra and --dec, --target, or run with --interactive")

        mode = args.mode
        show_fits = args.show_fits
        period_days = args.period
        stack_method = args.stack_method
        stack_n_frames = args.stack_n_frames
        stack_sigma = args.stack_sigma
        align_centroids = not args.no_align
        open_folder = args.open

        # Parse selected bands
        if args.bands.lower() == "all":
            selected_bands = [1, 2, 3, 4, 5, 6]
        else:
            selected_bands = [int(b.strip()) for b in args.bands.split(",") if b.strip().isdigit()]
            selected_bands = [b for b in selected_bands if 1 <= b <= 6]
            if not selected_bands:
                selected_bands = [1, 2, 3, 4, 5, 6]

    process_target(
        ra_deg=ra_deg,
        dec_deg=dec_deg,
        target_name=target_name,
        mode=mode,
        selected_bands=selected_bands,
        show_fits=show_fits,
        period_days=period_days,
        stack_method=stack_method,
        stack_n_frames=stack_n_frames,
        stack_sigma=stack_sigma,
        align_centroids=align_centroids,
        open_folder=open_folder,
        fits_dir=args.fits_dir,
        output_dir=args.output_dir,
        cutout_size=args.cutout_size,
    )


if __name__ == "__main__":
    main()
