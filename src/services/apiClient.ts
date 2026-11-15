// SPHEREx API Service & Switchable Backend
// Switches from the sample file to Member 1's real API (/api/frames) with a single address setting.

import type { SpherexApiResponse, SpherexBand, RgbCompositeData } from '../types/spherex';

// Configurable API Address. In production or local dev, point this to Member 1's FastAPI server.
const DEFAULT_BASE_URL =
  typeof import.meta !== 'undefined' && import.meta.env?.VITE_API_BASE_URL
    ? import.meta.env.VITE_API_BASE_URL
    : 'http://127.0.0.1:8000';

export const API_CONFIG = {
  // Member 1 FastAPI server base URL (configured via VITE_API_BASE_URL or settings)
  baseUrl: DEFAULT_BASE_URL,
  // Path as agreed in Section 7 API contract: /api/frames
  endpoint: '/api/frames',
};

export async function fetchSpherexSequence(params: {
  ra: number;
  dec: number;
  size?: number; // field of view in degrees
  band?: SpherexBand;
  release?: string;
  maxFrames?: number;
  timeoutMs?: number;
  signal?: AbortSignal;
}): Promise<SpherexApiResponse> {
  const {
    ra,
    dec,
    size = 0.25,
    band = 'SPHEREx-D6',
    release = 'DR1',
    maxFrames,
    timeoutMs,
    signal,
  } = params;

  // Use 120s timeout budget by default to accommodate large FOV (0.50 deg) IRSA cutouts
  const effectiveTimeoutMs = timeoutMs ?? 120000;

  // Real Level 2 SPHEREx observations are strictly served by Member 1's FastAPI backend.
  // Synthetic / fake astronomy datasets are disabled.

  // Switch to Member 1's real API:
  // Request: RA, Dec, size in degrees, band, release, and optional max_frames
  const queryParams = new URLSearchParams({
    ra: ra.toString(),
    dec: dec.toString(),
    size: size.toString(),
    band,
    release,
  });
  if (maxFrames !== undefined && maxFrames > 0) {
    queryParams.set('max_frames', maxFrames.toString());
  }

  const url = `${API_CONFIG.baseUrl}${API_CONFIG.endpoint}?${queryParams.toString()}`;

  // Manage bounded timeout alongside optional caller-provided abort signal
  const timeoutController = new AbortController();
  const timer = setTimeout(() => {
    timeoutController.abort(new Error(`SPHEREx API request timed out after ${Math.round(effectiveTimeoutMs / 1000)}s.`));
  }, effectiveTimeoutMs);

  let combinedSignal: AbortSignal;
  if (signal) {
    if (signal.aborted) {
      clearTimeout(timer);
      const abortErr = new Error('Aborted');
      abortErr.name = 'AbortError';
      throw abortErr;
    }
    const combined = new AbortController();
    signal.addEventListener('abort', () => combined.abort(signal.reason), { once: true });
    timeoutController.signal.addEventListener('abort', () => combined.abort(timeoutController.signal.reason), { once: true });
    combinedSignal = combined.signal;
  } else {
    combinedSignal = timeoutController.signal;
  }

  try {
    const res = await fetch(url, { signal: combinedSignal });
    clearTimeout(timer);

    if (!res.ok) {
      let errorDetail = res.statusText || 'Unknown Error';
      try {
        const errJson = await res.json();
        if (errJson && errJson.detail) {
          errorDetail = typeof errJson.detail === 'string' ? errJson.detail : JSON.stringify(errJson.detail);
        }
      } catch {
        // Keep default statusText if response is not JSON
      }
      throw new Error(`SPHEREx API error (${res.status}): ${errorDetail}`);
    }

    const data = await res.json();

    if (!data || typeof data !== 'object') {
      throw new Error('Malformed API response: expected JSON object from SPHEREx backend.');
    }

    if (!Array.isArray(data.frames)) {
      throw new Error('Malformed API response: missing "frames" array from SPHEREx backend.');
    }

    if (!data.wcs || typeof data.wcs !== 'object') {
      throw new Error('Malformed API response: missing "wcs" metadata from SPHEREx backend.');
    }

    // Convert raw array buffers to typed arrays matching frontend contract
    const processedFrames = data.frames.map((frame: any, idx: number) => {
      if (!frame || typeof frame !== 'object') {
        throw new Error(`Malformed frame at index ${idx}: expected frame object.`);
      }
      return {
        ...frame,
        flux: frame.flux instanceof Float32Array ? frame.flux : new Float32Array(frame.flux || []),
        flags: frame.flags ? (frame.flags instanceof Uint8Array ? frame.flags : new Uint8Array(frame.flags)) : undefined,
      };
    });

    return {
      ...data,
      frames: processedFrames,
      isSampleData: false,
    };
  } catch (err: any) {
    clearTimeout(timer);
    if (signal?.aborted) {
      const abortErr = new Error('Aborted');
      abortErr.name = 'AbortError';
      throw abortErr;
    }
    if (timeoutController.signal.aborted) {
      throw new Error(
        `SPHEREx API request timed out after ${Math.round(effectiveTimeoutMs / 1000)}s. The server may be busy or downloading archive data.`
      );
    }
    if (err instanceof TypeError && err.message.toLowerCase().includes('fetch')) {
      throw new Error(
        `Cannot connect to SPHEREx backend at ${API_CONFIG.baseUrl}. Ensure the FastAPI server is running on ${API_CONFIG.baseUrl}.`
      );
    }
    throw err;
  }
}

export async function fetchSpherexRgbComposite(params: {
  ra: number;
  dec: number;
  size?: number;
  redBand?: SpherexBand;
  greenBand?: SpherexBand;
  blueBand?: SpherexBand;
  release?: string;
  timeoutMs?: number;
  signal?: AbortSignal;
}): Promise<RgbCompositeData> {
  const {
    ra,
    dec,
    size = 0.25,
    redBand = 'SPHEREx-D6',
    greenBand = 'SPHEREx-D2',
    blueBand = 'SPHEREx-D1',
    release = 'DR1',
    timeoutMs,
    signal,
  } = params;

  // Use 120s timeout budget for large FOV (> 0.25 deg) fresh IRSA cutouts, 60s otherwise
  const effectiveTimeoutMs = timeoutMs ?? (size > 0.25 ? 120000 : 60000);

  const queryParams = new URLSearchParams({
    ra: ra.toString(),
    dec: dec.toString(),
    size: size.toString(),
    red_band: redBand,
    green_band: greenBand,
    blue_band: blueBand,
    release,
  });

  const url = `${API_CONFIG.baseUrl}/api/rgb?${queryParams.toString()}`;

  const timeoutController = new AbortController();
  const timer = setTimeout(() => {
    timeoutController.abort(new Error(`SPHEREx RGB request timed out after ${Math.round(effectiveTimeoutMs / 1000)}s.`));
  }, effectiveTimeoutMs);

  let combinedSignal: AbortSignal;
  if (signal) {
    if (signal.aborted) {
      clearTimeout(timer);
      const abortErr = new Error('Aborted');
      abortErr.name = 'AbortError';
      throw abortErr;
    }
    const combined = new AbortController();
    signal.addEventListener('abort', () => combined.abort(signal.reason), { once: true });
    timeoutController.signal.addEventListener('abort', () => combined.abort(timeoutController.signal.reason), { once: true });
    combinedSignal = combined.signal;
  } else {
    combinedSignal = timeoutController.signal;
  }

  try {
    const res = await fetch(url, { signal: combinedSignal });
    clearTimeout(timer);

    if (!res.ok) {
      let errorDetail = res.statusText || 'Unknown Error';
      try {
        const errJson = await res.json();
        if (errJson && errJson.detail) {
          errorDetail = typeof errJson.detail === 'string' ? errJson.detail : JSON.stringify(errJson.detail);
        }
      } catch {
        // Keep default statusText
      }
      throw new Error(`SPHEREx RGB error (${res.status}): ${errorDetail}`);
    }

    const data = await res.json();

    if (!data || typeof data !== 'object') {
      throw new Error('Malformed API response: expected JSON object from SPHEREx backend.');
    }

    if (!data.channels || typeof data.channels !== 'object') {
      throw new Error('Malformed API response: missing "channels" in RGB response.');
    }

    const channels: any = {};
    for (const key of ['red', 'green', 'blue']) {
      const ch = data.channels[key];
      if (!ch) {
        throw new Error(`Malformed API response: missing "${key}" channel data.`);
      }
      channels[key] = {
        ...ch,
        flux: ch.flux instanceof Float32Array ? ch.flux : new Float32Array(ch.flux || []),
        flags: ch.flags instanceof Uint8Array ? ch.flags : new Uint8Array(ch.flags || []),
      };
    }

    return {
      ...data,
      channels,
      isSampleData: false,
    };
  } catch (err: any) {
    clearTimeout(timer);
    if (signal?.aborted) {
      const abortErr = new Error('Aborted');
      abortErr.name = 'AbortError';
      throw abortErr;
    }
    if (timeoutController.signal.aborted) {
      throw new Error(
        `SPHEREx RGB request timed out after ${Math.round(effectiveTimeoutMs / 1000)}s.`
      );
    }
    if (err instanceof TypeError && err.message.toLowerCase().includes('fetch')) {
      throw new Error(
        `Cannot connect to SPHEREx backend at ${API_CONFIG.baseUrl}. Ensure the FastAPI server is running.`
      );
    }
    throw err;
  }
}
