# SPHEREx Sky Viewer — Member 3: Spectrum, Checks and Release

[![NASA Space Apps 2026](https://img.shields.io/badge/NASA%20Space%20Apps-2026-blue.svg)](https://www.spaceappschallenge.org/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Astropy](https://img.shields.io/badge/astronomy-astropy%20%7C%20photutils-orange.svg)](https://www.astropy.org/)
[![Tests](https://img.shields.io/badge/verification-100%25%20passed-brightgreen.svg)](run_all_checks.py)

This repository contains the scientific data processing engine, multi-detector spectrum extraction, time-domain light curve engine, quality control checks, and scientific validation for the **SPHEREx Sky Viewer** (NASA Space Apps Challenge 2026).

---

## 1. Scientific Overview & SPHEREx Mission Context

NASA's **SPHEREx** (Spectro-Photometer for the History of the Universe, Epoch of Reionization and Ices Explorer) maps the entire celestial sphere in 102 near- and mid-infrared spectral bands.

### Key Instrument Characteristics
- **Linear Variable Filters (LVF)**: Wavelength varies continuously across one spatial axis of each detector array. As the spacecraft sweeps across the sky, stars land on different detector pixels, sampling different central wavelengths from **0.75 to 5.00 $\mu\text{m}$**.
- **Six Distinct Detector Arrays**:
  - **Detector 1**: $0.75 - 1.11\,\mu\text{m}$ ($R \sim 41$, Near-IR)
  - **Detector 2**: $1.11 - 1.64\,\mu\text{m}$ ($R \sim 41$, Near-IR)
  - **Detector 3**: $1.64 - 2.42\,\mu\text{m}$ ($R \sim 41$, Near-IR)
  - **Detector 4**: $2.42 - 3.82\,\mu\text{m}$ ($R \sim 35$, Mid-IR)
  - **Detector 5**: $3.82 - 4.42\,\mu\text{m}$ ($R \sim 110$, Mid-IR, CO/ice line resolution)
  - **Detector 6**: $4.42 - 5.00\,\mu\text{m}$ ($R \sim 130$, Mid-IR)
- **Pixel Scale**: $\sim 6.2^{\prime\prime}/\text{pixel}$ with a Point Spread Function (PSF) FWHM of $\sim 5^{\prime\prime} - 6^{\prime\prime}$ ($\sim 1$ pixel).
- **Pixel Solid Angle**: $\Omega_{\text{pix}} \approx 9.035 \times 10^{-10}\text{ steradians}$.

---

## 2. Member 3 Responsibilities & Architecture

```
spherex_sky_viewer/
├── data_models.py           # SPHERExFrame, SpectrumResult, LightCurveResult, QualityFlag
├── photometry.py            # Aperture photometry, sigma-clipped background annulus, error propagation
├── stacking.py              # Frame stacking, SNR boost (~sqrt(N)), sub-pixel shift-and-add, cosmic ray rejection
├── analysis.py              # extract_spectrum, extract_light_curve, plot_spectrum, plot_light_curve
├── fits_loader.py           # Astropy WCS Cutout2D extractor, MEF FITS reader/writer, coordinate parser
├── process_target.py        # User interactive & CLI target processing pipeline
├── target_validation.py     # Scientific validation rules for the 5 challenge targets
├── scientific_validation_report.md # Comprehensive astrophysical validation report
├── run_all_checks.py        # Master verification runner and scorecard across all 7 stages
├── requirements.txt         # Package dependencies
├── test_data_models.py      # Stage 1 tests (models & interface guards)
├── test_photometry.py       # Stage 2 tests (photometry recovery & background invariance)
├── test_spectrum.py         # Stage 3 tests (6-detector synthesis & missing detector handling)
├── test_light_curve.py      # Stage 4 tests (time-series, AB magnitudes & saturation)
├── test_targets.py          # Stage 5 tests (challenge target verification)
├── test_stacking.py         # Stage 6 tests (frame stacking, outlier rejection & alignment)
└── test_fits_pipeline.py    # Stage 7 tests (FITS I/O, WCS Cutout2D & user target pipeline)
```

---

## 3. Installation & Clean Environment Setup

### Prerequisites
- Python 3.10, 3.11, or 3.12
- Operating System: Windows, macOS, or Linux

### Installation
```bash
# 1. Clone or navigate to the project directory
cd spherex_sky_viewer

# 2. (Optional) Create and activate a virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

# 3. Install astronomical dependencies
pip install -r requirements.txt
```

---

## 4. Quickstart & Verification

Run the master verification suite from a clean start:

```bash
python run_all_checks.py
```

### Expected Output
```text
============================================================================
 SPHEREx Sky Viewer — Member 3 Master Verification Suite
============================================================================
--> Running: Stage 1: Data Models & Interfaces (test_data_models.py)...    [PASSED]
--> Running: Stage 2: Core Photometry Engine (test_photometry.py)...      [PASSED]
--> Running: Stage 3: Multi-Detector Spectrum Engine (test_spectrum.py)... [PASSED]
--> Running: Stage 4: Time-Series Light Curve Engine (test_light_curve.py) [PASSED]
--> Running: Stage 5: 5 Challenge Targets Validation (test_targets.py)... [PASSED]
============================================================================
>> ALL SYSTEMS OPERATIONAL: Member 3 analysis suite is clean & release-ready!
============================================================================
```

---

## 5. Usage & Core API

### A. Multi-Detector Spectrum Extraction
```python
from analysis import extract_spectrum, plot_spectrum
from data_models import SPHERExFrame

# cutouts provided by Member 2 (Backend)
spectrum = extract_spectrum(
    cutouts=cutouts,
    target_ra=269.452,
    target_dec=4.693,
    aperture_radius_pix=2.5,
    annulus_inner_pix=4.0,
    annulus_outer_pix=6.0,
    target_name="Barnard's Star",
)

# Plot publication-grade spectrum with 6 detector bands shaded
fig = plot_spectrum(spectrum, output_path="spectrum.png")

# Export clean JSON for Member 1 (Frontend)
frontend_json = spectrum.to_dict()
```

### B. Time-Series Light Curve Extraction
```python
from analysis import extract_light_curve, plot_light_curve

# Extract time-series photometry (MJD sequenced, AB magnitude converted)
light_curve = extract_light_curve(
    cutouts=time_series_cutouts,
    target_ra=77.465,
    target_dec=30.402,
    detector_id=2,                 # Isolate Band 2 (1.11 - 1.64 um)
    wavelength_tolerance_um=0.05,
    target_name="RW Aurigae",
)

# Plot dual-panel figure (Flux + Inverted AB Magnitude)
fig = plot_light_curve(light_curve, output_path="light_curve.png", plot_type="both")

# Access metadata
print(f"Dimming amplitude: {light_curve.metadata['peak_to_peak_amplitude_mag']:.2f} mag")
print(f"Saturated epochs:  {light_curve.metadata['saturated_epoch_count']}")
```

### C. Frame Stacking & Shift-and-Add Coaddition
```python
from stacking import stack_frames
from photometry import measure_aperture_photometry

# Coadd N exposures of faint target (e.g., WISE 0855) with sub-pixel alignment & cosmic ray rejection
stacked_frame = stack_frames(
    frames=faint_cutouts,
    method="weighted_mean",        # 'weighted_mean', 'median', or 'mean'
    sigma_clip=3.0,                # Outlier rejection for cosmic ray hits
    align_centroids=True,          # Shift-and-add for proper motion drift
)

# Measure aperture flux on clean, coadded frame (SNR boosted by ~sqrt(N))
meas = measure_aperture_photometry(stacked_frame)
print(f"Stacked SNR: {meas.snr:.1f} (Theoretical Boost: {stacked_frame.additional_metadata['theoretical_snr_boost']:.1f}x)")
```

### D. User Target Selection & Automated SPHEREx FITS Pipeline
Users can provide celestial coordinates in **decimal degrees** or **sexagesimal notation**, or select predefined challenge targets. The pipeline extracts sub-images using Astropy WCS `Cutout2D` from multi-extension FITS files (`PRIMARY`, `SCI`, `UNCERT`, `MASK`) and runs the complete analysis suite.

#### 1. Interactive Mode
Run without arguments to launch the guided console menu:
```bash
python process_target.py
```
```
============================================================================
  SPHEREx Sky Viewer — Target Selection & Analysis Pipeline
============================================================================
Select a target or enter custom celestial coordinates (J2000 / ICRS):
----------------------------------------------------------------------------
  [1] WISE 0855        (RA=133.790 deg, Dec=-7.240 deg)  - Cold Brown Dwarf
  [2] Barnard's Star   (RA=269.452 deg, Dec=+4.693 deg)  - High Proper Motion
  [3] Epsilon Indi B   (RA=330.840 deg, Dec=-56.790 deg) - T-dwarf Binary
  [4] RW Aurigae       (RA=77.108 deg,  Dec=+30.402 deg) - Variable Young Star
  [5] R Draconis       (RA=248.370 deg, Dec=+66.702 deg) - Mira Pulsating Giant
  [C] Custom Coordinates (Enter decimal degrees or sexagesimal)
----------------------------------------------------------------------------
```

#### 2. Command Line Interface (CLI) & Custom User Inputs
All scientific analysis parameters can be customized via command-line flags or interactive wizard:

```bash
# 1. Custom Coordinates & Complete Analysis
python process_target.py --ra 133.790 --dec -7.240 --name "WISE_0855" --mode all

# 2. Sexagesimal Coordinates (hours/degrees notation)
python process_target.py --ra "17h57m48.5s" --dec "+04d41m36s" --name "Barnards_Star"

# 3. User Filter / Band Selection (e.g. only Bands 1, 2, 3 or Bands 5 & 6)
python process_target.py --target WISE_0855 --bands 5,6 --mode spectrum

# 4. User Stacking Parameters (Method: weighted_mean / median / mean, frame count, sigma threshold)
python process_target.py --target RW_AUR --stack-method median --stack-n-frames 8 --stack-sigma 2.5 --mode stack

# 5. User Variability Period & Phase-Folded Light Curve (e.g., P = 245.0 days for Mira giant R Draconis)
python process_target.py --target R_DRA --period 245.0 --mode lightcurve

# 6. Multi-Panel FITS Cutout & Aperture Visual Inspection Display
python process_target.py --target R_DRA --bands 1,2,3 --period 245.0 --show-fits --stack-method median --stack-n-frames 6
```

#### Generated Deliverables & Visual Diagnostics:
- `<target>_fits_inspection_det<B>.png`: 3-panel FITS diagnostic plot showing the Calibrated Science image (`SCI`) with green circular aperture ($r_{\text{aper}}$) and orange background sky annulus ($r_{\text{in}} - r_{\text{out}}$) overlays, $1\sigma$ Uncertainty map (`UNCERT`), and Quality bitmask (`MASK`).
- `<target>_spectrum.png`: 6-band shaded spectrum plot ($0.75 - 5.0\,\mu\text{m}$) across selected detectors.
- `<target>_light_curve.png`: Dual-panel flux ($\mu\text{Jy}$) and inverted AB magnitude light curve.
- `<target>_phase_folded.png`: Phase-folded light curve over 2 full cycles ($\phi \in [0.0, 2.0)$) with smooth model trend.
- `<target>_stacked.png`: Side-by-side single exposure vs coadded stack comparison ($\sim \sqrt{N}$ SNR boost).
- `<target>_results.json`: Complete JSON data release consumable by frontend.

---

## 6. Scientific Validation of the 5 Challenge Targets

See [`scientific_validation_report.md`](scientific_validation_report.md) for full details.

| Target Name | Type | Key Scientific Findings | Saturation Status | Annual Pixel Drift |
| :--- | :--- | :--- | :---: | :---: |
| **WISE 0855** | Sub-stellar Y-dwarf ($T \sim 250\text{ K}$) | Faint/undetected in NIR (Bands 1-3), detected in Bands 5-6 ($4.5\,\mu\text{m}$ window). | None (Linear) | $1.31\text{ pix/yr}$ |
| **Barnard's Star** | High proper motion M-dwarf | Highest proper motion ($10.37^{\prime\prime}/\text{yr}$). Peak in Band 2 ($1.25\,\mu\text{m}$). | None (Linear) | $1.67\text{ pix/yr}$ |
| **Epsilon Indi B** | Cold T-dwarf binary | Methane & water absorption valleys at $1.4, 1.9, 3.3\,\mu\text{m}$. | None (Linear) | $0.76\text{ pix/yr}$ |
| **RW Aurigae** | Classical T Tauri binary | Severe dust obscuration dimming ($\Delta m = 1.97\text{ mag}$) over 96 days. | None (Linear) | Sub-pixel |
| **R Draconis** | Mira pulsating red giant | Pulsation period $\sim 245\text{ d}$. Peaks exceed $50\,\text{MJy/sr}$. | Saturated (2 epochs) | Sub-pixel |

---

## 7. Data Contracts & Integration Guide

### Backend Contract (Member 2 $\to$ Member 3)
Member 2 provides cutouts conforming to `SPHERExFrame`:
- `data`: 2D `float64` array in physical units (`'MJy/sr'`).
- `uncertainty`: 2D `float64` array ($1\sigma$ Gaussian uncertainty).
- `mask`: 2D `int32` bitwise flag array (`1`=Bad, `2`=Saturated, `4`=Cosmic Ray, `8`=Edge).
- Metadata: `frame_id`, `mjd`, `timestamp_utc`, `detector_id` (1..6), `wavelength_um`, `ra_deg`, `dec_deg`, `pixel_scale_arcsec` ($6.2^{\prime\prime}$), `flux_unit` (`'MJy/sr'`).

### Frontend Contract (Member 3 $\to$ Member 1)
All analysis outputs implement `.to_dict()` returning JSON-serializable dictionaries containing:
- Lists of floats/integers (no raw numpy objects or memory buffers).
- Wavelengths, fluxes ($\mu\text{Jy}$), uncertainties, SNRs, detector IDs, and bitwise flags.
- Light curve Modified Julian Dates, timestamps, AB magnitudes, and saturation booleans.

---

## 8. NASA / IRSA Required Acknowledgement

As required for all research and public software making use of NASA infrared survey data:

> *"This research has made use of the NASA/IPAC Infrared Science Archive, which is funded by the National Aeronautics and Space Administration and operated by the California Institute of Technology."*
