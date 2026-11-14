# SPHEREx Sky Viewer
**NASA Space Apps Challenge 2026: Planet X and SPHEREx**

An interactive web viewer for multi-epoch, multi-wavelength cutouts from NASA's SPHEREx mission. Users can explore how patches of the infrared sky change over time to detect moving objects (such as Planet Nine and cool brown dwarfs like WISE 0855) and transient/variable stars.

---

## Architecture & Team Division

- **Member 1 (Data, processing, and release)**:
  - IRSA TAP query, cutout downloads with retry, bad pixel masking, reprojection, and caching.
  - Serves data via FastAPI endpoint: `GET /api/frames?ra={ra}&dec={dec}&size={size}&band={band}&release={release}`.
- **Member 2 (Player, controls, and sky map — This Module)**:
  - High-performance HTML5 Canvas multi-epoch blink player.
  - Client-side real-time stretch (Linear, Logarithmic) and Invert controls running directly on raw pixel values.
  - Test target presets (WISE 0855, Barnard's Star, Epsilon Indi B, RW Aurigae, R Draconis).
  - Shareable and embeddable URL state (`?ra=&dec=&size=&band=&speed=&stretch=&invert=`).
  - Seamless toggle between local sample file (fake moving dot) and Member 1's `/api/frames` endpoint.
- **Member 3 (Analysis features and checks)**:
  - Standalone pure functions in `src/analysis/` for stacking, difference view, shift-and-stack, and light curves.

---

## Getting Started

### Prerequisites
- Node.js (v18+)
- npm

### Installation
```bash
npm install
```

### Development Server
```bash
npm run dev
```
Open [http://localhost:5173](http://localhost:5173) in your browser.

### Production Build
```bash
npm run build
```
The compiled static assets in `dist/` can be served directly by Member 1's FastAPI server (`StaticFiles`), Vercel, Netlify, or GitHub Pages.

---

## API Contract (Section 7)

Endpoint: `GET /api/frames`

### Query Parameters:
- `ra`: Target Right Ascension in decimal degrees (e.g. `133.795129`)
- `dec`: Target Declination in decimal degrees (e.g. `-7.245147`)
- `size`: Field of view in decimal degrees (e.g. `0.05`)
- `band`: Detector bandpass (`SPHEREx-D1` through `SPHEREx-D6`)
- `release`: Data release string (`DR1`, `QR3`)

### JSON Response Structure:
```json
{
  "target": { "ra": 133.795129, "dec": -7.245147, "name": "WISE 0855" },
  "fovDegrees": 0.05,
  "band": "SPHEREx-D1",
  "dataRelease": "DR1",
  "wcs": {
    "crval": [133.795129, -7.245147],
    "crpix": [18, 18],
    "cdelt": [-0.00172, 0.00172],
    "ctype": ["RA---TAN", "DEC--TAN"]
  },
  "frameCount": 6,
  "frames": [
    {
      "index": 0,
      "mjd": 60500.0,
      "dateUtc": "2024-07-16",
      "wavelengthMicrons": 1.05,
      "band": "SPHEREx-D1",
      "width": 36,
      "height": 36,
      "flux": [ ... ],
      "flags": [ ... ],
      "minFlux": 4.5,
      "maxFlux": 65.2
    }
  ]
}
```

---

## Required IRSA Acknowledgement

> "This publication makes use of data products from the Spectro-Photometer for the History of the Universe, Epoch of Reionization and Ices Explorer (SPHEREx), which is a joint project of the Jet Propulsion Laboratory and the California Institute of Technology, and is funded by the National Aeronautics and Space Administration."
