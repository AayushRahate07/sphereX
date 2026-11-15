// URL Query Parameter State Synchronization
// Keeps view settings in the URL so any view is shareable and embeddable.

import type { SpherexBand, StretchType } from '../types/spherex';

export interface ViewStateParams {
  ra: number;
  dec: number;
  size: number;
  band: SpherexBand;
  speed: number;
  stretch: StretchType;
  invert: boolean;
  min?: number;
  max?: number;
  embed?: boolean;
  maxFrames?: number;
}

export function parseUrlState(): Partial<ViewStateParams> {
  if (typeof window === 'undefined') return {};
  const params = new URLSearchParams(window.location.search);

  const parsed: Partial<ViewStateParams> = {};

  if (params.has('ra')) parsed.ra = parseFloat(params.get('ra')!);
  if (params.has('dec')) parsed.dec = parseFloat(params.get('dec')!);
  if (params.has('size')) parsed.size = parseFloat(params.get('size')!);
  if (params.has('band')) parsed.band = params.get('band') as SpherexBand;
  if (params.has('speed')) {
    const val = parseFloat(params.get('speed')!);
    if (!isNaN(val) && val > 0) {
      parsed.speed = Math.round(val * 100) / 100;
    }
  }
  if (params.has('stretch')) parsed.stretch = params.get('stretch') as StretchType;
  if (params.has('invert')) parsed.invert = params.get('invert') === '1' || params.get('invert') === 'true';
  if (params.has('min')) parsed.min = parseFloat(params.get('min')!);
  if (params.has('max')) parsed.max = parseFloat(params.get('max')!);
  if (params.has('embed')) parsed.embed = params.get('embed') === 'true' || params.get('embed') === '1';
  if (params.has('max_frames')) {
    const val = parseInt(params.get('max_frames')!, 10);
    if (!isNaN(val) && val > 0) parsed.maxFrames = val;
  } else if (params.has('frames')) {
    const val = parseInt(params.get('frames')!, 10);
    if (!isNaN(val) && val > 0) parsed.maxFrames = val;
  }

  return parsed;
}

export function syncUrlState(state: ViewStateParams): void {
  if (typeof window === 'undefined') return;
  const params = new URLSearchParams();

  params.set('ra', state.ra.toFixed(6));
  params.set('dec', state.dec.toFixed(6));
  params.set('size', state.size.toString());
  params.set('band', state.band);
  params.set('speed', (Math.round(state.speed * 100) / 100).toString());
  params.set('stretch', state.stretch);
  params.set('invert', state.invert ? '1' : '0');

  if (state.min !== undefined) {
    const prec = state.max !== undefined && Math.abs(state.max - state.min) < 5 ? 3 : 1;
    params.set('min', state.min.toFixed(prec));
  }
  if (state.max !== undefined) {
    const prec = state.min !== undefined && Math.abs(state.max - state.min) < 5 ? 3 : 1;
    params.set('max', state.max.toFixed(prec));
  }
  if (state.embed) params.set('embed', '1');
  if (state.maxFrames !== undefined) params.set('max_frames', state.maxFrames.toString());

  const newUrl = `${window.location.pathname}?${params.toString()}`;
  window.history.replaceState(null, '', newUrl);
}

export function getShareableUrl(): string {
  return window.location.href;
}
