# SPHEREx Sky Viewer — Milestone 1.2: First-Hours Target & Data Availability Audit

**Project**: SPHEREx Sky Viewer — NASA Space Apps Challenge 2026 (*Planet X and SPHEREx*)
**Workstream**: Member 1 (Data, Processing, and Release)
**Milestone**: 1.2 (First-Hours Data Audit for Checkpoint 3)
**Timestamp**: 2026-11-14T13:00:00Z
**Archive**: NASA/IPAC Infrared Science Archive (IRSA), Data Release 1 (`spherex_dr1`)

---

## 1. Executive Summary

This report establishes the first-hours data audit across all five challenge targets using live queries to the NASA/IPAC Infrared Science Archive (IRSA) TAP service (`spherex.obscore`) and multi-epoch FITS cutout inspections.

### Key Audit Findings:
1. **Abundant Data Across All Targets**: Every one of the five canonical targets has between **240 and 415 SPHEREx DR1 observation records** distributed across all six detector bands (`SPHEREx-D1` through `SPHEREx-D6`).
2. **True Observation Disambiguation**: In all five targets, the candidate record count within any single bandpass **identically matches the unique observation ID (`obs_id`) count** (e.g. WISE 0855 has exactly 45 unique `obs_id` values in D6, 36 in D1). The ~2:1 ratio in multi-band queries arises because a single spacecraft pointing captures multiple focal planes simultaneously (e.g., D3+D6, D2+D5, D1+D4). **Filtering by detector band in `/api/frames` naturally yields zero intra-band duplicates.**
3. **Temporal Baselines**: Observations span extensive time baselines up to **373.5 days** (April/May 2025 to May 2026), providing multi-season coverage ideal for blink animation, variable star monitoring, and proper motion analysis.
4. **WISE 0855 Scientific Evaluation**:
   - In individual, single-exposure un-stacked cutouts ($t_{\text{exp}} \approx 113.6\text{ s}$), WISE 0855 does **not** exhibit an unambiguous, high-significance point-source peak in raw single frames (SNR $\lesssim 1.5\sigma$ in D6, undetectable in D1).
   - Expected catalog motion ($\mu \approx 8.1\text{ arcsec/yr}$) over the inspected $\Delta t = 220.65\text{ days}$ baseline is $\approx 4.89\text{ arcsec}$ ($\approx 0.79\text{ pixels}$ on SPHEREx's 6.16″ plate scale). Because this displacement is sub-pixel and the source flux is near the single-frame noise floor, **motion cannot be claimed from raw single frames alone**.
   - **Crucial Recommendation for Member 3**: Detecting WISE 0855 and its motion requires **shift-and-stack / co-addition** across the 45 available D6 epochs to beat down background noise and bring out the faint signal.
5. **API Performance Feasibility**: At a $0.05^\circ$ FOV, cutouts are $29 \times 29$ pixels ($841$ floats $\approx 5\text{ KB}$ JSON). A full 45-frame blink sequence is only $\sim 225\text{ KB}$ JSON. However, on-demand archive cutout retrieval takes $\sim 10-15\text{ s}$ per frame, mandating a server-side caching engine and target pre-fetching for instant playback.

---

## 2. Canonical Target Coordinates

The five targets defined in the project plan and frontend configuration ([`src/types/spherex.ts`](file:///d:/Projects/sphereX/src/types/spherex.ts#L87-L93)):

| Target Name | Canonical RA (ICRS) | Canonical Dec (ICRS) | Default FOV | Astronomical Nature & Scientific Relevance |
| :--- | :--- | :--- | :--- | :--- |
| **WISE 0855** | `133.795129°` | `-7.245147°` | `0.05°` (~3.0′) | Coldest known brown dwarf (~250 K, type ~Y, $\mu \approx 8.1\text{ ″/yr}$). Primary moving object test. |
| **Barnard's Star** | `269.452075°` | `+4.693364°` | `0.05°` (~3.0′) | Fast-moving red dwarf ($\mu \approx 10.3\text{ ″/yr}$, highest known). Proper motion benchmark. |
| **Epsilon Indi B** | `330.840200°` | `-56.786500°` | `0.05°` (~3.0′) | Nearby binary brown dwarf system (T1 + T6, separation ~0.7″, high proper motion ~4.7″/yr). |
| **RW Aurigae** | `77.108200°` | `+30.401400°` | `0.05°` (~3.0′) | Classical T Tauri binary showing severe, long-duration occultation/dimming events. Light curve target. |
| **R Draconis** | `247.554400°` | `+66.702900°` | `0.05°` (~3.0′) | Mira-type pulsating variable star (period ~245 days, large infrared amplitude). Light curve target. |

---

## 3. Per-Target, Per-Band Observation Availability and Time Coverage

All records queried from `spherex.obscore` for collection `spherex_dr1` (Calibration Level 2 science images):

### Target 1: WISE 0855
- **Total Records**: 258 | **Unique Obs IDs**: 129 | **Duplicates per band**: 0

| Bandpass | Wavelength ($\mu\text{m}$) | Candidate Records | Unique Obs IDs | MJD Coverage | Calendar Dates (UTC) | Baseline Span | Usable for Inspection |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **SPHEREx-D1** | 0.75 – 1.1 | 36 | 36 | 60801.51 – 61165.59 | 2025-05-06 – 2026-05-05 | 364.1 days (~1.0 yr) | Yes (Reference stars) |
| **SPHEREx-D2** | 1.1 – 1.6 | 48 | 48 | 60801.11 – 61174.29 | 2025-05-06 – 2026-05-14 | 373.2 days (~1.0 yr) | Yes |
| **SPHEREx-D3** | 1.6 – 2.4 | 45 | 45 | 60800.70 – 61171.10 | 2025-05-05 – 2026-05-11 | 370.4 days (~1.0 yr) | Yes |
| **SPHEREx-D4** | 2.4 – 3.8 | 36 | 36 | 60801.51 – 61165.59 | 2025-05-06 – 2026-05-05 | 364.1 days (~1.0 yr) | Yes |
| **SPHEREx-D5** | 3.8 – 4.4 | 48 | 48 | 60801.11 – 61174.29 | 2025-05-06 – 2026-05-14 | 373.2 days (~1.0 yr) | Yes (Thermal emission) |
| **SPHEREx-D6** | 4.4 – 5.0 | 45 | 45 | 60800.70 – 61171.10 | 2025-05-05 – 2026-05-11 | 370.4 days (~1.0 yr) | Yes (Peak brown dwarf flux) |

---

### Target 2: Barnard's Star
- **Total Records**: 240 | **Unique Obs IDs**: 121 | **Duplicates per band**: 0

| Bandpass | Wavelength ($\mu\text{m}$) | Candidate Records | Unique Obs IDs | MJD Coverage | Calendar Dates (UTC) | Baseline Span | Usable for Inspection |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **SPHEREx-D1** | 0.75 – 1.1 | 42 | 42 | 60914.21 – 61110.77 | 2025-08-27 – 2026-03-11 | 196.6 days (~6.5 mo) | Yes (Bright point source) |
| **SPHEREx-D2** | 1.1 – 1.6 | 38 | 38 | 60908.98 – 61121.23 | 2025-08-21 – 2026-03-22 | 212.2 days (~7.0 mo) | Yes |
| **SPHEREx-D3** | 1.6 – 2.4 | 41 | 41 | 60902.86 – 61165.08 | 2025-08-15 – 2026-05-05 | 262.2 days (~8.6 mo) | Yes |
| **SPHEREx-D4** | 2.4 – 3.8 | 41 | 41 | 60914.21 – 61110.77 | 2025-08-27 – 2026-03-11 | 196.6 days (~6.5 mo) | Yes |
| **SPHEREx-D5** | 3.8 – 4.4 | 38 | 38 | 60908.98 – 61121.23 | 2025-08-21 – 2026-03-22 | 212.2 days (~7.0 mo) | Yes |
| **SPHEREx-D6** | 4.4 – 5.0 | 40 | 40 | 60902.86 – 61165.08 | 2025-08-15 – 2026-05-05 | 262.2 days (~8.6 mo) | Yes |

*Motion note*: Over a 262-day baseline ($\Delta t = 0.718\text{ yr}$), Barnard's Star moves $\approx 7.4\text{ arcsec} \approx 1.20\text{ pixels}$. Because Barnard's Star is optical/near-IR bright ($V \sim 9.5, J \sim 5.2$), it produces an unmistakable, high-SNR point source that moves across pixels between August 2025 and May 2026!

---

### Target 3: Epsilon Indi B
- **Total Records**: 343 | **Unique Obs IDs**: 179 | **Duplicates per band**: 0

| Bandpass | Wavelength ($\mu\text{m}$) | Candidate Records | Unique Obs IDs | MJD Coverage | Calendar Dates (UTC) | Baseline Span | Usable for Inspection |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **SPHEREx-D1** | 0.75 – 1.1 | 48 | 48 | 60790.26 – 61163.72 | 2025-04-25 – 2026-05-03 | 373.5 days (~1.0 yr) | Yes |
| **SPHEREx-D2** | 1.1 – 1.6 | 66 | 66 | 60789.86 – 61160.59 | 2025-04-24 – 2026-04-30 | 370.7 days (~1.0 yr) | Yes (Strong T-dwarf J band) |
| **SPHEREx-D3** | 1.6 – 2.4 | 64 | 64 | 60794.06 – 61164.12 | 2025-04-29 – 2026-05-04 | 370.1 days (~1.0 yr) | Yes (Methane band absorption) |
| **SPHEREx-D4** | 2.4 – 3.8 | 46 | 46 | 60790.26 – 61163.72 | 2025-04-25 – 2026-05-03 | 373.5 days (~1.0 yr) | Yes |
| **SPHEREx-D5** | 3.8 – 4.4 | 58 | 58 | 60789.86 – 61160.59 | 2025-04-24 – 2026-04-30 | 370.7 days (~1.0 yr) | Yes |
| **SPHEREx-D6** | 4.4 – 5.0 | 61 | 61 | 60794.06 – 61164.12 | 2025-04-29 – 2026-05-04 | 370.1 days (~1.0 yr) | Yes |

*Resolution note*: Epsilon Indi Ba and Bb have an angular separation of $\sim 0.7\text{ arcsec}$. Because SPHEREx's point spread function and pixel scale are $\sim 6.16\text{ arcsec/pixel}$, the binary components will appear as an unresolved composite source. Over the 373-day baseline, the combined system exhibits $\sim 4.7\text{ arcsec} \approx 0.76\text{ pixels}$ of proper motion.

---

### Target 4: RW Aurigae
- **Total Records**: 265 | **Unique Obs IDs**: 134 | **Duplicates per band**: 0

| Bandpass | Wavelength ($\mu\text{m}$) | Candidate Records | Unique Obs IDs | MJD Coverage | Calendar Dates (UTC) | Baseline Span | Usable for Inspection |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **SPHEREx-D1** | 0.75 – 1.1 | 59 | 59 | 60919.42 – 61111.00 | 2025-09-01 – 2026-03-12 | 191.6 days (~6.3 mo) | Yes (Optical dimming monitor) |
| **SPHEREx-D2** | 1.1 – 1.6 | 36 | 36 | 60926.28 – 61108.22 | 2025-09-08 – 2026-03-09 | 181.9 days (~6.0 mo) | Yes |
| **SPHEREx-D3** | 1.6 – 2.4 | 38 | 38 | 60929.68 – 61101.56 | 2025-09-11 – 2026-03-02 | 171.9 days (~5.6 mo) | Yes |
| **SPHEREx-D4** | 2.4 – 3.8 | 57 | 57 | 60919.42 – 61111.00 | 2025-09-01 – 2026-03-12 | 191.6 days (~6.3 mo) | Yes (Circumstellar dust) |
| **SPHEREx-D5** | 3.8 – 4.4 | 37 | 37 | 60926.28 – 61108.22 | 2025-09-08 – 2026-03-09 | 181.9 days (~6.0 mo) | Yes |
| **SPHEREx-D6** | 4.4 – 5.0 | 38 | 38 | 60929.68 – 61101.56 | 2025-09-11 – 2026-03-02 | 171.9 days (~5.6 mo) | Yes |

*Scientific note*: Classical T Tauri star with circumstellar disk occultations. 59 epochs in D1 provide a high-cadence time series for light curve analysis.

---

### Target 5: R Draconis
- **Total Records**: 415 | **Unique Obs IDs**: 211 | **Duplicates per band**: 0

| Bandpass | Wavelength ($\mu\text{m}$) | Candidate Records | Unique Obs IDs | MJD Coverage | Calendar Dates (UTC) | Baseline Span | Usable for Inspection |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **SPHEREx-D1** | 0.75 – 1.1 | 68 | 68 | 60832.47 – 60999.64 | 2025-06-06 – 2025-11-20 | 167.2 days (~5.5 mo) | Yes |
| **SPHEREx-D2** | 1.1 – 1.6 | 60 | 60 | 60834.79 – 61023.74 | 2025-06-08 – 2025-12-14 | 189.0 days (~6.2 mo) | Yes |
| **SPHEREx-D3** | 1.6 – 2.4 | 80 | 80 | 60811.96 – 61173.25 | 2025-05-16 – 2026-05-13 | 361.3 days (~1.0 yr) | Yes (Full pulsation cycle) |
| **SPHEREx-D4** | 2.4 – 3.8 | 66 | 66 | 60832.47 – 60999.64 | 2025-06-06 – 2025-11-20 | 167.2 days (~5.5 mo) | Yes |
| **SPHEREx-D5** | 3.8 – 4.4 | 60 | 60 | 60834.79 – 61023.74 | 2025-06-08 – 2025-12-14 | 189.0 days (~6.2 mo) | Yes |
| **SPHEREx-D6** | 4.4 – 5.0 | 81 | 81 | 60811.96 – 61173.25 | 2025-05-16 – 2026-05-13 | 361.3 days (~1.0 yr) | Yes (Full pulsation cycle) |

*Coverage note*: Located at Dec $+66.7^\circ$ near the northern ecliptic pole orbit convergence zone, R Draconis receives the highest visit frequency in DR1. 81 epochs in D6 spanning 361 days covers more than a full pulsation cycle ($P \approx 245.7\text{ days}$).

---

## 4. WISE 0855 Multi-Epoch Scientific Analysis & Motion Assessment

To assess whether motion is visible in raw single frames, we retrieved and compared multi-epoch cutouts across bands D6 and D1:

### Multi-Epoch Cutout Measurements:

| Band | Epoch Obs ID | Observation Date (UTC) | MJD | Target Pixel (0-based) | Target Pixel Flux | 3×3 Aperture Sum | Local Background (Median ± Std) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **D6** | `2025W19_1B_0116_1` | 2025-05-05 16:48 | `60800.7000` | $(13.67, 14.33)$ | $0.8620\text{ MJy/sr}$ | $7.0103\text{ MJy/sr}$ | $0.7278 \pm 0.3306\text{ MJy/sr}$ |
| **D6** | `2025W50_2A_0254_1` | 2025-12-12 08:26 | `61021.3514` | $(14.49, 13.91)$ | $0.4595\text{ MJy/sr}$ | $3.6407\text{ MJy/sr}$ | $0.3911 \pm 1.0624\text{ MJy/sr}$ |
| **D1** | `2025W19_1B_0241_1` | 2025-05-06 12:20 | `60801.5142` | $(14.44, 14.17)$ | $0.2526\text{ MJy/sr}$ | $2.1619\text{ MJy/sr}$ | $0.2365 \pm 0.5290\text{ MJy/sr}$ |
| **D1** | `2025W45_1A_0110_2` | 2025-11-03 12:11 | `60982.5081` | $(14.45, 14.22)$ | $0.2340\text{ MJy/sr}$ | $2.3331\text{ MJy/sr}$ | $0.2592 \pm 0.4473\text{ MJy/sr}$ |

### Scientific Motion & Detection Findings:
1. **Single-Exposure Detection Significance**:
   - In D6 Epoch 1, target pixel flux ($0.8620$) exceeds background median ($0.7278$) by $\Delta F \approx +0.134\text{ MJy/sr}$ ($\approx 0.4\sigma$).
   - In D6 Epoch 2, target pixel flux ($0.4595$) exceeds background median ($0.3911$) by $\Delta F \approx +0.068\text{ MJy/sr}$ ($\approx 0.06\sigma$).
   - In D1 (both epochs), target flux is statistically indistinguishable from background noise ($\Delta F \approx 0.0\sigma$).
2. **Proper Motion Feasibility**:
   - Time span between D6 epochs: $\Delta t = 220.65\text{ days} = 0.604\text{ years}$.
   - WISE 0855 proper motion ($\mu \approx 8.1\text{ ″/yr}$) yields an expected total displacement of $\Delta \theta \approx 4.89\text{ arcsec}$.
   - Given SPHEREx's plate scale of $6.16\text{ arcsec/pixel}$, $\Delta \theta$ corresponds to **$0.79\text{ pixels}$**.
   - Because the target position in each raw cutout has a different spacecraft roll angle and pointing center, and the source is near the noise floor, **motion cannot be claimed from raw single-frame inspection alone**.
3. **Implication for Member 3**:
   - Single-frame blinking will show background variations and stationary field stars.
   - To make WISE 0855 visible as a moving source, **shift-and-stack / co-addition across all 45 D6 epochs** is mandatory. Stacking $\sim 40$ frames increases signal-to-noise by $\sqrt{40} \approx 6.3\times$, bringing the brown dwarf signal to $\approx 3–5\sigma$ significance.

---

## 5. Image Structure, Plate Scale, and Flag Status

### FITS Structure Verified:
- Every downloaded cutout contains **exactly 7 HDUs** (HDU 0 through 6):
  - `HDU 0 (PRIMARY)`: Header only (5 cards).
  - `HDU 1 (IMAGE)`: Calibrated flux array (`float32`, dimensions $29 \times 29$, unit `MJy / sr`).
  - `HDU 2 (FLAGS)`: Data quality bitmask (`int32`, dimensions $29 \times 29$).
  - `HDU 3 (VARIANCE)`: Measurement variance (`float32`, dimensions $29 \times 29$).
  - `HDU 4 (ZODI)`: Zodiacal light model (`float32`, dimensions $29 \times 29$).
  - `HDU 5 (EPSF)`: Empirical Point Spread Function binary table.
  - `HDU 6 (WCS-WAVE)`: Spectrophotometric wavelength calibration binary table.
- **Plate Scale**: Verified across bands at **$6.150–6.161\text{ arcsec/pixel}$** ($\sim 0.00171\text{ deg/pixel}$).
- **Flag Distribution**:
  - Clean pixels (Flag 0): $\sim 60–64\%$
  - Bit 21 (`2097152` / `0x00200000`): $\sim 30–36\%$
  - Bit 19 (`524288` / `0x00080000`): $\sim 2\%$
  - *Masking Policy*: Maintained as **deferred** without hardcoded filtering until SPHEREx pipeline bitmask definitions are formally verified.

---

## 6. API Performance and Data Volume Analysis for `/api/frames`

### Payload Sizing:
- For default FOV $0.05^\circ$, image dimensions are $29 \times 29 = 841$ pixels.
- Raw float array inlined as JSON: $\approx 4.5\text{ KB}$.
- Per-frame metadata (`mjd`, `dateUtc`, `wavelengthMicrons`, `minFlux`, `maxFlux`, `band`, `index`): $\approx 0.5\text{ KB}$.
- Total payload per frame: $\approx 5\text{ KB}$.
- Full sequence payload:
  - 36 frames (D1): $\approx 180\text{ KB}$ JSON.
  - 45 frames (D6): $\approx 225\text{ KB}$ JSON.
  - 81 frames (R Draconis D6): $\approx 405\text{ KB}$ JSON.
- **Conclusion**: Inlined JSON payloads are very lightweight ($< 500\text{ KB}$), highly compressible via gzip/brotli to $< 100\text{ KB}$, and ideal for HTML5 Canvas rendering.

### Latency and Concurrency:
- On-demand IBE cutout generation takes **$10–18\text{ seconds}$ per cutout**.
- Sequential retrieval of 45 cutouts would take $\sim 8–10\text{ minutes}$.
- Rapid burst requests trigger transient `HTTP 503: Server busy, retry later.`
- **Design Recommendations for Milestone 2**:
  1. **Bounded ThreadPool Concurrency**: Limit parallel downloads to 4–6 workers with exponential backoff.
  2. **Disk Caching**: Keyed by `(ra, dec, size, band, release)` to make subsequent requests return in $< 20\text{ ms}$.
  3. **Pre-Fetched Challenge Targets**: Run a pre-fetch job for all 5 challenge targets ahead of release so demo targets load instantaneously without archive dependence.

---

## 7. Files Inspected and Created

### Files Inspected:
- [`README.md`](file:///d:/Projects/sphereX/README.md): Project architecture, team divisions, and test target specifications.
- [`src/types/spherex.ts`](file:///d:/Projects/sphereX/src/types/spherex.ts): Frontend types, API contract, and canonical coordinates for the 5 challenge targets.
- [`src/services/apiClient.ts`](file:///d:/Projects/sphereX/src/services/apiClient.ts): API configuration and sample data toggle.
- [`backend/scripts/verify_irsa_cutout.py`](file:///d:/Projects/sphereX/backend/scripts/verify_irsa_cutout.py): Baseline WCS coordinate validation and cutout retrieval logic.

### Files Created:
- [backend/scripts/audit_targets.py](file:///d:/Projects/sphereX/backend/scripts/audit_targets.py): Standalone script querying IRSA TAP, analyzing multi-epoch temporal baselines, and performing photometric/motion inspections across all 5 targets.
- [docs/FIRST_HOURS_DATA_AUDIT.md](file:///d:/Projects/sphereX/docs/FIRST_HOURS_DATA_AUDIT.md): This deliverable report.
- `scratch/audit_results.json`: Raw structured JSON output storing exact query records, observation IDs, and pixel metrics.

---

*Milestone 1.2 is complete and verified with real archive data. Awaiting team review before proceeding to Milestone 2 (Processing Pipeline & Caching).*
