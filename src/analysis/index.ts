// SPHEREx Analysis Function Stubs (Member 3 Workspace)
// Member 3 will supply the implementations for these functions at Checkpoints 4 and 5.
// Member 2 provides the input frames and connects their outputs to the display.

import type { SpherexFrame } from '../types/spherex';

/**
 * Member 3 Slot: Stacking
 * Averages or co-adds frames per detector to bring out faint signal.
 */
export function stackFrames(
  _frames: SpherexFrame[],
  method: 'mean' | 'median' | 'sum' = 'mean'
): Float32Array | null {
  // Member 3 will provide this implementation
  console.info(`[Member 3 Hook] stackFrames called with method: ${method}`);
  return null;
}

/**
 * Member 3 Slot: Difference View
 * Subtracts one frame from another (same detector only).
 */
export function computeDifference(
  _frameA: SpherexFrame,
  _frameB: SpherexFrame
): Float32Array | null {
  // Member 3 will provide this implementation
  console.info('[Member 3 Hook] computeDifference called');
  return null;
}

/**
 * Member 3 Slot: Shift-and-Stack
 * Shifts each frame by hypothesized proper motion and stacks them.
 */
export function shiftAndStack(
  _frames: SpherexFrame[],
  pmRaArcsecPerYr: number,
  pmDecArcsecPerYr: number
): Float32Array | null {
  // Member 3 will provide this implementation
  console.info(`[Member 3 Hook] shiftAndStack called with motion: (${pmRaArcsecPerYr}, ${pmDecArcsecPerYr})`);
  return null;
}

export interface PhotometryPoint {
  mjd: number;
  flux: number;
}

/**
 * Member 3 Slot: Light Curve
 * Adds up pixel values inside an aperture for each frame over time.
 */
export function computeLightCurve(
  _frames: SpherexFrame[],
  pixelX: number,
  pixelY: number
): PhotometryPoint[] | null {
  // Member 3 will provide this implementation
  console.info(`[Member 3 Hook] computeLightCurve called at (${pixelX}, ${pixelY})`);
  return null;
}

export interface SpectrumPoint {
  wavelengthMicrons: number;
  flux: number;
}

/**
 * Member 3 Slot: Spectrum
 * Plots flux against wavelength across detectors for a clicked position.
 */
export function computeSpectrum(
  _frames: SpherexFrame[],
  pixelX: number,
  pixelY: number
): SpectrumPoint[] | null {
  // Member 3 will provide this implementation
  console.info(`[Member 3 Hook] computeSpectrum called at (${pixelX}, ${pixelY})`);
  return null;
}
