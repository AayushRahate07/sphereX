// Sample Fake Moving Dot Dataset for Member 2 development
// Clearly labeled as synthetic data to avoid any confusion with real SPHEREx observations.

import type { SpherexApiResponse, SpherexFrame, SpherexBand } from '../types/spherex';

export function getSampleMovingDotData(
  ra = 133.795129,
  dec = -7.245147,
  band: SpherexBand = 'SPHEREx-D1'
): SpherexApiResponse {
  const width = 36;
  const height = 36;
  const numFrames = 6;
  const frames: SpherexFrame[] = [];

  for (let f = 0; f < numFrames; f++) {
    const flux = new Float32Array(width * height);
    const mjd = 60500.0 + f * 45.0; // 45 days apart
    const dateUtc = new Date((mjd - 40587) * 86400 * 1000).toISOString().split('T')[0];

    // Background level (~5.0 units) with slight uniform noise
    for (let i = 0; i < flux.length; i++) {
      flux[i] = 5.0 + Math.sin(i * 0.7 + f) * 0.4;
    }

    // Fixed reference star at (x=10, y=10)
    addSimpleDot(flux, width, height, 10, 10, 40.0);

    // Moving dot: moves from (x=14, y=14) to (x=24, y=22) over the 6 frames
    const movingX = 14 + (f / (numFrames - 1)) * 10;
    const movingY = 14 + (f / (numFrames - 1)) * 8;
    addSimpleDot(flux, width, height, movingX, movingY, 65.0);

    // Calculate min and max flux
    let min = Infinity;
    let max = -Infinity;
    for (let i = 0; i < flux.length; i++) {
      const v = flux[i];
      if (v < min) min = v;
      if (v > max) max = v;
    }

    frames.push({
      index: f,
      mjd,
      dateUtc,
      wavelengthMicrons: +(1.0 + f * 0.05).toFixed(2),
      band,
      width,
      height,
      flux,
      minFlux: min,
      maxFlux: max,
    });
  }

  return {
    target: {
      ra,
      dec,
      name: 'Sample Fake Moving Dot (Not Real Data)',
    },
    fovDegrees: 0.05,
    band,
    dataRelease: 'MOCK-SAMPLE',
    wcs: {
      crval: [ra, dec],
      crpix: [width / 2, height / 2],
      cdelt: [-0.00172, 0.00172],
      ctype: ['RA---TAN', 'DEC--TAN'],
    },
    frameCount: frames.length,
    frames,
    isSampleData: true,
  };
}

function addSimpleDot(
  flux: Float32Array,
  width: number,
  height: number,
  cx: number,
  cy: number,
  brightness: number
) {
  const ix = Math.round(cx);
  const iy = Math.round(cy);

  for (let dy = -2; dy <= 2; dy++) {
    const y = iy + dy;
    if (y < 0 || y >= height) continue;
    for (let dx = -2; dx <= 2; dx++) {
      const x = ix + dx;
      if (x < 0 || x >= width) continue;
      const distSq = (x - cx) * (x - cx) + (y - cy) * (y - cy);
      const intensity = brightness * Math.exp(-distSq / 1.5);
      flux[y * width + x] += intensity;
    }
  }
}
