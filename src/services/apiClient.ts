// SPHEREx API Service & Switchable Backend
// Switches from the sample file to Member 1's real API (/api/frames) with a single address setting.

import type { SpherexApiResponse, SpherexBand } from '../types/spherex';
import { getSampleMovingDotData } from './sampleData';

// Configurable API Address. In production or local dev, point this to Member 1's FastAPI server.
export const API_CONFIG = {
  // Member 1 FastAPI server base URL
  baseUrl: 'http://localhost:8000',
  // Path as agreed in Section 7 API contract: /api/frames
  endpoint: '/api/frames',
  // When true, uses the local sample file (fake moving dot) instead of calling Member 1's API
  useSampleFile: true,
};

export async function fetchSpherexSequence(params: {
  ra: number;
  dec: number;
  size?: number; // field of view in degrees
  band?: SpherexBand;
  release?: string;
}): Promise<SpherexApiResponse> {
  const { ra, dec, size = 0.05, band = 'SPHEREx-D1', release = 'DR1' } = params;

  if (API_CONFIG.useSampleFile) {
    // Return the sample fake moving dot dataset directly
    return getSampleMovingDotData(ra, dec, band);
  }

  // Switch to Member 1's real API:
  // Request: RA, Dec, size in degrees, band and data release
  const url = `${API_CONFIG.baseUrl}${API_CONFIG.endpoint}?ra=${ra}&dec=${dec}&size=${size}&band=${band}&release=${release}`;

  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Member 1 API failed (${res.status}): ${res.statusText}`);
  }

  const data = await res.json();

  // Convert raw array buffers if necessary
  const processedFrames = data.frames.map((frame: any) => ({
    ...frame,
    flux: frame.flux instanceof Float32Array ? frame.flux : new Float32Array(frame.flux),
    flags: frame.flags ? (frame.flags instanceof Uint8Array ? frame.flags : new Uint8Array(frame.flags)) : undefined,
  }));

  return {
    ...data,
    frames: processedFrames,
    isSampleData: false,
  };
}
