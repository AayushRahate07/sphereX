# SPHEREx Sky Viewer — Milestone 2.4B: Scientific Validation of WISE 0855 Motion Claim

**Date**: 2026-11-14
**Author**: Member 1 (IRSA Data Retrieval & Processing)
**Status**: Validated, Refuted as Direct Detection, and Scientifically Reclassified
**Milestone Scope**: Validate the reported 8.23-arcsecond displacement between the May 5, 2025 and December 12, 2025 SPHEREx D6 observations before describing it as measured proper motion.

---

## 1. Executive Summary

Milestone 2.4B performed an independent, authoritative astrometric and centroid validation of the reported 8.23-arcsecond displacement between SPHEREx observations `2025W19_1B_0116_1` (May 5, 2025) and `2025W50_2A_0254_1` (Dec 12, 2025).

### Critical Scientific Findings:
1. **Mathematical Reproducibility vs. Physical Reality**:
   - The reported 8.23-arcsecond shift is **100% mathematically reproducible** under the specific scratch script settings ($7 \times 7$ box with median clipping).
   - However, rigorous astrometric analysis proves this number is **NOT a physical detection of WISE 0855's proper motion**.
2. **The 15-Year Proper Motion Offset (Target Outside Cutout)**:
   - The canonical target coordinates defined in the project (`RA = 133.795129°, Dec = -7.245147°`) correspond to the discovery epoch ($\sim 2010.54$, Luhman 2014).
   - Because WISE 0855 has an extreme proper motion ($\mu_\alpha \cos\delta = -8,123.7\text{ mas/yr}$, $\mu_\delta = +673.2\text{ mas/yr}$), it moved **120.7 arcseconds (~2.0 arcminutes) Westward** between 2010 and 2025.
   - On the requested $0.05^\circ$ ($180''$ FOV, $\pm 90''$ half-width) common grid, the true position of WISE 0855 in May 2025 is at pixel $(x = 33.51, y = 15.62)$, and in December 2025 at $(x = 34.31, y = 15.68)$.
   - **The brown dwarf is located ~30.7 arcseconds (~5 pixels) outside the Western edge of the $29 \times 29$ cutout!**
3. **True Astrometric Displacement over 220.65 Days**:
   - The true expected on-sky displacement over the 220.65-day interval ($\Delta t = 0.60411\text{ yr}$) is **4.16 arcseconds (0.675 pixels)**, composed of:
     - Proper Motion: $4.92''$ ($4.91''$ Westward, $0.41''$ Northward)
     - Annual Parallax: $0.81''$ ($0.75''$ Eastward, $0.32''$ Southward), which **opposes** proper motion.
   - The reported 8.23 arcsec is nearly double the true physical on-sky motion ($4.16''$).
4. **Centroid Instability**:
   - In the $7 \times 7$ box around $(14, 14)$, there is only diffuse zodiacal background ($\sim 0.40 - 0.75\text{ MJy/sr}$).
   - In Epoch 3, a minor noise fluctuation at the bottom-right corner pixel $(x=17, y=11)$ with flux $0.59\text{ MJy/sr}$ biased the unweighted center-of-mass, creating an apparent 1.34-pixel (8.23 arcsec) vector shift. Varying the box size causes the shift to swing wildly from $0.04''$ to $11.12''$.
5. **Mandatory Scientific Reclassification**:
   - The result must be labeled as an **apparent centroid displacement of the background patch**, and **explicitly refuted** as a verified proper-motion measurement of WISE 0855.

---

## 2. Independent Reproduction of the Reported Result

Using the cached Level 2 cutouts in `backend/cache/fits/`:
- `spherex_dr1_2025W19_1B_0116_1_SPHEREx-D6_0.0500.fits`
- `spherex_dr1_2025W50_2A_0254_1_SPHEREx-D6_0.0500.fits`

### Observation Metadata from Science HDU (`IMAGE` HDU)
- **Epoch 1 (`2025W19_1B_0116_1`)**:
  - `DATE-OBS`: `2025-05-05T16:48:02.459 UTC`
  - `MJD-OBS`: `60800.700028461`
  - `EXPTIME`: `113.5826 s`
  - Bandpass: `SPHEREx-D6` ($\lambda_{\text{cen}} \approx 5.001\ \mu\text{m}$)
- **Epoch 3 (`2025W50_2A_0254_1`)**:
  - `DATE-OBS`: `2025-12-12T08:26:02.508 UTC`
  - `MJD-OBS`: `61021.351417917`
  - `EXPTIME`: `113.5826 s`
  - Bandpass: `SPHEREx-D6` ($\lambda_{\text{cen}} \approx 5.001\ \mu\text{m}$)
- **Elapsed Time**: $\Delta t = 220.651389\text{ days} = 0.604111\text{ Julian years}$.

### Reprojection & Scratch Centroid Replication
- **Common Grid**: $29 \times 29$ pixels, centered at $(\text{RA} = 133.795129^\circ, \text{Dec} = -7.245147^\circ)$, plate scale $6.1632''/\text{pixel}$ ($0.0017120^\circ/\text{pixel}$).
- **Nominal Center**: Exactly $(x = 14.000, y = 14.000)$.
- **Scratch Method**: $7 \times 7$ box ($x \in [11, 17], y \in [11, 17]$) with `sub_clipped = np.clip(sub_flux - np.median(sub_flux), 0, None)`:
  - Epoch 1 centroid: $(x = 13.673, y = 13.890)$
  - Epoch 3 centroid: $(x = 14.870, y = 13.298)$
  - $\Delta x = +1.198\text{ pixels}$
  - $\Delta y = -0.592\text{ pixels}$
  - $\Delta r = \sqrt{(+1.198)^2 + (-0.592)^2} = 1.336\text{ pixels} = \mathbf{8.234\text{ arcseconds}}$.

**Conclusion**: The calculation is 100% reproducible, but represents noise-induced aperture shift, not stellar motion.

---

## 3. Astrometric Analysis: Proper Motion & Annual Parallax

### 3.1 Authoritative Astrometric Parameters (Kirkpatrick et al. 2021; Luhman 2014)
- **Proper Motion in RA ($\mu_\alpha \cos\delta$)**: $-8,123.7 \pm 1.3\text{ mas/yr} = -8.1237''/\text{yr}$ (Westward)
- **Proper Motion in Dec ($\mu_\delta$)**: $+673.2 \pm 1.3\text{ mas/yr} = +0.6732''/\text{yr}$ (Northward)
- **Total Proper Motion Rate**: $\mu_{\text{tot}} = 8.1515''/\text{yr}$
- **Trigonometric Parallax ($\varpi$)**: $439.0 \pm 2.4\text{ mas} = 0.4390''$ ($d = 2.278\text{ pc}$)

### 3.2 Expected Displacement over $\Delta t = 0.604111\text{ yr}$

#### A. Proper Motion Component (Linear Drift)
$$\Delta(\alpha \cos\delta)_{\text{PM}} = -8.1237''/\text{yr} \times 0.604111\text{ yr} = -4.9076'' \text{ (Westward)}$$
$$\Delta\delta_{\text{PM}} = +0.6732''/\text{yr} \times 0.604111\text{ yr} = +0.4067'' \text{ (Northward)}$$
$$\Delta r_{\text{PM}} = \sqrt{(-4.9076)^2 + (+0.4067)^2} = \mathbf{4.9244''}$$

#### B. Earth Orbit & Annual Parallax Reflex Vector
Using Earth's barycentric position $\mathbf{r}_{\oplus}(t)$ in AU:
- Epoch 1 (May 05, 2025): $\mathbf{r}_{\oplus} = (-0.7169, -0.6603, -0.2861)\text{ AU}$
  - Reflex Parallax on sky: $\Delta(\alpha \cos\delta)_{\text{plx}, 1} = -0.4278''$, $\Delta\delta_{\text{plx}, 1} = +0.1235''$
- Epoch 3 (Dec 12, 2025): $\mathbf{r}_{\oplus} = (+0.1644, +0.8851, +0.3838)\text{ AU}$
  - Reflex Parallax on sky: $\Delta(\alpha \cos\delta)_{\text{plx}, 3} = +0.3210''$, $\Delta\delta_{\text{plx}, 3} = -0.1962''$
- **Parallax Reflex Change ($\text{Epoch } 3 - \text{Epoch } 1$)**:
  $$\Delta(\alpha \cos\delta)_{\text{plx}} = +0.7488'' \text{ (Eastward)}$$
  $$\Delta\delta_{\text{plx}} = -0.3197'' \text{ (Southward)}$$
  $$\Delta r_{\text{plx}} = \mathbf{0.8142''}$$

*Note*: Because Earth moved towards the positive Y / positive X quadrant in December relative to May, the reflex parallax vector **opposes** the westward proper motion, reducing the net on-sky displacement.

#### C. Total True On-Sky Astrometric Displacement
$$\Delta(\alpha \cos\delta)_{\text{total}} = -4.9076'' + 0.7488'' = \mathbf{-4.1588''} \text{ (Westward)}$$
$$\Delta\delta_{\text{total}} = +0.4067'' - 0.3197'' = \mathbf{+0.0870''} \text{ (Northward)}$$
$$\Delta r_{\text{total}} = \sqrt{(-4.1588)^2 + (+0.0870)^2} = \mathbf{4.1597''}$$

#### D. Expected Shift on SPHEREx Common Grid (Plate Scale $6.1632''/\text{pix}$)
$$\Delta x = -\frac{\Delta(\alpha \cos\delta)_{\text{total}}}{\text{scale}} = -\frac{-4.1588''}{6.1632''/\text{pix}} = \mathbf{+0.6748\text{ pixels}}$$
$$\Delta y = +\frac{\Delta\delta_{\text{total}}}{\text{scale}} = +\frac{+0.0870''}{6.1632''/\text{pix}} = \mathbf{+0.0141\text{ pixels}}$$
$$\Delta r_{\text{pix}} = \mathbf{0.6749\text{ pixels}} \implies \mathbf{4.16\text{ arcseconds}}$$

**Verdict**: The true physical displacement is **4.16 arcseconds**, not 8.23 arcseconds.

---

## 4. The 15-Year Proper Motion Gap: Target is Outside the $0.05^\circ$ Cutout

The fundamental reason the scratch centroid script measured background noise instead of WISE 0855 is that **the brown dwarf was not inside the $29 \times 29$ image**:

1. **Origin of Coordinates**:
   `RA = 133.795129°, Dec = -7.245147°` is the discovery position from Luhman (2014), measured in June 2010 (Epoch $\sim 2010.54$).
2. **Elapsed Proper Motion**:
   Between 2010.54 and May 2025 (14.9 years):
   $$\Delta(\alpha \cos\delta) \approx -8.1237''/\text{yr} \times 14.9\text{ yr} = -121.28'' \text{ Westward}$$
   $$\Delta\delta \approx +0.6732''/\text{yr} \times 14.9\text{ yr} = +10.05'' \text{ Northward}$$
3. **True Coordinates in 2025**:
   - May 05, 2025: $\text{RA} = 133.761457^\circ, \text{Dec} = -7.242378^\circ$
   - Dec 12, 2025: $\text{RA} = 133.760083^\circ, \text{Dec} = -7.242265^\circ$
4. **Grid Coordinates**:
   - $0.05^\circ$ cutout half-width is $90.0''$ ($14.5$ pixels). Grid pixel bounds are $[0, 28]$.
   - Target position in May 2025 projects to: $(x = 33.51, y = 15.62)$ $\implies$ **5.5 pixels beyond the Western edge!**
   - Target position in Dec 2025 projects to: $(x = 34.31, y = 15.68)$ $\implies$ **6.3 pixels beyond the Western edge!**

---

## 5. Centroid Robustness & Vulnerability Analysis

To understand why the $7 \times 7$ box produced $8.23''$, we tested 12 combinations of box radius ($3 \times 3$ to $9 \times 9$) and background estimators on the reprojected frames:

| Box Size | Background Method | Epoch 1 Centroid $(x, y)$ | Epoch 3 Centroid $(x, y)$ | Measured $\Delta x, \Delta y$ | Measured Shift |
|---|---|---|---|---|---|
| **$3 \times 3$** | Median | $(13.765, 14.242)$ | $(14.128, 14.016)$ | $(+0.363, -0.226)$ | **$0.428\text{ px} = 2.64''$** |
| **$3 \times 3$** | Minimum | $(14.002, 14.192)$ | $(14.037, 14.118)$ | $(+0.034, -0.074)$ | **$0.081\text{ px} = 0.50''$** |
| **$3 \times 3$** | None | $(14.000, 14.021)$ | $(14.005, 14.017)$ | $(+0.005, -0.003)$ | **$0.006\text{ px} = 0.04''$** |
| **$5 \times 5$** | Median | $(14.153, 14.275)$ | $(14.196, 14.517)$ | $(+0.043, +0.242)$ | **$0.246\text{ px} = 1.51''$** |
| **$5 \times 5$** | Minimum | $(14.153, 14.129)$ | $(13.947, 14.104)$ | $(-0.206, -0.025)$ | **$0.207\text{ px} = 1.28''$** |
| **$5 \times 5$** | None | $(14.015, 14.012)$ | $(13.993, 14.014)$ | $(-0.022, +0.002)$ | **$0.022\text{ px} = 0.14''$** |
| **$7 \times 7$** | **Median (scratch)** | $(13.673, 13.890)$ | $(14.870, 13.298)$ | $(+1.198, -0.592)$ | **$1.336\text{ px} = 8.23''$** |
| **$7 \times 7$** | Minimum | $(13.837, 13.881)$ | $(14.298, 13.819)$ | $(+0.461, -0.062)$ | **$0.465\text{ px} = 2.87''$** |
| **$7 \times 7$** | None | $(13.971, 13.979)$ | $(14.043, 13.974)$ | $(+0.072, -0.006)$ | **$0.072\text{ px} = 0.44''$** |
| **$9 \times 9$** | Median | $(14.077, 13.364)$ | $(15.855, 13.056)$ | $(+1.778, -0.308)$ | **$1.805\text{ px} = 11.12''$** |
| **$9 \times 9$** | Minimum | $(14.061, 13.827)$ | $(14.722, 13.709)$ | $(+0.661, -0.119)$ | **$0.672\text{ px} = 4.14''$** |
| **$9 \times 9$** | None | $(14.053, 13.970)$ | $(14.109, 13.956)$ | $(+0.057, -0.014)$ | **$0.058\text{ px} = 0.36''$** |

### Mechanism of Bias:
1. In empty, background-dominated sky, flux values are $\sim 0.40 - 0.75\text{ MJy/sr}$ with Gaussian noise $\sigma \approx 0.05\text{ MJy/sr}$.
2. In Epoch 3, pixel $(x=17, y=11)$ has flux $0.5910\text{ MJy/sr}$ (a $+3.8\sigma$ noise/background fluctuation).
3. In a $7 \times 7$ box, subtracting median ($0.4038\text{ MJy/sr}$) leaves a positive residual at the extreme corner, exerting a large moment arm that pulls `com_x` by $+0.87$ px and `com_y` by $-0.70$ px.
4. Expanding the box to $9 \times 9$ amplifies the lever arm to $11.12''$; shrinking to $5 \times 5$ cuts off the pixel, reducing the shift to $1.51''$.

---

## 6. Scientifically Cautious Conclusions & Non-Claims

1. **Non-Claim on 8.23 Arcseconds**:
   The 8.23-arcsecond displacement reported in Milestone 2.4A is **not** proper motion. It is an artifact of background noise and aperture truncation acting on an empty sky region.
2. **Target Position Reality**:
   Because of WISE 0855's extreme proper motion, the object at observation epoch (2025) is located **outside** the $0.05^\circ$ ($29 \times 29$) field of view when centered on 2010 discovery coordinates.
3. **True Physical Motion**:
   Between May 5, 2025 and December 12, 2025, WISE 0855 physically displaced by **4.16 arcseconds (0.675 pixels)** Westward ($\text{PM} + \text{Parallax}$).
4. **Prerequisites for Quantitative Astrometry**:
   - Proper-motion-propagated targeting or a wider FOV ($\ge 0.08^\circ / 48 \times 48\text{ pixels}$) to encompass the target.
   - Point Spread Function (PSF) fitting photometry with local zodiacal background modeling.
   - Quality-mask weighting and cosmic ray rejection.

---

## 7. Verification & Working Tree State

- **Backend Pytest**: **63 passed in 2.26s**.
- **Working Tree (`git status --short`)**:
  ```text
   M package-lock.json
   M src/App.tsx
   M src/services/apiClient.ts
   M src/types/spherex.ts
   M src/utils/urlState.ts
   M vite.config.ts
  ?? backend/
  ?? docs/
  ```
- **Integrity**: Member 2 UI components remain untouched; no Git modifications or unauthorized dependencies added.
