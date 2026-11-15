// SPHEREx Astronomical Stretch Utilities
// Provides Linear, Logarithmic, and Asinh scaling on calibrated flux values
// with explicit quality flag handling and robust display range determination.

import type { SpherexFrame, StretchType } from '../types/spherex';

export interface StretchParams {
  type: StretchType; // 'linear' | 'log' | 'asinh'
  min: number;
  max: number;
  invert: boolean;
}

/**
 * Normalizes a raw flux value into [0.0, 1.0] using linear, log, or asinh stretch.
 */
export function applyStretch(
  value: number,
  type: StretchType,
  min: number,
  max: number
): number {
  if (max <= min) max = min + 1e-4;
  const clamped = Math.max(min, Math.min(max, value));
  const norm = (clamped - min) / (max - min);

  if (type === 'log') {
    const a = 100.0;
    return Math.log(1.0 + a * norm) / Math.log(1.0 + a);
  }

  if (type === 'asinh') {
    // Astronomical Asinh stretch (Lupton et al. 2004)
    // Soft knee parameter beta ~ 0.1 preserves linear contrast at background and compresses bright peaks
    const beta = 0.1;
    return Math.asinh(norm / beta) / Math.asinh(1.0 / beta);
  }

  return norm; // Linear
}

/**
 * Computes a robust display range [P_min, P_max] across clean, unmasked pixels of a single frame.
 * Strictly ignores unmasked defect spikes, bad pixels (flags !== 0), and non-finite values.
 */
export function computeFrameDisplayRange(
  frame: SpherexFrame,
  pMin: number = 0.01,
  pMax: number = 0.99
): { min: number; max: number } {
  if (!frame || !frame.flux || frame.flux.length === 0) {
    return { min: 0.0, max: 1.0 };
  }

  const cleanValues: number[] = [];
  const hasFlags = frame.flags && frame.flags.length === frame.flux.length;
  for (let i = 0; i < frame.flux.length; i++) {
    if (!hasFlags || frame.flags![i] === 0) {
      const v = frame.flux[i];
      if (Number.isFinite(v)) {
        cleanValues.push(v);
      }
    }
  }

  if (cleanValues.length === 0) {
    return { min: frame.minFlux ?? 0.0, max: frame.maxFlux ?? 1.0 };
  }

  cleanValues.sort((a, b) => a - b);
  const minIdx = Math.max(0, Math.floor(cleanValues.length * pMin));
  const maxIdx = Math.min(cleanValues.length - 1, Math.floor(cleanValues.length * pMax));

  let min = cleanValues[minIdx];
  let max = cleanValues[maxIdx];
  if (max <= min) {
    max = min + 0.1;
  }

  return { min, max };
}

/**
 * Computes a robust sequence-wide display stretch [P1, P99] across clean pixels.
 * Guarantees stable, flicker-free background brightness across observation epochs.
 */
export function computeRobustDisplayRange(frames: SpherexFrame[]): { min: number; max: number } {
  if (!frames || frames.length === 0) return { min: 0.0, max: 1.0 };

  const allCleanValues: number[] = [];
  for (const f of frames) {
    const hasFlags = f.flags && f.flags.length === f.flux.length;
    for (let i = 0; i < f.flux.length; i++) {
      if (!hasFlags || f.flags![i] === 0) {
        const v = f.flux[i];
        if (Number.isFinite(v)) {
          allCleanValues.push(v);
        }
      }
    }
  }

  if (allCleanValues.length === 0) {
    const f0 = frames[0];
    return { min: f0.minFlux, max: f0.maxFlux };
  }

  allCleanValues.sort((a, b) => a - b);
  const p1Idx = Math.floor(allCleanValues.length * 0.01);
  const p99Idx = Math.min(allCleanValues.length - 1, Math.floor(allCleanValues.length * 0.99));

  let min = allCleanValues[p1Idx];
  let max = allCleanValues[p99Idx];
  if (max <= min) {
    max = min + 0.1;
  }

  return { min, max };
}

/**
 * Renders 2D float pixel array into HTML Canvas ImageData with quality flag awareness.
 */
export function renderFluxToCanvas(
  flux: Float32Array,
  width: number,
  height: number,
  targetImageData: ImageData,
  params: StretchParams,
  flags?: Uint8Array
): void {
  const pixels = targetImageData.data;
  const { type, min, max, invert } = params;
  const total = width * height;

  for (let i = 0; i < total; i++) {
    const offset = i * 4;

    // Distinct neutral background for invalid / masked / out-of-bounds pixels
    if (flags && flags[i] === 1) {
      pixels[offset] = 20;     // R
      pixels[offset + 1] = 22; // G
      pixels[offset + 2] = 28; // B (subtle dark slate)
      pixels[offset + 3] = 255;
      continue;
    }

    const val = flux[i];
    let norm = applyStretch(val, type, min, max);

    if (invert) {
      norm = 1.0 - norm;
    }

    const byteVal = Math.min(255, Math.max(0, Math.floor(norm * 255)));

    pixels[offset] = byteVal;     // R
    pixels[offset + 1] = byteVal; // G
    pixels[offset + 2] = byteVal; // B
    pixels[offset + 3] = 255;     // A
  }
}

/**
 * Renders calibrated 3-band infrared science arrays into an HTML Canvas ImageData false-color composite.
 * Channels are stretched individually to reveal faint structure across detector passbands.
 * Quality masks reject contaminated and out-of-bounds pixels with neutral background rendering.
 */
export function renderRgbToCanvas(
  redFlux: Float32Array,
  greenFlux: Float32Array,
  blueFlux: Float32Array,
  width: number,
  height: number,
  targetImageData: ImageData,
  redStretch: StretchParams,
  greenStretch: StretchParams,
  blueStretch: StretchParams,
  redFlags?: Uint8Array,
  greenFlags?: Uint8Array,
  blueFlags?: Uint8Array
): void {
  const pixels = targetImageData.data;
  const total = width * height;

  for (let i = 0; i < total; i++) {
    const offset = i * 4;

    const rVal = redFlux[i];
    const gVal = greenFlux[i];
    const bVal = blueFlux[i];

    const isRedValid = (!redFlags || redFlags[i] === 0) && Number.isFinite(rVal);
    const isGreenValid = (!greenFlags || greenFlags[i] === 0) && Number.isFinite(gVal);
    const isBlueValid = (!blueFlags || blueFlags[i] === 0) && Number.isFinite(bVal);

    // If all channels are flagged as invalid or out-of-bounds, render dark slate
    if (!isRedValid && !isGreenValid && !isBlueValid) {
      pixels[offset] = 20;     // R
      pixels[offset + 1] = 22; // G
      pixels[offset + 2] = 28; // B
      pixels[offset + 3] = 255; // A
      continue;
    }

    let rNorm = isRedValid ? applyStretch(rVal, redStretch.type, redStretch.min, redStretch.max) : 0.0;
    let gNorm = isGreenValid ? applyStretch(gVal, greenStretch.type, greenStretch.min, greenStretch.max) : 0.0;
    let bNorm = isBlueValid ? applyStretch(bVal, blueStretch.type, blueStretch.min, blueStretch.max) : 0.0;

    if (redStretch.invert) rNorm = 1.0 - rNorm;
    if (greenStretch.invert) gNorm = 1.0 - gNorm;
    if (blueStretch.invert) bNorm = 1.0 - bNorm;

    pixels[offset] = Math.min(255, Math.max(0, Math.floor(rNorm * 255)));
    pixels[offset + 1] = Math.min(255, Math.max(0, Math.floor(gNorm * 255)));
    pixels[offset + 2] = Math.min(255, Math.max(0, Math.floor(bNorm * 255)));
    pixels[offset + 3] = 255;
  }
}
