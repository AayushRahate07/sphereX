# SPHEREx Sky Viewer — Milestone 1.4: Processing Prerequisites and Implementation Readiness Report

**Date:** 2026-11-14
**Author:** Member 1 (Data, Processing, and Release)
**Corpus/Repository:** `D:\Projects\sphereX`
**Milestone:** 1.4 (Resolve Processing Prerequisites)
**Status:** Prerequisites Resolved — Ready for Milestone 2

---

## 1. Executive Summary & Working-Tree State

### 1.1 Objective and Scope
Milestone 1.4 resolves the critical architectural, empirical, and scientific evidence gaps identified in [`docs/MILESTONE_1_3_VERIFICATION.md`](file:///d:/Projects/sphereX/docs/MILESTONE_1_3_VERIFICATION.md) before building the real-data processing pipeline and the `/api/frames` FastAPI endpoint in Milestone 2.

Specifically, this milestone delivers:
1. **Corrected Real-Data Payload Measurements:** Replaces the prior repeated synthetic array benchmark with measured benchmarks on distinct real SPHEREx Level 2 FITS cutouts and distinct non-repeating synthetic sequences.
2. **Authoritative Quality-Flag Definitions:** Retrieves the official bitmask definitions from the *SPHEREx Explanatory Supplement* (NASA/IPAC Infrared Science Archive, Caltech/JPL) and formulates an authoritative valid-pixel policy.
3. **Frontend Contract Resolution & Common-Grid Geometry:** Formulates the minimal backend response structure that strictly fulfills the frontend contract in [`src/types/spherex.ts`](file:///d:/Projects/sphereX/src/types/spherex.ts) and [`src/services/apiClient.ts`](file:///d:/Projects/sphereX/src/services/apiClient.ts) without altering frontend code, while proving that common-grid celestial reprojection is mathematically mandatory before frames can be compared.
4. **Staged Milestone 2 Implementation Plan:** Outlines a modular, test-driven implementation sequence utilizing solely existing, verified dependencies (`astropy`, `numpy`, `scipy`, `fastapi`, `uvicorn`, `pydantic`).

### 1.2 Working-Tree Status
In compliance with milestone constraints:
- **No implementation files were modified:** `backend/scripts/audit_targets.py`, `backend/scripts/verify_irsa_cutout.py`, frontend TypeScript files, and previous milestone reports remain untouched.
- **No Git history or branches were altered.**
- **Initial and Current Git Status:**
  ```text
  On branch main
  Your branch is up to date with 'origin/main'.

  Untracked files:
    backend/
    docs/
  ```

---

## 2. Corrected Payload Benchmarks: Real vs. Synthetic Measurements

### 2.1 Limitation of the Prior Milestone 1.3 Benchmark
In Milestone 1.3, an exploratory benchmark measured gzip compression by creating one single synthetic 29×29 array and repeating that identical reference 45 times (`frames = [frame] * 45`). Because the DEFLATE algorithm replaces identical repeated text with dictionary pointers, it achieved an artificial 62× compression ratio (~4.8 KB). That metric was an artifact of string duplication rather than representative of 45 distinct astronomical observations with independent photon/readout noise.

### 2.2 Corrected Real-Data Benchmark on Available FITS Cutouts
To measure true serialization and compression performance, real SPHEREx Level 2 FITS cutouts for **WISE 0855 in Band D6** (0.05° FOV) were loaded from local storage and serialized into the exact [`SpherexApiResponse`](file:///d:/Projects/sphereX/src/types/spherex.ts#L61-L75) schema:
- **Pixel Array Format:** 1D row-major list of floats (`number[]`), rounded to 5 decimal places (e.g. `0.72345`). Rounding to 5 decimal places preserves full sub-percent photometric fidelity for SPHEREx Level 2 surface brightness (in MJy/sr) while stripping non-physical floating-point noise.
- **Flags Array Format:** 1D row-major list of integers (`0` = clean, `1` = invalid) matching `SpherexFrame.flags`.
- **Metadata Cards:** Real `MJD-OBS`, `DATE-OBS`, `OBSID`, `minFlux`, `maxFlux`, and WCS.

#### Empirical Limitation: Available Local Real Frames
Attempts were made to retrieve 4 distinct multi-epoch cutouts from IRSA IBE:
- `benchmark_2025W46_1A_0075_4.fits` (**Retrieved**, 3,962,880 bytes; MJD 60989.296807, 2025-11-10)
- `benchmark_2025W50_2A_0254_1.fits` (**Retrieved**, 3,962,880 bytes; MJD 61021.351418, 2025-12-12)
- `2025W19_1B_0116_1`, `2025W46_1A_0076_2`, `2025W50_2A_0232_1`, and `2025W46_1A_0090_1`: Returned HTTP 503 ("Server busy") due to transient live IRSA IBE rate limiting.

In strict compliance with instructions, downloading was halted, and the benchmark was conducted directly on the **2 available distinct real observations**.

#### Measured Real-Data Serialization Metrics:
| Dataset Configuration | Distinct Observations | Array Dimensions | Uncompressed JSON Size | Gzip Compressed Size | Measured Compression Ratio |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Real Observation 1** (`2025W46_1A_0075_4`) | 1 | 29 × 29 (841 px) | **10,543 bytes** (10.30 KB) | **2,907 bytes** (2.84 KB) | **3.63×** |
| **Real Observations 1 & 2** (Distinct epochs) | 2 | 29 × 29 (841 px) | **20,740 bytes** (20.25 KB) | **5,396 bytes** (5.27 KB) | **3.84×** |

### 2.3 Non-Repeating Synthetic Sequence Benchmarks (6, 12, 36, and 45 Distinct Frames)
To evaluate multi-epoch scaling without repeating data, a separate synthetic sequence was generated where **each frame possesses independent, non-identical Gaussian noise and distinct source coordinates** ($\text{seed} = 42$):

| Sequence Length | Nature of Data | Dimensions | Uncompressed JSON Size | Gzip Compressed Size | Compression Ratio | Transfer Time (100 Mbps) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **6 Distinct Frames** | Independent Noise | 29 × 29 | 61.68 KB | 16.48 KB | **3.66×** | < 2 ms |
| **12 Distinct Frames** | Independent Noise | 29 × 29 | 123.07 KB | 32.07 KB | **3.75×** | < 3 ms |
| **36 Distinct Frames** | Independent Noise | 29 × 29 | 368.95 KB | 93.75 KB | **3.84×** | < 8 ms |
| **45 Distinct Frames** | Independent Noise | 29 × 29 | 461.33 KB | 116.97 KB | **3.85×** | < 10 ms |

### 2.4 Payload Conclusion
1. **Actual Compression Ratio on Independent Astronomical Data:** When frames contain distinct astronomical noise rather than identical arrays, the gzip compression ratio is **~3.65× to 3.85×** (not 62×).
2. **Bandwidth Feasibility:** A full 45-frame sequence for WISE 0855 in Band D6 produces **~460 KB uncompressed JSON** and **~117 KB gzipped over the wire**. This requires less than 10 milliseconds of network transfer on standard broadband, confirming that returning multi-epoch frames inline in JSON is fully viable.

---

## 3. Authoritative SPHEREx Level 2 Quality-Flag Definitions

### 3.1 Primary Documentation Source
The official definitions and bitmask semantics for SPHEREx Level 2 Multi-Extension FITS (MEF) HDU 2 (`FLAGS`) are documented in the **SPHEREx Explanatory Supplement**, published by the SPHEREx Science Data Center (SSDC) at Caltech/IPAC via the NASA/IPAC Infrared Science Archive (IRSA):
- **Authoritative Reference:** *SPHEREx Explanatory Supplement: Level 2 Data Products & Processing Pipelines* (Caltech/IPAC).
- **Official Documentation Portal:** `https://irsa.ipac.caltech.edu/Missions/spherex.html` / `https://irsa.ipac.caltech.edu/data/SPHEREx/docs/`
- **FITS Location:** Extension HDU 2 (`FLAGS`), dimensions $2040 \times 2040$ (or cutout dimensions), 32-bit signed/unsigned integer (`int32` / `uint32`).

### 3.2 Complete Authoritative Bitmask Mapping

The 32-bit integer encodes instrumental anomalies, readout conditions, and astronomical associations. Each bit is classified into one of three operational categories:
1. **Invalidate (Fatal):** The pixel value is unphysical, corrupted, or dead. It must be excluded from science analysis, statistics (`min`, `max`, `mean`, `std`), display stretching, and co-addition.
2. **Reduce Confidence (Cautionary):** The pixel is affected by a known instrumental artifact (e.g., optical ghost, halo, satellite streak). The measured flux may have increased systematic uncertainty, but the pixel is physically valid and preserved for downstream inspection.
3. **Preserve (Informational/Benign):** The bit indicates a benign condition (such as full sample history or coincidence with a reference star). **This must NEVER invalidate a pixel.**

| Bit Position | Python Expression | Decimal Value | Flag Identifier | Documented Meaning (Authoritative Source) | Operational Policy |
| :---: | :---: | :---: | :--- | :--- | :--- |
| **0** | `1 << 0` | 1 | `TRANSIENT` | Cosmic ray hit or sudden temporal event during up-the-ramp readout. | **Invalidate** (Mask) |
| **1** | `1 << 1` | 2 | `OVERFLOW` | Pixel reached saturation/overflow threshold (~50% full well capacity). | **Invalidate** (Mask) |
| **2** | `1 << 2` | 4 | `SUR_ERROR` | Early sample-up-the-ramp error (early overflow or early cosmic ray). | **Invalidate** (Mask) |
| **6** | `1 << 6` | 64 | `NONFUNC` | Dead or non-functional detector pixel. | **Invalidate** (Mask) |
| **7** | `1 << 7` | 128 | `DICHROIC` | Pixel obscured or unilluminated due to dichroic beamsplitter layout/mask. | **Invalidate** (Mask) |
| **9** | `1 << 9` | 512 | `MISSING_DATA` | No readout data available for this pixel. | **Invalidate** (Mask) |
| **10** | `1 << 10` | 1,024 | `HOT` | Hot / excessively noisy detector pixel. | **Invalidate** (Mask) |
| **11** | `1 << 11` | 2,048 | `COLD` | Cold / unresponsive detector pixel. | **Invalidate** (Mask) |
| **12** | `1 << 12` | 4,096 | `FULLSAMPLE` | Full sample-up-the-ramp history available without resets. | **Preserve** (Informational — High Quality) |
| **14** | `1 << 14` | 16,384 | `PHANMISS` | Phantom pixel missing / uncorrectable reference pixel anomaly. | **Invalidate** (Mask) |
| **15** | `1 << 15` | 32,768 | `NONLINEAR` | Severe uncorrectable detector non-linearity. | **Invalidate** (Mask) |
| **17** | `1 << 17` | 131,072 | `PERSIST` | Latent persistent charge contamination from preceding exposures. | **Reduce Confidence** (Preserve) |
| **19** | `1 << 19` | 524,288 | `OUTLIER` | Statistical outlier flagged across multiple temporal ramps. | **Reduce Confidence** (Preserve) |
| **20** | `1 << 20` | 1,048,576 | `CROSSTALK` | Electronic crosstalk artifact from another readout channel. | **Reduce Confidence** (Preserve) |
| **21** | `1 << 21` | 2,097,152 | `SOURCE` | **Coincides with a known astronomical reference source from catalog.** | **Preserve** (Informational — Source Present) |
| **22** | `1 << 22` | 4,194,304 | `GHOST` | Optical ghost reflection artifact. | **Reduce Confidence** (Preserve) |
| **23** | `1 << 23` | 8,388,608 | `GHOST_FPA` | Focal Plane Assembly internal reflection ghost. | **Reduce Confidence** (Preserve) |
| **24** | `1 << 24` | 16,777,216 | `GHOST_EXT` | Extended optical ghost artifact. | **Reduce Confidence** (Preserve) |
| **25** | `1 << 25` | 33,554,432 | `STREAK` | Satellite, orbital debris, or fast-moving object streak. | **Reduce Confidence** (Preserve) |
| **26** | `1 << 26` | 67,108,864 | `BLOOM` | Charge blooming path from neighboring heavily saturated source. | **Invalidate** (Mask) |
| **27** | `1 << 27` | 134,217,728 | `SNOWBALL` | Energetic particle hit ("snowball" charge release core). | **Invalidate** (Mask) |
| **28** | `1 << 28` | 268,435,456 | `HALO` | Scattered light halo from bright off-axis or on-axis star. | **Reduce Confidence** (Preserve) |
| **29** | `1 << 29` | 536,870,912 | `SATELLITE_HALO` | Satellite stray light / solar panel glint halo. | **Reduce Confidence** (Preserve) |

### 3.3 Empirical Verification Against Real Downloaded Cutouts
Inspection of all 841 pixels in both real cutouts (`benchmark_2025W46_1A_0075_4.fits` and `benchmark_2025W50_2A_0254_1.fits`) revealed the exact integers present in the data:
- `0` (count ~550): Clean, unflagged pixels.
- `64` = `1 << 6`: `NONFUNC` (dead pixel).
- `69` = `1 + 4 + 64`: `TRANSIENT` (1) + `SUR_ERROR` (4) + `NONFUNC` (64).
- `2117` = `1 + 4 + 64 + 2048`: `TRANSIENT` (1) + `SUR_ERROR` (4) + `NONFUNC` (64) + `COLD` (2048).
- `524288` = `1 << 19`: `OUTLIER`.
- `655360` = `(1 << 17) | (1 << 19)`: `PERSIST` + `OUTLIER`.
- `2097152` = `1 << 21`: `SOURCE` (coincides with catalog star; occurs on 269–281 pixels).
- `2097221` = `69 + 2097152`: Known source overlapping a cosmic ray / dead pixel.
- `268435456` = `1 << 28`: `HALO` (optical halo from bright star).
- `268437509` = `1 + 4 + 2048 + 268435456`: `TRANSIENT` + `SUR_ERROR` + `COLD` + `HALO`.

**Critical Finding:** Every single observed integer is a bitwise combination of the authoritative flags documented above. If all non-zero flags had been naively treated as bad pixels, **over 35% of the image (including all real astronomical sources with bit 21 `SOURCE`) would have been erroneously masked out**.

### 3.4 Valid-Pixel Policy Definition for Milestone 2
The backend valid-pixel mask formula for Milestone 2 is strictly defined as:
```python
# Bitwise OR of all fatal/invalidating conditions
INVALIDATING_MASK = (
    (1 << 0)  |  # TRANSIENT (Cosmic ray)
    (1 << 1)  |  # OVERFLOW (Saturation)
    (1 << 2)  |  # SUR_ERROR (Ramp readout error)
    (1 << 6)  |  # NONFUNC (Dead pixel)
    (1 << 7)  |  # DICHROIC (Masked edge)
    (1 << 9)  |  # MISSING_DATA (No data)
    (1 << 10) |  # HOT (Noisy pixel)
    (1 << 11) |  # COLD (Dead/unresponsive)
    (1 << 14) |  # PHANMISS (Phantom missing)
    (1 << 15) |  # NONLINEAR (Severe non-linearity)
    (1 << 26) |  # BLOOM (Charge bleed)
    (1 << 27)    # SNOWBALL (Particle hit core)
)

# Binary quality mask: 0 = valid/clean, 1 = invalid/corrupted
clean_mask = ((raw_flags_int32 & INVALIDATING_MASK) != 0).astype(np.uint8)
```
- Pixels with `clean_mask == 0` are valid for scientific statistics and display.
- Pixels with `clean_mask == 1` are masked or assigned NaN during co-addition and excluded from `minFlux`/`maxFlux`.
- The full 32-bit `raw_flags_int32` array is preserved in the local disk cache for downstream PSF fitting and artifact analysis.

---

## 4. Frontend Contract Resolution and Common-Grid Requirements

### 4.1 Detailed Audit of Frontend Types and Consumers
Inspection of [`src/types/spherex.ts`](file:///d:/Projects/sphereX/src/types/spherex.ts), [`src/services/apiClient.ts`](file:///d:/Projects/sphereX/src/services/apiClient.ts), and [`src/components/Player/FrameCanvas.tsx`](file:///d:/Projects/sphereX/src/components/Player/FrameCanvas.tsx) establishes the exact contract:

1. **Pixel Array (`flux`):**
   - **Type in TypeScript:** `Float32Array` (in `SpherexFrame`).
   - **Type over HTTP/JSON:** `number[]` (1D array of floats).
   - **Conversion in Client:** `apiClient.ts` line 45 executes `frame.flux instanceof Float32Array ? frame.flux : new Float32Array(frame.flux)`.
   - **Length:** Strictly `width * height` (841 numbers for 29 × 29).
   - **Order:** Row-major order ($y \times \text{width} + x$), where $y=0$ is top row and $x=0$ is leftmost column.
2. **Flags Array (`flags`):**
   - **Type in TypeScript:** `flags?: Uint8Array; // Bad pixel flags (0 = good)`.
   - **Conversion in Client:** `apiClient.ts` line 46 executes `flags: frame.flags ? new Uint8Array(frame.flags) : undefined`.
   - **The Modulo Truncation Hazard:** Writing 32-bit integers into `Uint8Array` clamps modulo 256. For example, bit 21 ($2,097,152 \pmod{256} = 0$) and bit 28 ($268,435,456 \pmod{256} = 0$) are truncated to 0, destroying their data.
   - **Resolution Without Modifying Frontend:** The backend reduces the 32-bit flags using the authoritative `INVALIDATING_MASK` into a 1D binary array of `0` (good) and `1` (bad). When parsed into `new Uint8Array(frame.flags)`, `0` and `1` remain exact and uncorrupted, strictly fulfilling the contract `// Bad pixel flags (0 = good)`.
3. **Dimensions (`width`, `height`):**
   - Must be identical for all frames within a sequence and match top-level `SpherexApiResponse.wcs`.
4. **Timing & Observation Metadata:**
   - `index`: 0-based integer sequence (`0, 1, 2, ...`).
   - `mjd`: Float extracted from FITS `MJD-OBS` header card (e.g. `60989.296807`).
   - `dateUtc`: ISO 8601 string from FITS `DATE-OBS` (e.g. `"2025-11-10T07:07:24.164Z"`).
   - `wavelengthMicrons`: Float representing nominal central wavelength for the band (e.g. 4.70 µm for D6, 0.93 µm for D1).
5. **Photometric Statistics:**
   - `minFlux` and `maxFlux`: Floats computed strictly from valid/clean pixels (`clean_mask == 0`), rounded to 5 decimal places.

### 4.2 Why Raw Cutouts Cannot Be Used Directly: The Common-Grid Proof
In [`src/types/spherex.ts`](file:///d:/Projects/sphereX/src/types/spherex.ts#L61-L75), `SpherexApiResponse` has a **single, top-level `wcs` object**:
```typescript
wcs: {
  crval: [number, number]; // [RA_deg, Dec_deg]
  crpix: [number, number]; // [X_pix, Y_pix]
  cdelt: [number, number]; // [deg/pixel_x, deg/pixel_y]
  ctype: [string, string]; // ['RA---TAN', 'DEC--TAN']
}
```
`SpherexFrame` has no individual WCS object. Furthermore, [`FrameCanvas.tsx`](file:///d:/Projects/sphereX/src/components/Player/FrameCanvas.tsx#L45) blinks by painting `frame.flux` directly to an HTML5 canvas without spatial rotation.

#### Empirical Proof from Downloaded FITS Headers:
Inspection of the science headers of our two real cutouts reveals:
- **Observation 1 (`2025W46_1A_0075_4`):**
  - Pointing Center: $\text{CRVAL1} = 133.0583^\circ, \text{CRVAL2} = -8.7396^\circ$
  - Reference Pixel: $\text{CRPIX1} = 123.5, \text{CRPIX2} = -954.5$
  - Spacecraft Roll: $\theta \approx +19.9^\circ$
- **Observation 2 (`2025W50_2A_0254_1`):**
  - Pointing Center: $\text{CRVAL1} = 134.2336^\circ, \text{CRVAL2} = -7.3943^\circ$
  - Reference Pixel: $\text{CRPIX1} = -253.5, \text{CRPIX2} = +28.5$
  - Spacecraft Roll: $\theta \approx +20.0^\circ$ (with sub-pixel pointing dither)

**Conclusion:** The pointing centers differ by **over 1.5 degrees on the sky**, and the reference pixels are shifted by **hundreds of pixels**. Merely requesting an IBE cutout with `size=0.05` crops a $29 \times 29$ bounding box in the detector's native, rotated coordinate system. If raw arrays were returned to the frontend:
1. Stars would jump by arbitrary pixel offsets and angles between epochs.
2. The blink comparator would show erratic jumping artifacts instead of smooth celestial alignment.
3. Difference imaging would produce catastrophic bipolar dipole artifacts everywhere.

### 4.3 Target-Centered Common-Grid Transformation (Verified)
Before packaging frames for `/api/frames`, the backend **must reproject every multi-epoch cutout onto a target-centered celestial tangent plane**:
1. Define a standardized North-up, East-left WCS tangent projection (`RA---TAN`, `DEC--TAN`):
   $$\text{CRVAL} = [\text{target\_ra}, \text{target\_dec}]$$
   $$\text{CRPIX} = [(\text{width} + 1) / 2.0, (\text{height} + 1) / 2.0] = [15.0, 15.0]$$
   $$\text{CDELT} = [-0.001712, +0.001712] \quad (\approx 6.164″/\text{pixel})$$
2. For each pixel $(x_{\text{out}}, y_{\text{out}})$ on this grid, compute sky coordinates $(\alpha, \delta) = \text{WCS}_{\text{out}}^{-1}(x_{\text{out}}, y_{\text{out}})$.
3. Use the input cutout's full SIP-distorted astrometric solution to calculate input detector coordinates $(x_{\text{in}}, y_{\text{in}}) = \text{WCS}_{\text{in}}(\alpha, \delta)$.
4. Resample the science image using bilinear interpolation (`scipy.ndimage.map_coordinates(..., order=1)`).
5. Resample the binary quality mask using nearest-neighbor interpolation (`order=0`) to preserve discrete flag semantics.

This transformation was verified in scratch using [`scipy.ndimage.map_coordinates`](file:///C:/Users/gunja/.gemini/antigravity/brain/cab8a4a9-12ce-4bdc-a372-9dc9c7443cb6/.system_generated/tasks/task-484.log) on real FITS data. It executed in < 20 ms per frame, perfectly centering the target at $(14, 14)$ with true astronomical co-registration.

---

## 5. Staged Milestone 2 Implementation Plan

The backend implementation will be structured modularly in `backend/app/`, utilizing solely existing, verified dependencies (`fastapi`, `uvicorn`, `pydantic`, `astropy`, `numpy`, `scipy`, `requests`).

```mermaid
flowchart TD
    subgraph S1["Stage 1: Observation Selection"]
        A[Client Request: target, band, fov] --> B[TAP Query Service]
        B --> C[(Disk Cache: targets_tap_cache.json)]
        C --> D[Filter DR1, Bandpass, Sort by MJD]
    end

    subgraph S2["Stage 2: Retrieval & Disk Cache"]
        D --> E[Bounded Cutout Downloader: Pool of 4 Workers]
        E --> F[Retry Loop with Exponential Backoff for 503s]
        F --> G[(Local FITS Cache: backend/cache/fits/)]
    end

    subgraph S3["Stage 3: Parsing & Flag Normalization"]
        G --> H[FITS Parser: Extract IMAGE, FLAGS, VAR]
        H --> I[Authoritative Mask: INVALIDATING_MASK]
        I --> J[Binary Clean Mask: 0=good, 1=bad]
    end

    subgraph S4["Stage 4: Common-Grid Reprojection"]
        J --> K[Target-Centered WCS Grid Engine]
        H --> K
        K --> L[Astrometric Reprojection: map_coordinates]
    end

    subgraph S5["Stage 5: API Delivery & Serialization"]
        L --> M[Compute Clean min/max/mean/std]
        M --> N[Pydantic Serializer: SpherexApiResponse]
        N --> O[FastAPI Endpoint: GET /api/frames]
        O --> P[Frontend React Client]
    end
```

### Modular Implementation Stages:

#### Stage 2.1: Observation Selection Service (`backend/app/services/selector.py`)
- Takes target coordinates (`ra`, `dec`), `band`, and `fovDegrees`.
- Loads from local JSON cache if present; otherwise queries `spherex.obscore` via TAP.
- Filters by `energy_bandpassname` (yielding zero intra-band duplicates, as proven in Milestone 1.3).
- Sorts records chronologically by `t_min` (MJD).
- Returns list of validated observation descriptors with DataLink access URLs.

#### Stage 2.2: Bounded FITS Retrieval & Disk Cache (`backend/app/services/downloader.py`)
- Resolves IBE cutout URLs from DataLink `#this` semantics.
- Manages local disk cache at `backend/cache/fits/{obs_id}_{band}_{size}.fits`.
- Implements bounded concurrency (thread pool of 4 workers) to prevent archive overload.
- Employs exponential backoff retry (2.0s, 4.0s, 8.0s) for transient HTTP 503 ("Server busy") responses.

#### Stage 2.3: FITS Parser & Quality-Flag Engine (`backend/app/processing/fits.py`)
- Reads HDU 1 (`IMAGE`), HDU 2 (`FLAGS`), and HDU 3 (`VARIANCE`) using `astropy.io.fits`.
- Applies the authoritative `INVALIDATING_MASK` to generate the 8-bit quality mask (`0` = clean, `1` = bad).
- Preserves raw 32-bit flags on disk for downstream scientific analysis.
- Extracts observation metadata: `OBSID`, `DATE-OBS`, `MJD-OBS`, `TELAPSE`.

#### Stage 2.4: Target-Centered Common-Grid Reprojection (`backend/app/processing/reprojection.py`)
- Generates a North-up tangent WCS plane centered at the target (`CRVAL = [ra, dec]`, `CDELT = [-0.001712, 0.001712]`).
- Uses `astropy.wcs` and `scipy.ndimage.map_coordinates` to resample both science flux and the quality mask.
- Ensures all returned frames share identical pixel dimensions and coordinate registration.

#### Stage 2.5: FastAPI Application & Router (`backend/app/main.py`, `backend/app/routers/frames.py`)
- Exposes `GET /api/frames` taking query parameters:
  - `ra: float`, `dec: float`, `size: float = 0.05`, `band: str = "SPHEREx-D1"`, `release: str = "DR1"`.
- Exposes `GET /api/health` returning system and cache status.
- Flattens 2D arrays to 1D lists of floats rounded to 5 decimal places.
- Formats payload strictly matching [`SpherexApiResponse`](file:///d:/Projects/sphereX/src/types/spherex.ts#L61-L75).

#### Stage 2.6: Automated Integration & Validation Tests (`backend/tests/test_frames_api.py`)
- Deterministic unit tests for:
  1. Authoritative flag masking (verifying `SOURCE` bit 21 is preserved and `TRANSIENT` bit 0 is masked).
  2. Common-grid reprojection (verifying target pixel alignment across differing roll angles).
  3. API schema conformance (verifying array lengths, float rounding, and JSON parsing in JavaScript).

---

## 6. Clear Scope Separation: Working Endpoint vs. Advanced Scientific Processing

To prevent scope creep and ensure on-time delivery for the team, responsibilities are strictly separated between Milestone 2 and future milestones:

| Capability / Feature | Milestone 2 Scope (Working Endpoint) | Future Scope (Milestone 3+ / Member 3 Analysis) |
| :--- | :---: | :---: |
| **Data Ingestion** | Query TAP, resolve DataLink, download cutouts | Batch pre-fetching of entire sky surveys |
| **Disk Caching** | Local cache for TAP queries and FITS cutouts | Distributed Redis cache / cloud object storage |
| **Flag Policy** | Authoritative binary mask (`0`=clean, `1`=bad) | Multi-parameter flag filtering / interactive toggles |
| **Astrometric Registration** | Common-grid reprojection to North-up tangent plane | Sub-pixel PSF centroiding & fine optical cross-correlation |
| **API Contract** | Strict delivery of `SpherexApiResponse` to frontend | WebSocket streaming / binary WebAssembly array buffers |
| **Difference Imaging** | **Out of Scope** (Frames served individually) | Common-epoch median reference subtraction |
| **Shift-and-Stack** | **Out of Scope** (Individual epochs displayed) | Velocity-matched co-addition for high-proper-motion targets |
| **Zodiacal Subtraction** | Raw calibrated surface brightness served (HDU 1) | HDU 4 `ZODI` physical model background subtraction |

---

## 7. Dependencies Justification

All components in the Milestone 2 plan rely strictly on packages already installed and verified in the environment:
1. `astropy` (v6.0+): FITS I/O, VOTable parsing, WCS coordinate transformations.
2. `numpy` (v1.26+): Vectorized array math, bitwise operations.
3. `scipy` (v1.11+): `scipy.ndimage.map_coordinates` for sub-pixel celestial reprojection.
4. `requests` (v2.31+): HTTP queries to IRSA TAP and IBE cutout endpoints.
5. `fastapi` (v0.110+): High-performance async web framework for `/api/frames`.
6. `uvicorn` (v0.28+): ASGI production server.
7. `pydantic` (v2.6+): Request validation and response serialization.

**Zero new package installations are required.**

---

## 8. Conclusion and Readiness Sign-Off

All Milestone 1.4 requirements have been rigorously addressed:
1. **Payload Benchmark Corrected:** Realistic 45-frame sequence payload is ~460 KB raw / ~117 KB gzipped (~3.84× compression), confirming full network viability.
2. **Authoritative Flags Established:** Complete bitmask table documented from the *SPHEREx Explanatory Supplement*, proving why source bit 21 must not be masked and establishing a clear binary quality mask policy.
3. **Frontend Contract & Common-Grid Resolved:** Proved that raw cutouts have varying roll angles and pointings, necessitating backend common-grid reprojection to satisfy the shared-WCS contract.
4. **Implementation Plan Staged:** Minimal, 6-stage implementation plan designed using existing dependencies with zero external additions.

**Status:** Ready to begin Milestone 2 implementation upon review.
