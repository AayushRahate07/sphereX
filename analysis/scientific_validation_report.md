# SPHEREx Sky Viewer — Scientific Target Validation Report

This report documents the scientific verification of the five NASA Space Apps 2026
challenge targets using the SPHEREx Member 3 analysis suite.

## Summary Table

| Target Name | Type | Frame Count | Detectors Present | Saturation Status | Annual Pixel Drift |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **WISE J085510.83-071442.5** | Sub-stellar brown dwarf  | 6 | 1, 2, 3, 4, 5, 6 | Linear (OK) | 1.31 pix/yr |
| **Barnard's Star (GJ 699)** | High proper motion red dwarf  | 10 | 1, 2, 3, 4, 5, 6 | Linear (OK) | 1.67 pix/yr |
| **Epsilon Indi B (HD 209100B)** | Cold T-dwarf binary system  | 9 | 1, 2, 3, 4, 5, 6 | Linear (OK) | 0.76 pix/yr |
| **RW Aurigae** | Classical T Tauri young stellar object  | 8 | 2 | Linear (OK) | 0.00 pix/yr |
| **R Draconis** | Mira pulsating red giant  | 7 | 1 | Saturated (2) | 0.00 pix/yr |

---

## Target: WISE J085510.83-071442.5
- **Astrophysical Classification**: Sub-stellar brown dwarf (Y-dwarf, T_eff ~ 250 K)
- **Exposures Analyzed**: 6 frames spanning 300.0 days
- **Detector Visibility**: Observed Detectors: [1, 2, 3, 4, 5, 6] (Missing: None)
- **Apparent Movement**: 8.138 arcsec/yr (1.31 pix/yr at 6.2"/pix).
  > **Movement Assessment**: Significant proper motion: Star moves 1.08 pixels (6.68 arcsec) over 300.0 days. Coordinate propagation recommended.
- **Photometric Dynamic Range & Saturation**:
  - Peak Pixel Recorded: 0.5 MJy/sr
  - Saturated Exposures: 0 (Saturated Pixels: 0)
  - Risk Assessment: **None**
- **Source Visibility & SNR Breakdown**:
  - Confirmed Detections (SNR >= 3.0): 0
  - Low SNR / Non-Detections (SNR < 3.0): 6
- **Key Spectral Signatures**:
  - Strong 4.5-4.9 um atmospheric window emission (Band 5 & 6)
  - Deep H2O and CH4 molecular absorption suppressing near-IR flux (Bands 1-3)
  - Sub-stellar thermal emission peaking in mid-infrared
- **Scientific Limitations & Caveats**:
  - *Near-IR flux (< 2.5 um) is below single-exposure detection limit; requires coadding.*
  - *High proper motion (~8.14 arcsec/yr = 1.31 pix/yr) causes smearing across years if uncorrected.*

---

## Target: Barnard's Star (GJ 699)
- **Astrophysical Classification**: High proper motion red dwarf (M4V)
- **Exposures Analyzed**: 10 frames spanning 657.0 days
- **Detector Visibility**: Observed Detectors: [1, 2, 3, 4, 5, 6] (Missing: None)
- **Apparent Movement**: 10.369 arcsec/yr (1.67 pix/yr at 6.2"/pix).
  > **Movement Assessment**: Significant proper motion: Star moves 3.01 pixels (18.65 arcsec) over 657.0 days. Coordinate propagation recommended.
- **Photometric Dynamic Range & Saturation**:
  - Peak Pixel Recorded: 14.9 MJy/sr
  - Saturated Exposures: 0 (Saturated Pixels: 0)
  - Risk Assessment: **Low to Moderate**
- **Source Visibility & SNR Breakdown**:
  - Confirmed Detections (SNR >= 3.0): 10
  - Low SNR / Non-Detections (SNR < 3.0): 0
- **Key Spectral Signatures**:
  - Spectral peak in near-IR (1.1 - 1.5 um, Band 2)
  - Prominent molecular absorption bands (TiO, VO, FeH)
  - Rayleigh-Jeans decline into Bands 4-6
  - CO bandhead absorption at 2.3 um and 4.6 um
- **Scientific Limitations & Caveats**:
  - *Highest known proper motion (10.36 arcsec/yr = 1.67 pix/yr); requires epoch coordinate update.*
  - *Nearby field stars may contaminate annulus during orbital slews.*

---

## Target: Epsilon Indi B (HD 209100B)
- **Astrophysical Classification**: Cold T-dwarf binary system (T1 + T6)
- **Exposures Analyzed**: 9 frames spanning 320.0 days
- **Detector Visibility**: Observed Detectors: [1, 2, 3, 4, 5, 6] (Missing: None)
- **Apparent Movement**: 4.704 arcsec/yr (0.76 pix/yr at 6.2"/pix).
  > **Movement Assessment**: Significant proper motion: Star moves 0.66 pixels (4.12 arcsec) over 320.0 days. Coordinate propagation recommended.
- **Photometric Dynamic Range & Saturation**:
  - Peak Pixel Recorded: 3.0 MJy/sr
  - Saturated Exposures: 0 (Saturated Pixels: 0)
  - Risk Assessment: **Low**
- **Source Visibility & SNR Breakdown**:
  - Confirmed Detections (SNR >= 3.0): 6
  - Low SNR / Non-Detections (SNR < 3.0): 3
- **Key Spectral Signatures**:
  - Deep methane (CH4) and water (H2O) absorption bands at 1.4, 1.9, 2.3, and 3.3 um
  - Near-IR transmission peaks in Y, J, H, and K windows
  - Sub-stellar binary spectral blend
- **Scientific Limitations & Caveats**:
  - *Proximity to bright primary star Epsilon Indi A (V ~ 4.7) causes severe stray light and halo contamination.*
  - *Band 4 flux heavily depressed by 3.3 um fundamental methane absorption band.*

---

## Target: RW Aurigae
- **Astrophysical Classification**: Classical T Tauri young stellar object (binary)
- **Exposures Analyzed**: 8 frames spanning 84.0 days
- **Detector Visibility**: Observed Detectors: [2] (Missing: [1, 3, 4, 5, 6])
- **Apparent Movement**: 0.020 arcsec/yr (0.00 pix/yr at 6.2"/pix).
  > **Movement Assessment**: Apparent movement is sub-pixel over observation baseline.
- **Photometric Dynamic Range & Saturation**:
  - Peak Pixel Recorded: 13.6 MJy/sr
  - Saturated Exposures: 0 (Saturated Pixels: 0)
  - Risk Assessment: **Low to Moderate**
- **Source Visibility & SNR Breakdown**:
  - Confirmed Detections (SNR >= 3.0): 8
  - Low SNR / Non-Detections (SNR < 3.0): 0
- **Key Spectral Signatures**:
  - Infrared excess from warm circumstellar dust disk (Bands 3-6)
  - Accretion emission lines (Paschen/Brackett hydrogen recombination)
  - Pronounced photometric dimming events (Delta m > 2 mag) from circumstellar dust occultation
- **Scientific Limitations & Caveats**:
  - *Erratic non-periodic dimming requires continuous multi-epoch monitoring.*
  - *Color temperature changes dramatically between bright and faint states.*

---

## Target: R Draconis
- **Astrophysical Classification**: Mira pulsating red giant (AGB star, period ~245 days)
- **Exposures Analyzed**: 7 frames spanning 210.0 days
- **Detector Visibility**: Observed Detectors: [1] (Missing: [2, 3, 4, 5, 6])
- **Apparent Movement**: 0.011 arcsec/yr (0.00 pix/yr at 6.2"/pix).
  > **Movement Assessment**: Apparent movement is sub-pixel over observation baseline.
- **Photometric Dynamic Range & Saturation**:
  - Peak Pixel Recorded: 50.0 MJy/sr
  - Saturated Exposures: 2 (Saturated Pixels: 2)
  - Risk Assessment: **Extreme (at pulsation maximum)**
- **Source Visibility & SNR Breakdown**:
  - Confirmed Detections (SNR >= 3.0): 7
  - Low SNR / Non-Detections (SNR < 3.0): 0
- **Key Spectral Signatures**:
  - Large-amplitude pulsation (Delta V ~ 6.5 mag, Delta NIR ~ 1.5-2.0 mag)
  - Extremely intense near-IR flux (> 250,000 uJy at maximum)
  - Deep titanium oxide (TiO), CO, and H2O absorption in circumstellar envelope
- **Scientific Limitations & Caveats**:
  - *Detector saturation at maximum brightness clips peak flux; must treat as lower limit.*
  - *Heavy mass loss creates circumstellar dust shell modifying infrared continuum.*

---
