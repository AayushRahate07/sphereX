// SPHEREx Astronomical Stretch Utilities
// Kept simple: Linear, Logarithmic, and Invert controls running directly on raw pixel values.

import type { StretchType } from '../types/spherex';

export interface StretchParams {
  type: StretchType; // 'linear' | 'log'
  min: number;
  max: number;
  invert: boolean;
}

/**
 * Normalizes a raw flux value into [0.0, 1.0] using linear or log stretch
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

  return norm; // Linear
}

/**
 * Renders 2D float pixel array into HTML Canvas ImageData
 */
export function renderFluxToCanvas(
  flux: Float32Array,
  width: number,
  height: number,
  targetImageData: ImageData,
  params: StretchParams
): void {
  const pixels = targetImageData.data;
  const { type, min, max, invert } = params;
  const total = width * height;

  for (let i = 0; i < total; i++) {
    const val = flux[i];
    let norm = applyStretch(val, type, min, max);

    if (invert) {
      norm = 1.0 - norm;
    }

    const byteVal = Math.min(255, Math.max(0, Math.floor(norm * 255)));
    const offset = i * 4;

    pixels[offset] = byteVal;     // R
    pixels[offset + 1] = byteVal; // G
    pixels[offset + 2] = byteVal; // B
    pixels[offset + 3] = 255;     // A
  }
}
