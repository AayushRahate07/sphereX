# SPHEREx Sky Viewer — WISE 0855 Epoch Coordinates and Cutout Framing Fix

**Date**: 2026-11-14
**Author**: Member 1 (IRSA Data Retrieval & Processing Pipeline)
**Status**: Implemented, Verified, and Tested (All 70 tests passing)

---

## 1. Executive Summary & Objective

This document records the resolution of the coordinate-epoch mismatch for the high-proper-motion brown dwarf **WISE 0855−0714** in the SPHEREx Sky Viewer backend.

### 1.1 The Coordinate-Epoch Error
- The canonical project coordinates for WISE 0855 (`RA = 133.795129°, Dec = -7.245147°`) correspond to the discovery epoch ($\sim 2010.54$, Luhman 2014).
- Over the 14.9-year baseline between 2010.54 and the SPHEREx DR1 observation epochs in 2025, WISE 0855's extreme proper motion ($\mu_\alpha \cos\delta = -8,123.7\text{ mas/yr}$, $\mu_\delta = +673.2\text{ mas/yr}$) moved the brown dwarf **120.7 arcseconds (~2.0 arcminutes) Westward** and **10.1 arcseconds Northward**.
- When retrieving a standard $0.05^\circ$ ($180''$ field of view, $\pm 90''$ half-width) cutout centered at the 2010 discovery coordinates, the brown dwarf was located at pixel coordinates $(x \approx 33.5, y \approx 15.6)$ on a $29 \times 29$ grid—**approximately 30.7 arcseconds (~5 pixels) outside the Western edge of the image**.

### 1.2 Refutation of the Previously Reported 8.23-Arcsecond Shift
- Milestone 2.4B independently validated and refuted the 8.23-arcsecond displacement reported in earlier scratch scripts:
  - The $7 \times 7$ centroid calculation was performed on an empty patch of background zodiacal sky where WISE 0855 was not present.
  - The apparent 1.34-pixel shift was caused by a minor noise fluctuation at corner pixel $(x=17, y=11)$ with flux $0.59\text{ MJy/sr}$ ($+3.8\sigma$ above background) exerting an unweighted lever arm on median-clipped centroiding.
  - The 8.23-arcsecond shift is **explicitly classified as an aperture/noise artifact on empty background sky, not an astronomical detection of WISE 0855**.

### 1.3 True Astrometric Motion Across Observation Epochs
Between May 5, 2025 and December 12, 2025 ($\Delta t = 220.65\text{ days} = 0.6041\text{ Julian years}$):
- **Proper Motion Displacement**: $4.91''$ Westward, $0.41''$ Northward ($4.92''$ total).
- **Annual Parallax Reflex**: $0.75''$ Eastward, $0.32''$ Southward ($0.81''$ total). Because Earth is on the opposite side of its orbit, parallax **opposes** proper motion.
- **Combined True Apparent Displacement**: **$4.16\text{ arcseconds}$ ($0.675\text{ pixels}$ at $6.16''/\text{pixel}$)** Westward along position angle $\theta \approx 271.2^\circ$.

---

## 2. Verified Astrometric Architecture & Parameters

### 2.1 Literature Astrometry (Kirkpatrick et al. 2021; Luhman 2014)
- Reference Epoch: `2010.54`
- Reference Position: `RA = 133.795129°`, `Dec = -7.245147°` (ICRS)
- Proper Motion: $\mu_\alpha \cos\delta = -8,123.7 \pm 1.3\text{ mas/yr}$, $\mu_\delta = +673.2 \pm 1.3\text{ mas/yr}$
- Trigonometric Parallax: $\varpi = 439.0 \pm 2.4\text{ mas}$ ($d = 2.278\text{ pc}$)

### 2.2 Implemented Components

1. **Astrometry Configuration (`backend/app/config.py`)**:
   - Defined `AstrometryConfig` dataclass:
     ```python
     @dataclass
     class AstrometryConfig:
         reference_ra: float
         reference_dec: float
         reference_epoch: float
         pm_ra_cosdec: float
         pm_dec: float
         parallax_mas: float = 0.0
     ```
   - Configured `astrometry` entry for `WISE 0855` in `TARGET_PRESETS`. Other presets preserve `astrometry: None`.

2. **Astrometry Service (`backend/app/services/astrometry.py`)**:
   - `get_target_astrometry(ra, dec, name, tolerance)`: Identifies if coordinates match a configured astrometric preset.
   - `propagate_coordinates_to_epoch(ra, dec, epoch, target_name, include_parallax)`:
     - Normalizes epoch inputs (MJD float, decimal year, or Astropy `Time`).
     - Computes linear proper motion displacement $\Delta\alpha_{\text{PM}}, \Delta\delta_{\text{PM}}$.
     - Computes Earth barycentric orbit vector $\mathbf{r}_{\oplus}(t)$ in AU via Astropy `get_body_barycentric` and projects annual parallax reflex vector onto local celestial unit vectors $(\hat{\mathbf{u}}_{\text{East}}, \hat{\mathbf{u}}_{\text{North}})$.
     - Targets without astrometry return input coordinates unchanged.

3. **Coordinate-Aware Retrieval & Caching (`backend/app/services/retrieval.py`)**:
   - Deterministic cache filenames include rounded center coordinates:
     `spherex_{release}_{obs_id}_{band}_{ra:.4f}_{dec:.4f}_{size:.4f}.fits`
   - `get_cached_fits_path()` verifies that legacy cutouts actually cover requested coordinates inside $[2, \text{NAXIS}-3]$ before accepting them; cutouts missing the target are rejected and re-downloaded.
   - `batch_retrieve_cutouts()` and `retrieve_cutouts_adaptive()` accept `coords_per_obs` mapping each observation to its epoch coordinates.

4. **Observation Selector (`backend/app/services/selector.py`)**:
   - Automatically computes `coords_per_obs` during cache inspection when targets have astrometry, ensuring epoch-spaced selection correctly prioritizes cached cutouts centered on the target.

5. **Frames Endpoint Pipeline (`backend/app/routers/frames.py`)**:
   - Computes propagated epoch coordinates for all candidate observations.
   - Anchors the **fixed common sky grid** (`common_wcs`) to the first observation epoch (`grid_anchor_ra, grid_anchor_dec = coords_per_obs[selected_obs[0].obs_id]`).
   - Reprojects all epochs onto this single, fixed tangent plane grid:
     - In Epoch 1, the target sits exactly at pixel $(14.0, 14.0)$ (center of the $29 \times 29$ grid, matching the UI reticle).
     - In subsequent epochs, the target moves across frames by $\sim 0.67$ pixels ($\sim 4.16''$) Westward.
     - Background stars remain strictly stationary across all frames.
   - Retains canonical requested coordinates in `target.ra, target.dec` for UI display while anchoring `target_nominal` marker to `grid_anchor_ra, grid_anchor_dec`.

---

## 3. Empirical Verification & Evidence

### 3.1 Retrieved FITS Cutouts & Cutout Centers

The three real SPHEREx Level 2 cutouts were downloaded from IRSA IBE centered on the brown dwarf's propagated coordinates at each epoch:

| Observation ID | Observation Date (UTC) | MJD | Propagated Center (RA, Dec) | Object Pixel in Cutout |
|---|---|---|---|---|
| `2025W19_1B_0116_1` | 2025-05-05T16:48:02.459 | 60800.700028 | `133.761337°, -7.242345°` | $(x = 14.35, y = 13.94)$ |
| `2025W46_1A_0076_3` | 2025-11-10T07:14:12.445 | 60989.301533 | `133.760398°, -7.242318°` | $(x = 14.15, y = 14.44)$ |
| `2025W50_2A_0254_1` | 2025-12-12T08:26:02.508 | 61021.351418 | `133.760173°, -7.242320°` | $(x = 14.11, y = 13.77)$ |

**Result**: WISE 0855 is confirmed to be directly in the center of all three $29 \times 29$ cutouts ($[14.1 - 14.4, 13.8 - 14.4]$), safely away from array borders.

### 3.2 Fixed Common WCS Reprojection Across Epochs

When reprojecting onto the common sky grid anchored at Epoch 1 coordinates:
- `wcs.crval = [133.761337, -7.242345]`
- `wcs.crpix = [15.0, 15.0]` (1-based FITS convention $\implies$ 0-based pixel $(14.0, 14.0)$)
- **Epoch 1 (`2025W19_1B_0116_1`)**: Target at $(x = 14.000, y = 14.000)$
- **Epoch 2 (`2025W46_1A_0076_3`)**: Target at $(x = 14.544, y = 14.016)$
- **Epoch 3 (`2025W50_2A_0254_1`)**: Target at $(x = 14.675, y = 14.014)$
- **Apparent Displacement**:
  $$\Delta x = +0.675\text{ px}, \quad \Delta y = +0.014\text{ px} \implies \Delta r = 0.675\text{ px} = 4.159''$$
- **Background Celestial Objects**: Fixed at constant pixel coordinates in all frames.

### 3.3 Test Suite & Frontend Status

- **Backend Test Suite**: **70 passed in 2.05s** (`pytest backend/tests -v`).
  - Includes 7 new focused regression tests in `backend/tests/test_astrometry.py` verifying preset astrometry configuration, coordinate propagation, 15-year baseline displacement, 7.25-month proper motion + parallax displacement, FITS 1-based vs NumPy 0-based index consistency, stationary background preservation, and cache rejection of miscentered legacy cutouts.
- **Frontend Linter**: `npm run lint` $\implies$ 0 errors.
- **Frontend Build**: `npm run build` $\implies$ clean build in 1.05s.
- **Member 2 Isolation**: No modifications to viewer/player UI components (`FrameCanvas.tsx`, etc.).
