"""
Tests and Verification for SPHEREx Frame Stacking Engine (Stage 6)
==================================================================
Validates:
1. Signal-to-Noise Ratio (SNR) boost: SNR_stacked ~ sqrt(N) * SNR_single.
2. Cosmic ray & transient outlier rejection via sigma-clipped weighted mean.
3. Sub-pixel shift-and-add centroid alignment for proper-motion drift.
4. Scientific visualization: Generates stacking_demonstration.png comparing
   single noisy frames, cosmic ray contaminated frames, and clean stacked coadditions.
"""

import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from data_models import SPHERExFrame, QualityFlag, create_synthetic_cutout
from photometry import measure_aperture_photometry
from stacking import stack_frames, align_frame_to_center


def test_snr_improvement_boost():
    """Verify that coadding N frames boosts SNR by approximately sqrt(N)."""
    print("Test 1: Signal-to-Noise Ratio (SNR) boost verification...")
    n_frames = 16
    faint_flux_uJy = 180.0      # Sub-threshold source
    noise_sigma = 0.015         # Realistic near-IR background noise

    frames = []
    single_snrs = []
    for i in range(n_frames):
        f = create_synthetic_cutout(
            detector_id=2,
            wavelength_um=1.35,
            flux_uJy=faint_flux_uJy,
            cutout_size=25,
            noise_sigma_mjy_sr=noise_sigma,
            frame_id=f"exp_{i:02d}",
            random_seed=1000 + i,
        )
        frames.append(f)
        meas_single = measure_aperture_photometry(f)
        single_snrs.append(meas_single.snr)

    avg_single_snr = float(np.mean(single_snrs))

    # Coadd frames using sigma-clipped weighted mean
    stacked = stack_frames(frames, method="weighted_mean", sigma_clip=3.0)
    meas_stacked = measure_aperture_photometry(stacked)

    snr_boost = meas_stacked.snr / max(avg_single_snr, 0.1)
    theoretical_boost = np.sqrt(n_frames)  # sqrt(16) = 4.0

    print(f"  Input Frames:         {n_frames}")
    print(f"  Average Single Frame SNR: {avg_single_snr:.2f}")
    print(f"  Stacked Coadded Frame SNR: {meas_stacked.snr:.2f}")
    print(f"  Observed SNR Boost:    {snr_boost:.2f}x (Theoretical sqrt(N) = {theoretical_boost:.2f}x)")

    # Assert that SNR boosted significantly (> 2.8x for N=16)
    assert snr_boost >= 2.8, f"Expected SNR boost >= 2.8x, got {snr_boost:.2f}x"
    assert meas_stacked.snr > 3.0, "Stacked frame should achieve robust detection (SNR > 3.0)"
    print("  [OK] Stacking successfully boosted SNR consistent with sqrt(N) theory.\n")


def test_cosmic_ray_rejection():
    """Verify that sigma-clipped stacking rejects a severe cosmic ray transient."""
    print("Test 2: Cosmic ray and transient outlier rejection...")
    n_frames = 9
    flux_uJy = 2500.0
    noise_sigma = 0.005

    frames = [
        create_synthetic_cutout(
            detector_id=1,
            wavelength_um=0.95,
            flux_uJy=flux_uJy,
            cutout_size=25,
            noise_sigma_mjy_sr=noise_sigma,
            random_seed=100 + i,
        )
        for i in range(n_frames)
    ]

    # Inject a massive cosmic ray spike (200 MJy/sr) directly into frame #4 near the star core
    frames[4].data[12, 13] = 200.0
    frames[4].mask[12, 13] |= int(QualityFlag.COSMIC_RAY)

    # Stack with sigma-clipping enabled
    stacked = stack_frames(frames, method="weighted_mean", sigma_clip=3.0)

    # Verify that the peak pixel of the stacked frame did NOT get contaminated
    peak_val = np.max(stacked.data)
    print(f"  Cosmic Ray Injected Spike: 200.0 MJy/sr in Frame 4")
    print(f"  Clean Stacked Peak Value:  {peak_val:.2f} MJy/sr")

    assert peak_val < 30.0, f"Stacked frame retained cosmic ray contamination! Peak={peak_val}"
    # Verify photometry on stacked frame matches clean ground truth
    meas = measure_aperture_photometry(stacked)
    err_percent = abs(meas.flux_uJy - flux_uJy) / flux_uJy * 100.0
    print(f"  Stacked Recovered Flux:    {meas.flux_uJy:.1f} uJy (Error = {err_percent:.2f}%)")

    assert err_percent < 5.0, f"Flux error after cosmic ray rejection exceeded 5%: {err_percent:.2f}%"
    print("  [OK] Cosmic ray hit completely rejected by sigma-clipping.\n")


def test_subpixel_shift_and_add():
    """Verify sub-pixel centroid alignment for drifting stars."""
    print("Test 3: Sub-pixel shift-and-add alignment...")
    # Simulate a star drifting by +0.5 pixel per exposure due to proper motion
    shifts = [(0.0, 0.0), (0.5, 0.5), (1.0, 1.0), (1.5, 1.5)]
    frames = []

    for idx, (dx, dy) in enumerate(shifts):
        f = create_synthetic_cutout(
            detector_id=3,
            wavelength_um=2.00,
            flux_uJy=1200.0,
            cutout_size=25,
            source_offset_pix=(dx, dy),
            frame_id=f"drift_frame_{idx}",
        )
        frames.append(f)

    # Stack with centroid alignment enabled
    aligned_stack = stack_frames(frames, method="weighted_mean", align_centroids=True)

    # Check that source peak in stacked frame is at center (12, 12)
    cy, cx = np.unravel_index(np.argmax(aligned_stack.data), aligned_stack.data.shape)
    print(f"  Target Center: (12, 12)")
    print(f"  Stacked Aligned Peak: ({cx}, {cy})")

    assert (cx, cy) == (12, 12), f"Expected aligned peak at (12, 12), got ({cx}, {cy})"
    print("  [OK] Sub-pixel shift-and-add successfully aligned drifting source.\n")


def test_visual_stacking_demonstration():
    """Generate scientific visual comparison plot of single frame vs stacked coaddition."""
    print("Test 4: Scientific visualization plot (stacking_demonstration.png)...")
    out_file = "stacking_demonstration.png"
    if os.path.exists(out_file):
        os.remove(out_file)

    # Create 16 noisy frames of a faint source
    n_frames = 16
    faint_flux = 220.0
    frames = []
    for i in range(n_frames):
        f = create_synthetic_cutout(
            detector_id=2,
            wavelength_um=1.35,
            flux_uJy=faint_flux,
            cutout_size=25,
            background_level_mjy_sr=1.0,
            noise_sigma_mjy_sr=0.015,
            frame_id=f"demo_{i}",
            random_seed=2000 + i,
        )
        frames.append(f)

    # Inject a cosmic ray into frame 2 for visual comparison
    cr_frame = frames[2]
    cr_frame.data[12, 14] = 80.0

    # Stack
    stacked = stack_frames(frames, method="weighted_mean", sigma_clip=3.0)

    # Plot 3 comparison panels
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.5), dpi=150)

    # Panel 1: Single Noisy Frame
    im1 = axes[0].imshow(frames[0].data, origin="lower", cmap="inferno", vmin=0.8, vmax=1.5, interpolation="bicubic")
    axes[0].set_title(f"Single Exposure\n(SNR ~ {measure_aperture_photometry(frames[0]).snr:.1f})", fontsize=11, fontweight="bold")
    axes[0].set_xlabel("X [pixels]")
    axes[0].set_ylabel("Y [pixels]")
    plt.colorbar(im1, ax=axes[0], fraction=0.046, pad=0.04, label="MJy/sr")

    # Panel 2: Cosmic Ray Hit Frame
    im2 = axes[1].imshow(cr_frame.data, origin="lower", cmap="inferno", vmin=0.8, vmax=2.5, interpolation="bicubic")
    axes[1].set_title("Single Exposure with\nCosmic Ray Spike", fontsize=11, fontweight="bold", color="darkred")
    axes[1].set_xlabel("X [pixels]")
    axes[1].annotate("Cosmic Ray Hit", xy=(14, 12), xytext=(16, 18),
                     arrowprops=dict(facecolor="white", edgecolor="red", arrowstyle="->", lw=1.5),
                     color="white", fontsize=9, fontweight="bold")
    plt.colorbar(im2, ax=axes[1], fraction=0.046, pad=0.04, label="MJy/sr")

    # Panel 3: Clean Stacked Frame (16 coadded exposures)
    meas_st = measure_aperture_photometry(stacked)
    im3 = axes[2].imshow(stacked.data, origin="lower", cmap="inferno", vmin=0.8, vmax=1.5, interpolation="bicubic")
    axes[2].set_title(f"Stacked Coadd (N=16)\n(SNR ~ {meas_st.snr:.1f}) - Outlier Free", fontsize=11, fontweight="bold", color="darkgreen")
    axes[2].set_xlabel("X [pixels]")
    plt.colorbar(im3, ax=axes[2], fraction=0.046, pad=0.04, label="MJy/sr")

    plt.suptitle("SPHEREx Sky Viewer — Coaddition & Stacking Verification", fontsize=13, fontweight="bold", y=1.03)
    plt.tight_layout()
    fig.savefig(out_file, dpi=200, bbox_inches="tight")

    assert os.path.exists(out_file), "Demonstration plot was not written"
    print(f"  [OK] Stacking demonstration figure saved ({os.path.getsize(out_file)} bytes): {out_file}\n")


if __name__ == "__main__":
    print("=" * 70)
    print("SPHEREx Sky Viewer - Member 3 Frame Stacking Verification")
    print("=" * 70 + "\n")
    test_snr_improvement_boost()
    test_cosmic_ray_rejection()
    test_subpixel_shift_and_add()
    test_visual_stacking_demonstration()
    print("=" * 70)
    print("ALL STACKING ENGINE CHECKS PASSED SUCCESSFULLY!")
    print("=" * 70)
