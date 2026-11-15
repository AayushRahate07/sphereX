// SPHEREx Sky Viewer — Analysis Engine (Member 2 & 3 Client Integration)
// Implements client-side frame stacking, difference imaging, shift-and-stack motion co-addition,
// and background-subtracted aperture photometry matching Member 3's astrophysical standards.

import type { SpherexFrame } from '../types/spherex';

/**
 * Frame Stacking (Co-addition):
 * Averages or medians multiple epochs to boost Signal-to-Noise Ratio (SNR) by ~sqrt(N).
 */
export function stackFrames(
  frames: SpherexFrame[],
  method: 'mean' | 'median' | 'sum' = 'mean'
): Float32Array | null {
  if (!frames || frames.length === 0) return null;
  if (frames.length === 1) return new Float32Array(frames[0].flux);

  const n = frames.length;
  const len = frames[0].flux.length;
  const result = new Float32Array(len);

  if (method === 'sum') {
    for (let k = 0; k < n; k++) {
      const f = frames[k].flux;
      for (let i = 0; i < len; i++) {
        result[i] += f[i];
      }
    }
  } else if (method === 'mean') {
    for (let k = 0; k < n; k++) {
      const f = frames[k].flux;
      for (let i = 0; i < len; i++) {
        result[i] += f[i];
      }
    }
    for (let i = 0; i < len; i++) {
      result[i] /= n;
    }
  } else if (method === 'median') {
    const vals = new Float32Array(n);
    const mid = Math.floor(n / 2);
    for (let i = 0; i < len; i++) {
      for (let k = 0; k < n; k++) {
        vals[k] = frames[k].flux[i];
      }
      vals.sort();
      if (n % 2 === 1) {
        result[i] = vals[mid];
      } else {
        result[i] = (vals[mid - 1] + vals[mid]) / 2;
      }
    }
  }

  return result;
}

/**
 * Difference Imaging:
 * Subtracts reference frame A (Epoch 1) from frame B.
 * Stationary background stars cancel to zero; moving or variable targets stand out.
 */
export function computeDifference(
  frameA: SpherexFrame,
  frameB: SpherexFrame
): Float32Array | null {
  if (!frameA || !frameB || frameA.flux.length !== frameB.flux.length) return null;
  const len = frameA.flux.length;
  const diff = new Float32Array(len);
  for (let i = 0; i < len; i++) {
    diff[i] = frameB.flux[i] - frameA.flux[i];
  }
  return diff;
}

/**
 * Shift-and-Stack (Planet X & High Proper Motion Detection):
 * Shifts each epoch relative to the first epoch by hypothesized proper motion
 * and co-adds the shifted images using sub-pixel bilinear interpolation.
 *
 * SPHEREx nominal plate scale: 6.2 arcsec / pixel.
 * RA increases East (left in tangent projection X), Dec increases North (upwards in Y).
 */
export function shiftAndStack(
  frames: SpherexFrame[],
  pmRaArcsecPerYr: number,
  pmDecArcsecPerYr: number
): Float32Array | null {
  if (!frames || frames.length === 0) return null;
  if (frames.length === 1) return new Float32Array(frames[0].flux);

  const n = frames.length;
  const width = frames[0].width;
  const height = frames[0].height;
  const len = width * height;
  const stacked = new Float32Array(len);
  const counts = new Uint16Array(len);

  const refMjd = frames[0].mjd;
  const PLATE_SCALE = 6.2; // arcsec per pixel

  for (let k = 0; k < n; k++) {
    const frame = frames[k];
    const dtYears = (frame.mjd - refMjd) / 365.25;

    // Shift in pixels:
    // In celestial tangent projection: X = -RA, Y = +Dec
    const dxPix = (-pmRaArcsecPerYr * dtYears) / PLATE_SCALE;
    const dyPix = (pmDecArcsecPerYr * dtYears) / PLATE_SCALE;

    for (let y = 0; y < height; y++) {
      for (let x = 0; x < width; x++) {
        // Find corresponding coordinate in source frame k
        const srcX = x - dxPix;
        const srcY = y - dyPix;

        if (srcX >= 0 && srcX < width - 1 && srcY >= 0 && srcY < height - 1) {
          const x0 = Math.floor(srcX);
          const x1 = x0 + 1;
          const y0 = Math.floor(srcY);
          const y1 = y0 + 1;

          const fx = srcX - x0;
          const fy = srcY - y0;

          const v00 = frame.flux[y0 * width + x0];
          const v10 = frame.flux[y0 * width + x1];
          const v01 = frame.flux[y1 * width + x0];
          const v11 = frame.flux[y1 * width + x1];

          // Bilinear interpolation
          const interpolated =
            (1 - fx) * (1 - fy) * v00 +
            fx * (1 - fy) * v10 +
            (1 - fx) * fy * v01 +
            fx * fy * v11;

          const destIdx = y * width + x;
          stacked[destIdx] += interpolated;
          counts[destIdx] += 1;
        }
      }
    }
  }

  // Normalize by number of overlapping frames
  for (let i = 0; i < len; i++) {
    if (counts[i] > 0) {
      stacked[i] /= counts[i];
    } else {
      stacked[i] = frames[0].flux[i];
    }
  }

  return stacked;
}

export interface PhotometryPoint {
  mjd: number;
  flux: number;
}

export interface SpectrumPoint {
  wavelengthMicrons: number;
  flux: number;
}

/**
 * Aperture Photometry Light Curve:
 * 2.5-pixel radius circular aperture with local background annulus subtraction.
 */
export function computeLightCurve(
  frames: SpherexFrame[],
  pixelX: number,
  pixelY: number
): PhotometryPoint[] | null {
  if (!frames || frames.length === 0) return null;

  const rAp = 2.5;
  const rApSq = rAp * rAp;
  const rAnnIn = 3.5;
  const rAnnInSq = rAnnIn * rAnnIn;
  const rAnnOut = 5.5;
  const rAnnOutSq = rAnnOut * rAnnOut;

  return frames.map((frame) => {
    let apSum = 0;
    let apCount = 0;
    let annSum = 0;
    let annCount = 0;

    const xRound = Math.round(pixelX);
    const yRound = Math.round(pixelY);

    for (let dy = -6; dy <= 6; dy++) {
      const y = yRound + dy;
      if (y < 0 || y >= frame.height) continue;
      for (let dx = -6; dx <= 6; dx++) {
        const x = xRound + dx;
        if (x < 0 || x >= frame.width) continue;

        const distSq = dx * dx + dy * dy;
        const val = frame.flux[y * frame.width + x];

        if (distSq <= rApSq) {
          apSum += val;
          apCount++;
        } else if (distSq >= rAnnInSq && distSq <= rAnnOutSq) {
          annSum += val;
          annCount++;
        }
      }
    }

    const bkgPerPixel = annCount > 0 ? annSum / annCount : 0;
    const netFlux = apSum - bkgPerPixel * apCount;

    return {
      mjd: frame.mjd,
      flux: +netFlux.toFixed(3),
    };
  });
}

/**
 * Multi-wavelength Spectrum Extraction:
 * Extracts net aperture flux across observed wavelengths.
 */
export function computeSpectrum(
  frames: SpherexFrame[],
  pixelX: number,
  pixelY: number
): SpectrumPoint[] | null {
  const lc = computeLightCurve(frames, pixelX, pixelY);
  if (!lc) return null;

  const points: SpectrumPoint[] = frames.map((f, i) => ({
    wavelengthMicrons: f.wavelengthMicrons,
    flux: lc[i].flux,
  }));

  // Sort spectrally by wavelength
  points.sort((a, b) => a.wavelengthMicrons - b.wavelengthMicrons);
  return points;
}
