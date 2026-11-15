import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import type {
  SpherexApiResponse,
  SpherexBand,
  SpherexFrame,
  RgbCompositeData,
  ViewMode,
} from './types/spherex';
import { DEFAULT_BAND, TEST_TARGETS, SPHEREX_BANDS } from './types/spherex';
import { fetchSpherexSequence, fetchSpherexRgbComposite } from './services/apiClient';
import { parseUrlState, syncUrlState, getShareableUrl } from './utils/urlState';
import { type StretchParams, computeRobustDisplayRange, computeFrameDisplayRange } from './utils/stretch';
import { FrameCanvas } from './components/Player/FrameCanvas';
import { PlayerControls } from './components/Player/PlayerControls';
import { AladinSkyPicker } from './components/Navigation/AladinSkyPicker';
import { HelpModal } from './components/HUD/HelpModal';
import { ScienceDossierModal } from './components/HUD/ScienceDossierModal';
import { Navbar } from './components/Header/Navbar';
import { MissionSidebar } from './components/Sidebar/MissionSidebar';
import { computeDifference, stackFrames, shiftAndStack } from './analysis';
import {
  AlertCircle,
  Loader2,
  Layers,
  Film,
  SplitSquareVertical,
  Move,
  Palette,
  RefreshCw,
  StopCircle,
} from 'lucide-react';

export type { ViewMode };

export const App: React.FC = () => {
  // Parse initial state from URL query parameters
  const initialUrl = parseUrlState();

  const [ra, setRa] = useState<number>(initialUrl.ra ?? TEST_TARGETS[0].ra);
  const [dec, setDec] = useState<number>(initialUrl.dec ?? TEST_TARGETS[0].dec);
  const [fov, setFov] = useState<number>(initialUrl.size ?? 0.25);
  const [band, setBand] = useState<SpherexBand>(initialUrl.band ?? DEFAULT_BAND);
  const [maxFrames] = useState<number | undefined>(initialUrl.maxFrames);
  const [isEmbedMode] = useState<boolean>(initialUrl.embed ?? false);

  // Aladin Sky Picker modal toggle
  const [isAladinOpen, setIsAladinOpen] = useState<boolean>(false);

  // Help & Shortcuts modal toggle
  const [isHelpOpen, setIsHelpOpen] = useState<boolean>(false);

  // Science Dossier & Validation report modal toggle
  const [isScienceOpen, setIsScienceOpen] = useState<boolean>(false);

  // Aperture inspection state (X, Y in pixel coordinates)
  const [selectedAperture, setSelectedAperture] = useState<{ x: number; y: number } | null>(null);

  // View Mode: Blink sequence vs Difference vs Stacked vs Shift-and-Stack
  const [viewMode, setViewMode] = useState<ViewMode>('blink');

  // Proper motion sliders for Shift-and-Stack
  const [pmRa, setPmRa] = useState<number>(0);
  const [pmDec, setPmDec] = useState<number>(0);

  // Playback state
  const [currentFrameIndex, setCurrentFrameIndex] = useState<number>(0);
  const [isPlaying, setIsPlaying] = useState<boolean>(true);
  const [fps, setFps] = useState<number>(initialUrl.speed ?? 0.5);
  const [loopMode, setLoopMode] = useState<'loop' | 'bounce'>('loop');
  const bounceDirectionRef = useRef<1 | -1>(1);

  // Data & loading state
  const [sequenceData, setSequenceData] = useState<SpherexApiResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Loading progress & cancellation state
  const [loadingProgress, setLoadingProgress] = useState<number>(0);
  const [loadingStage, setLoadingStage] = useState<string>('Initializing archive query...');
  const [loadingElapsed, setLoadingElapsed] = useState<number>(0);

  // Request cancellation, race condition prevention, and caching refs
  const activeReqIdRef = useRef<number>(0);
  const abortControllerRef = useRef<AbortController | null>(null);
  const cacheRef = useRef<Map<string, SpherexApiResponse>>(new Map());

  // Stretch & contrast state
  const [stretch, setStretch] = useState<StretchParams>({
    type: initialUrl.stretch ?? 'linear',
    min: initialUrl.min ?? 0.0,
    max: initialUrl.max ?? 1.0,
    invert: initialUrl.invert ?? false,
  });
  // RGB Multi-Band Composite state
  const [rgbRedBand, setRgbRedBand] = useState<SpherexBand>('SPHEREx-D6');
  const [rgbGreenBand, setRgbGreenBand] = useState<SpherexBand>('SPHEREx-D2');
  const [rgbBlueBand, setRgbBlueBand] = useState<SpherexBand>('SPHEREx-D1');
  const [rgbData, setRgbData] = useState<RgbCompositeData | null>(null);
  const [isRgbLoading, setIsRgbLoading] = useState<boolean>(false);
  const [rgbErrorMsg, setRgbErrorMsg] = useState<string | null>(null);
  const activeRgbReqIdRef = useRef<number>(0);
  const rgbAbortControllerRef = useRef<AbortController | null>(null);
  const rgbCacheRef = useRef<Map<string, RgbCompositeData>>(new Map());

  const [redStretch, setRedStretch] = useState<StretchParams>({
    type: 'asinh',
    min: 0.5,
    max: 1.0,
    invert: false,
  });
  const [greenStretch, setGreenStretch] = useState<StretchParams>({
    type: 'asinh',
    min: 0.1,
    max: 0.6,
    invert: false,
  });
  const [blueStretch, setBlueStretch] = useState<StretchParams>({
    type: 'asinh',
    min: 0.1,
    max: 0.6,
    invert: false,
  });

  // Global keyboard shortcuts (M = toggle map, ? = open help)
  useEffect(() => {
    const handleGlobalKeys = (e: KeyboardEvent) => {
      if (['INPUT', 'SELECT', 'TEXTAREA'].includes((e.target as HTMLElement)?.tagName)) {
        return;
      }
      if (e.key === 'm' || e.key === 'M') {
        setIsAladinOpen((prev) => !prev);
      } else if (e.key === '?' || (e.shiftKey && e.key === '/')) {
        setIsHelpOpen((prev) => !prev);
      }
    };
    window.addEventListener('keydown', handleGlobalKeys);
    return () => window.removeEventListener('keydown', handleGlobalKeys);
  }, []);

  // Cancel search handler: aborts in-flight request and preserves current display
  const handleCancelSearch = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort('User cancelled search');
    }
    setIsLoading(false);
    setLoadingProgress(0);
    setLoadingStage('Search paused');
  }, []);

  // Fetch sequence data when target / band / data source changes
  const loadSequence = useCallback(async () => {
    // Check in-memory cache FIRST: zero-latency instantaneous switch without loading flash
    const cacheKey = `${ra.toFixed(6)}_${dec.toFixed(6)}_${fov}_${band}_${maxFrames ?? 'default'}`;
    if (cacheRef.current.has(cacheKey)) {
      const cached = cacheRef.current.get(cacheKey)!;
      setSequenceData(cached);
      setCurrentFrameIndex(0);
      setIsLoading(false);
      return;
    }

    // Abort any prior in-flight request to prevent race conditions
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    activeReqIdRef.current += 1;
    const currentReqId = activeReqIdRef.current;

    setIsLoading(true);
    setErrorMsg(null);
    setLoadingProgress(10);
    setLoadingStage('Connecting to SPHEREx archive...');
    setLoadingElapsed(0);

    // Progressive real-time estimator based on actual SPHEREx archive pipeline steps
    const startTime = Date.now();
    const progressInterval = setInterval(() => {
      const elapsedSec = Math.floor((Date.now() - startTime) / 1000);
      setLoadingElapsed(elapsedSec);

      if (elapsedSec < 12) {
        // Stage 1: TAP Cone Search Query
        const pct = Math.min(35, 10 + Math.round((elapsedSec / 12) * 25));
        setLoadingProgress(pct);
        setLoadingStage('Stage 1/3: Submitting ADQL cone query to NASA IRSA TAP archive...');
      } else if (elapsedSec < 28) {
        // Stage 2: Downloading & Caching Level 2 FITS Cutouts
        const pct = Math.min(75, 35 + Math.round(((elapsedSec - 12) / 16) * 40));
        setLoadingProgress(pct);
        setLoadingStage('Stage 2/3: Fetching Level 2 SPHEREx FITS cutouts & caching locally...');
      } else if (elapsedSec < 38) {
        // Stage 3: Reprojection & Coordinate Alignment
        const pct = Math.min(92, 75 + Math.round(((elapsedSec - 28) / 10) * 17));
        setLoadingProgress(pct);
        setLoadingStage('Stage 3/3: Reprojecting cutouts onto common celestial tangent grid...');
      } else {
        // Finalizing astrometric alignment & transmission
        const pct = Math.min(98, 92 + Math.round(((elapsedSec - 38) / 15) * 6));
        setLoadingProgress(pct);
        setLoadingStage('Finalizing astrometric alignment & packing spectral frames...');
      }
    }, 250);

    try {
      const data = await fetchSpherexSequence({
        ra,
        dec,
        size: fov,
        band,
        maxFrames,
        signal: controller.signal,
      });

      // Ignore stale response if a newer request was already dispatched
      if (currentReqId !== activeReqIdRef.current) {
        return;
      }

      cacheRef.current.set(cacheKey, data);
      setSequenceData(data);
      setCurrentFrameIndex(0);
      setLoadingProgress(100);

      // Auto-set robust sequence display scaling if not explicitly specified in URL
      if (data.frames.length > 0) {
        const robustRange = computeRobustDisplayRange(data.frames);
        setStretch((prev) => ({
          ...prev,
          min: initialUrl.min ?? robustRange.min,
          max: initialUrl.max ?? robustRange.max,
        }));
      }
    } catch (err: any) {
      if (err.name === 'AbortError') {
        return;
      }
      if (currentReqId === activeReqIdRef.current) {
        setErrorMsg(err.message || 'Failed to fetch SPHEREx frames.');
      }
    } finally {
      clearInterval(progressInterval);
      if (currentReqId === activeReqIdRef.current) {
        setIsLoading(false);
      }
    }
  }, [ra, dec, fov, band, maxFrames, initialUrl.min, initialUrl.max]);

  useEffect(() => {
    if (viewMode !== 'rgb') {
      loadSequence();
    }
  }, [viewMode, loadSequence]);

  // Fetch RGB composite data across 3 bands on shared WCS
  const loadRgbComposite = useCallback(async () => {
    if (rgbAbortControllerRef.current) {
      rgbAbortControllerRef.current.abort();
    }
    const controller = new AbortController();
    rgbAbortControllerRef.current = controller;

    activeRgbReqIdRef.current += 1;
    const currentReqId = activeRgbReqIdRef.current;

    setIsRgbLoading(true);
    setRgbErrorMsg(null);

    const cacheKey = `${ra.toFixed(6)}_${dec.toFixed(6)}_${fov}_${rgbRedBand}_${rgbGreenBand}_${rgbBlueBand}`;
    if (rgbCacheRef.current.has(cacheKey)) {
      const cached = rgbCacheRef.current.get(cacheKey)!;
      setRgbData(cached);
      setIsRgbLoading(false);
      return;
    }

    try {
      const data = await fetchSpherexRgbComposite({
        ra,
        dec,
        size: fov,
        redBand: rgbRedBand,
        greenBand: rgbGreenBand,
        blueBand: rgbBlueBand,
        signal: controller.signal,
      });

      if (currentReqId !== activeRgbReqIdRef.current) return;

      rgbCacheRef.current.set(cacheKey, data);
      setRgbData(data);

      // Auto-set robust stretch for each channel
      setRedStretch((prev) => ({
        ...prev,
        min: data.channels.red.p1Flux,
        max: data.channels.red.p99Flux,
      }));
      setGreenStretch((prev) => ({
        ...prev,
        min: data.channels.green.p1Flux,
        max: data.channels.green.p99Flux,
      }));
      setBlueStretch((prev) => ({
        ...prev,
        min: data.channels.blue.p1Flux,
        max: data.channels.blue.p99Flux,
      }));
    } catch (err: any) {
      if (err.name === 'AbortError') return;
      if (currentReqId === activeRgbReqIdRef.current) {
        setRgbData(null);
        setRgbErrorMsg(err.message || 'Failed to fetch RGB composite.');
      }
    } finally {
      if (currentReqId === activeRgbReqIdRef.current) {
        setIsRgbLoading(false);
      }
    }
  }, [ra, dec, fov, rgbRedBand, rgbGreenBand, rgbBlueBand]);

  useEffect(() => {
    if (viewMode === 'rgb') {
      loadRgbComposite();
    }
  }, [viewMode, loadRgbComposite]);

  // Sync settings back to URL
  useEffect(() => {
    syncUrlState({
      ra,
      dec,
      size: fov,
      band,
      speed: fps,
      stretch: stretch.type,
      invert: stretch.invert,
      min: stretch.min,
      max: stretch.max,
      embed: isEmbedMode,
      maxFrames,
    });
  }, [ra, dec, fov, band, fps, stretch, isEmbedMode, maxFrames]);

  // Playback animation loop
  useEffect(() => {
    if (!isPlaying || viewMode !== 'blink' || !sequenceData || sequenceData.frames.length <= 1) {
      return;
    }

    const intervalMs = 1000 / fps;
    let lastTime = performance.now();
    let animId: number;

    const tick = (now: number) => {
      const elapsed = now - lastTime;
      if (elapsed >= intervalMs) {
        lastTime = now - (elapsed % intervalMs);

        setCurrentFrameIndex((prev) => {
          const total = sequenceData.frames.length;
          if (loopMode === 'loop') {
            return (prev + 1) % total;
          } else {
            let next = prev + bounceDirectionRef.current;
            if (next >= total) {
              bounceDirectionRef.current = -1;
              next = Math.max(0, total - 2);
            } else if (next < 0) {
              bounceDirectionRef.current = 1;
              next = Math.min(total - 1, 1);
            }
            return next;
          }
        });
      }
      animId = requestAnimationFrame(tick);
    };

    animId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(animId);
  }, [isPlaying, viewMode, fps, loopMode, sequenceData]);

  // Step controls
  const handleStepForward = useCallback(() => {
    if (!sequenceData) return;
    setIsPlaying(false);
    setCurrentFrameIndex((prev) => (prev + 1) % sequenceData.frames.length);
  }, [sequenceData]);

  const handleStepBackward = useCallback(() => {
    if (!sequenceData) return;
    setIsPlaying(false);
    setCurrentFrameIndex((prev) =>
      prev === 0 ? sequenceData.frames.length - 1 : prev - 1
    );
  }, [sequenceData]);

  const handleRestart = useCallback(() => {
    setCurrentFrameIndex(0);
  }, []);

  const handleAutoMinMax = useCallback(() => {
    if (!sequenceData || sequenceData.frames.length === 0) return;
    const cur = sequenceData.frames[currentFrameIndex];
    // Calculate robust 1st-99th percentile limits over clean valid pixels (rejects cosmic rays and defect spikes)
    const robust = computeFrameDisplayRange(cur, 0.01, 0.99);
    setStretch((prev) => ({
      ...prev,
      min: robust.min,
      max: robust.max,
    }));
  }, [sequenceData, currentFrameIndex]);

  const handleTargetChange = (newRa: number, newDec: number, name?: string) => {
    setRa(newRa);
    setDec(newDec);
    setSelectedAperture(null);
    if (name) {
      const preset = TEST_TARGETS.find((t) => t.name === name);
      if (preset?.defaultFov) {
        setFov(preset.defaultFov);
      }
    }
  };

  const handleShare = () => {
    navigator.clipboard.writeText(getShareableUrl());
  };

  // Determine active frame for canvas display based on viewMode (memoized)
  const activeDisplayFrame = useMemo<SpherexFrame | null>(() => {
    if (!sequenceData || sequenceData.frames.length === 0) return null;
    const baseFrame = sequenceData.frames[currentFrameIndex];

    if (viewMode === 'blink') {
      return baseFrame;
    } else if (viewMode === 'difference') {
      const f0 = sequenceData.frames[0];
      const diffFlux = computeDifference(f0, baseFrame);
      return diffFlux ? { ...baseFrame, flux: diffFlux } : baseFrame;
    } else if (viewMode === 'stacked') {
      const stackedFlux = stackFrames(sequenceData.frames, 'mean');
      return stackedFlux ? { ...baseFrame, flux: stackedFlux } : baseFrame;
    } else if (viewMode === 'shift-stack') {
      const shiftedFlux = shiftAndStack(sequenceData.frames, pmRa, pmDec);
      return shiftedFlux ? { ...baseFrame, flux: shiftedFlux } : baseFrame;
    }
    return baseFrame;
  }, [sequenceData, currentFrameIndex, viewMode, pmRa, pmDec]);

  const analysisSlotNotice = useMemo<string | null>(() => {
    if (!sequenceData || sequenceData.frames.length === 0) return null;
    if (viewMode === 'difference') {
      return `Difference: Frame [Epoch ${currentFrameIndex + 1}] minus [Epoch 1 baseline]. Stationary stars cancel; moving & variable transients appear as dipoles.`;
    } else if (viewMode === 'stacked') {
      const nFrames = sequenceData.frames.length;
      return `Stacking: Co-adding ${nFrames} epochs. Background noise reduced by ~√${nFrames} (~${Math.sqrt(nFrames).toFixed(1)}× SNR boost).`;
    } else if (viewMode === 'shift-stack') {
      return `Shift-and-Stack Active: Proper motion (${pmRa.toFixed(1)}", ${pmDec.toFixed(1)}") / yr applied via sub-pixel bilinear interpolation.`;
    }
    return null;
  }, [sequenceData, currentFrameIndex, viewMode, pmRa, pmDec]);

  return (
    <div className="flex flex-col h-screen max-h-screen overflow-hidden bg-neutral-950 text-neutral-100 font-sans select-none">
      {!isEmbedMode && (
        <Navbar
          onShare={handleShare}
          onOpenHelp={() => setIsHelpOpen(true)}
          onOpenScienceDossier={() => setIsScienceOpen(true)}
          onApiUrlChange={() => {
            cacheRef.current.clear();
            loadSequence();
          }}
        />
      )}

      {/* Main Content Area */}
      <main className="flex-1 min-h-0 flex flex-col p-2 sm:p-3 overflow-hidden">
        {/* Error notification if API fails */}
        {errorMsg && (
          <div className="mb-2 shrink-0 bg-red-500/10 border border-red-500/40 text-red-300 p-2 rounded-lg text-xs flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />
              <span>{errorMsg}</span>
            </div>
            <button
              onClick={() => setErrorMsg(null)}
              className="text-red-400 hover:text-red-200 text-xs px-2 py-0.5 rounded bg-red-950/60"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* 2-Section Cockpit Grid */}
        <div className="flex-1 h-full min-h-0 grid grid-cols-1 lg:grid-cols-12 gap-3 overflow-hidden">
          {/* ================= LEFT SECTION: PRIMARY SKY VIEWER & TIMELINE ================= */}
          <div className="lg:col-span-7 xl:col-span-8 flex flex-col h-full min-h-0 space-y-2 overflow-hidden">
            {/* View Mode Selector Bar (Top of canvas) */}
            <div className="h-9 shrink-0 flex items-center justify-between bg-neutral-900/90 border border-neutral-800 rounded-lg px-2 text-xs">
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setViewMode('blink')}
                  className={`flex items-center gap-1.5 px-3 py-1 rounded-md text-xs transition ${
                    viewMode === 'blink'
                      ? 'bg-cyan-500 text-neutral-950 shadow-sm font-semibold'
                      : 'text-neutral-400 hover:text-neutral-200'
                  }`}
                >
                  <Film className="w-3.5 h-3.5" /> Blink Sequence
                </button>
                <button
                  onClick={() => setViewMode('difference')}
                  className={`flex items-center gap-1.5 px-3 py-1 rounded-md text-xs transition ${
                    viewMode === 'difference'
                      ? 'bg-cyan-500 text-neutral-950 shadow-sm font-semibold'
                      : 'text-neutral-400 hover:text-neutral-200'
                  }`}
                >
                  <SplitSquareVertical className="w-3.5 h-3.5" /> Difference
                </button>
                <button
                  onClick={() => setViewMode('stacked')}
                  className={`flex items-center gap-1.5 px-3 py-1 rounded-md text-xs transition ${
                    viewMode === 'stacked'
                      ? 'bg-cyan-500 text-neutral-950 shadow-sm font-semibold'
                      : 'text-neutral-400 hover:text-neutral-200'
                  }`}
                >
                  <Layers className="w-3.5 h-3.5" /> Stacking
                </button>
                <button
                  onClick={() => setViewMode('shift-stack')}
                  className={`flex items-center gap-1.5 px-3 py-1 rounded-md text-xs transition ${
                    viewMode === 'shift-stack'
                      ? 'bg-cyan-500 text-neutral-950 shadow-sm font-semibold'
                      : 'text-neutral-400 hover:text-neutral-200'
                  }`}
                >
                  <Move className="w-3.5 h-3.5" /> Shift-Stack
                </button>
                <button
                  onClick={() => setViewMode('rgb')}
                  className={`flex items-center gap-1.5 px-3 py-1 rounded-md text-xs transition ${
                    viewMode === 'rgb'
                      ? 'bg-amber-400 text-neutral-950 shadow-sm font-semibold'
                      : 'text-neutral-400 hover:text-neutral-200'
                  }`}
                >
                  <Palette className="w-3.5 h-3.5" /> False-Color RGB
                </button>
              </div>

              <div className="flex items-center gap-2">
                <span className="text-[11px] text-neutral-500 font-mono hidden sm:inline">
                  {viewMode === 'blink'
                    ? 'Epoch animation'
                    : viewMode === 'difference'
                    ? 'Subtraction (f_i - f_0)'
                    : viewMode === 'stacked'
                    ? 'Co-addition (~√N SNR)'
                    : viewMode === 'shift-stack'
                    ? 'Proper motion track'
                    : 'Multi-band infrared false-color composite'}
                </span>
                <button
                  onClick={() => setIsAladinOpen(true)}
                  className="px-2 py-0.5 rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-300 text-[11px] border border-neutral-700 transition cursor-pointer"
                  title="Open All-Sky Interactive Map"
                >
                  All-Sky Map
                </button>
              </div>
            </div>

            {/* False-Color RGB multi-band selectors */}
            {viewMode === 'rgb' && (
              <div className="shrink-0 bg-neutral-900/90 border border-neutral-800 rounded-lg p-2.5 text-xs flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-3">
                  <div className="flex items-center gap-1.5 font-mono">
                    <span className="w-2.5 h-2.5 rounded-full bg-red-500 inline-block" />
                    <span className="text-neutral-400">R:</span>
                    <select
                      value={rgbRedBand}
                      onChange={(e) => setRgbRedBand(e.target.value as SpherexBand)}
                      className="bg-neutral-800 border border-neutral-700 text-neutral-100 rounded px-1.5 py-0.5 text-xs focus:outline-none focus:border-red-500"
                    >
                      {Object.keys(SPHEREX_BANDS).map((b) => (
                        <option key={b} value={b}>
                          {SPHEREX_BANDS[b as SpherexBand].label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="flex items-center gap-1.5 font-mono">
                    <span className="w-2.5 h-2.5 rounded-full bg-green-500 inline-block" />
                    <span className="text-neutral-400">G:</span>
                    <select
                      value={rgbGreenBand}
                      onChange={(e) => setRgbGreenBand(e.target.value as SpherexBand)}
                      className="bg-neutral-800 border border-neutral-700 text-neutral-100 rounded px-1.5 py-0.5 text-xs focus:outline-none focus:border-green-500"
                    >
                      {Object.keys(SPHEREX_BANDS).map((b) => (
                        <option key={b} value={b}>
                          {SPHEREX_BANDS[b as SpherexBand].label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="flex items-center gap-1.5 font-mono">
                    <span className="w-2.5 h-2.5 rounded-full bg-blue-500 inline-block" />
                    <span className="text-neutral-400">B:</span>
                    <select
                      value={rgbBlueBand}
                      onChange={(e) => setRgbBlueBand(e.target.value as SpherexBand)}
                      className="bg-neutral-800 border border-neutral-700 text-neutral-100 rounded px-1.5 py-0.5 text-xs focus:outline-none focus:border-blue-500"
                    >
                      {Object.keys(SPHEREX_BANDS).map((b) => (
                        <option key={b} value={b}>
                          {SPHEREX_BANDS[b as SpherexBand].label}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
                <button
                  onClick={loadRgbComposite}
                  disabled={isRgbLoading}
                  className="flex items-center gap-1 px-2.5 py-1 bg-amber-500/20 text-amber-300 border border-amber-500/40 rounded hover:bg-amber-500/30 text-xs font-medium transition cursor-pointer"
                >
                  <RefreshCw className={`w-3 h-3 ${isRgbLoading ? 'animate-spin' : ''}`} />
                  {isRgbLoading ? 'Synthesizing...' : 'Re-synthesize RGB'}
                </button>
              </div>
            )}

            {/* Analysis Notice (if active) */}
            {analysisSlotNotice && viewMode !== 'rgb' && (
              <div className="shrink-0 py-1 px-2.5 bg-cyan-950/40 border border-cyan-500/30 text-cyan-300 text-[11px] rounded-lg font-mono">
                ℹ {analysisSlotNotice}
              </div>
            )}

            {/* RGB Error message */}
            {viewMode === 'rgb' && rgbErrorMsg && (
              <div className="shrink-0 py-1 px-2.5 bg-rose-950/40 border border-rose-500/30 text-rose-300 text-[11px] rounded-lg font-mono">
                ⚠ {rgbErrorMsg}
              </div>
            )}

            {/* 2D Canvas Viewport (Fills available vertical space) */}
            <div className="flex-1 min-h-0 relative flex flex-col rounded-xl overflow-hidden border border-neutral-800 bg-neutral-950 shadow-inner">
              {viewMode === 'rgb' ? (
                isRgbLoading && !rgbData ? (
                  <div className="flex-1 flex flex-col items-center justify-center p-6 text-center gap-3">
                    <Loader2 className="w-6 h-6 text-amber-400 animate-spin" />
                    <span className="text-xs text-neutral-300 font-mono">
                      Retrieving 3 detector bands & synthesizing RGB composite...
                    </span>
                  </div>
                ) : rgbData ? (
                  <FrameCanvas
                    stretch={stretch}
                    rgbData={rgbData}
                    redStretch={redStretch}
                    greenStretch={greenStretch}
                    blueStretch={blueStretch}
                    aperture={selectedAperture}
                    onSelectAperture={(px, py) => setSelectedAperture({ x: px, y: py })}
                  />
                ) : (
                  <div className="flex-1 flex flex-col items-center justify-center text-xs text-neutral-400 gap-1.5">
                    <span className="font-medium text-neutral-200">No RGB composite data.</span>
                    <span className="text-neutral-500">{rgbErrorMsg || 'Click Re-synthesize RGB to fetch 3 bands.'}</span>
                  </div>
                )
              ) : isLoading && !sequenceData ? (
                <div className="flex-1 flex flex-col items-center justify-center p-6 text-center">
                  <div className="w-full max-w-sm bg-neutral-900/90 border border-neutral-800 rounded-xl p-5 shadow-2xl space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Loader2 className="w-5 h-5 text-cyan-400 animate-spin" />
                        <span className="text-xs font-semibold text-neutral-100">Fetching SPHEREx Data</span>
                      </div>
                      <span className="text-sm font-bold font-mono text-cyan-400">{loadingProgress}%</span>
                    </div>

                    <div className="w-full bg-neutral-950 rounded-full h-2 overflow-hidden">
                      <div
                        className="bg-cyan-400 h-full rounded-full transition-all duration-300"
                        style={{ width: `${Math.max(5, loadingProgress)}%` }}
                      />
                    </div>
                    <div className="text-[11px] text-neutral-400 font-mono truncate">
                      {loadingStage} {loadingElapsed > 0 ? `(${loadingElapsed}s)` : ''}
                    </div>

                    <button
                      type="button"
                      onClick={handleCancelSearch}
                      className="w-full py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-white font-medium text-xs transition flex items-center justify-center gap-1.5 cursor-pointer"
                    >
                      <StopCircle className="w-3.5 h-3.5" /> Stop Search
                    </button>
                  </div>
                </div>
              ) : activeDisplayFrame ? (
                <div className="relative flex-1 h-full min-h-0 flex flex-col">
                  <FrameCanvas
                    frame={activeDisplayFrame}
                    stretch={stretch}
                    isSampleData={sequenceData?.isSampleData}
                    aperture={selectedAperture}
                    onSelectAperture={(px, py) => setSelectedAperture({ x: px, y: py })}
                  />

                  {/* Non-destructive background fetching overlay */}
                  {isLoading && (
                    <div className="absolute inset-0 bg-neutral-950/60 backdrop-blur-[2px] flex items-center justify-center z-30">
                      <div className="bg-neutral-900/95 border border-neutral-800 rounded-xl p-4 shadow-xl max-w-xs w-full mx-4 space-y-2">
                        <div className="flex items-center justify-between text-xs">
                          <span className="flex items-center gap-2 text-cyan-300 font-medium">
                            <Loader2 className="w-3.5 h-3.5 animate-spin" /> Switching target...
                          </span>
                          <span className="font-mono text-cyan-400 font-bold">{loadingProgress}%</span>
                        </div>
                        <div className="w-full bg-neutral-950 rounded-full h-1.5 overflow-hidden">
                          <div
                            className="bg-cyan-400 h-full rounded-full transition-all duration-200"
                            style={{ width: `${Math.max(5, loadingProgress)}%` }}
                          />
                        </div>
                        <div className="flex justify-end pt-1">
                          <button
                            type="button"
                            onClick={handleCancelSearch}
                            className="text-[11px] text-rose-400 hover:text-rose-300 transition cursor-pointer"
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="flex-1 flex flex-col items-center justify-center text-xs text-neutral-400 gap-1.5">
                  <span className="font-medium text-neutral-200">No frames loaded.</span>
                  <span className="text-neutral-500">Pick an object from the sidebar on the right to start exploring.</span>
                </div>
              )}
            </div>

            {/* Timeline Scrubber & Playback Controls Bar */}
            {sequenceData && viewMode !== 'stacked' && viewMode !== 'shift-stack' && viewMode !== 'rgb' && (
              <div className="shrink-0">
                <PlayerControls
                  currentFrame={currentFrameIndex}
                  totalFrames={sequenceData.frameCount}
                  isPlaying={isPlaying && viewMode === 'blink'}
                  fps={fps}
                  loopMode={loopMode}
                  onPlayToggle={() => setIsPlaying((p) => !p)}
                  onStepForward={handleStepForward}
                  onStepBackward={handleStepBackward}
                  onSeek={(idx) => {
                    setIsPlaying(false);
                    setCurrentFrameIndex(idx);
                  }}
                  onFpsChange={setFps}
                  onLoopModeToggle={() => setLoopMode((m) => (m === 'loop' ? 'bounce' : 'loop'))}
                  onRestart={handleRestart}
                  frames={sequenceData.frames}
                />
              </div>
            )}
          </div>

          {/* ================= RIGHT SECTION: MISSION SIDEBAR ================= */}
          <div className="lg:col-span-5 xl:col-span-4 h-full min-h-0 flex flex-col overflow-hidden">
            <MissionSidebar
              ra={ra}
              dec={dec}
              fovDegrees={fov}
              band={band}
              onTargetChange={handleTargetChange}
              onFovChange={setFov}
              onBandChange={setBand}
              isLoading={isLoading}
              onCancelSearch={handleCancelSearch}
              stretch={stretch}
              onStretchChange={(updated) => setStretch((prev) => ({ ...prev, ...updated }))}
              onAutoMinMax={handleAutoMinMax}
              minPossible={activeDisplayFrame?.minFlux ?? 0}
              maxPossible={activeDisplayFrame?.maxFlux ?? 100}
              pmRa={pmRa}
              pmDec={pmDec}
              onChangePm={(nRa, nDec) => {
                setPmRa(nRa);
                setPmDec(nDec);
              }}
              onResetPm={() => {
                setPmRa(0);
                setPmDec(0);
              }}
              sequenceData={sequenceData}
              activeDisplayFrame={activeDisplayFrame}
              onOpenInfrared101={() => setIsScienceOpen(true)}
              selectedAperture={selectedAperture}
              onSelectAperture={(px, py) => setSelectedAperture({ x: px, y: py })}
              onClearAperture={() => setSelectedAperture(null)}
            />
          </div>
        </div>
      </main>

      {/* Guide & Keyboard Shortcuts Modal */}
      <HelpModal isOpen={isHelpOpen} onClose={() => setIsHelpOpen(false)} />

      {/* Science Dossier & Validation Report Modal */}
      <ScienceDossierModal
        isOpen={isScienceOpen}
        onClose={() => setIsScienceOpen(false)}
        onSelectTarget={(nRa, nDec, name) => handleTargetChange(nRa, nDec, name)}
      />

      {/* Aladin Lite All-Sky Modal Overlay */}
      {isAladinOpen && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-neutral-900 border border-neutral-800 rounded-2xl w-full max-w-4xl h-[80vh] flex flex-col overflow-hidden shadow-2xl">
            <div className="px-4 py-3 flex items-center justify-between border-b border-neutral-800 bg-neutral-950">
              <span className="font-semibold text-sm text-neutral-100 flex items-center gap-2">
                All-Sky Celestial Map (CDS Aladin Lite)
              </span>
              <button
                onClick={() => setIsAladinOpen(false)}
                className="text-neutral-400 hover:text-neutral-100 text-xs px-2.5 py-1 rounded bg-neutral-800"
              >
                Close Map
              </button>
            </div>
            <div className="flex-1 min-h-0 relative">
              <AladinSkyPicker
                ra={ra}
                dec={dec}
                fovDegrees={fov}
                isOpen={isAladinOpen}
                onClose={() => setIsAladinOpen(false)}
                onSelectPosition={(newRa, newDec) => {
                  setRa(+newRa.toFixed(6));
                  setDec(+newDec.toFixed(6));
                  setSelectedAperture(null);
                  setIsAladinOpen(false);
                }}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default App;
