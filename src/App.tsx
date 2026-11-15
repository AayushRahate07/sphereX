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
import { StretchControls } from './components/Controls/StretchControls';
import { ShiftStackControls } from './components/Controls/ShiftStackControls';
import { TargetBar } from './components/Navigation/TargetBar';
import { AladinSkyPicker } from './components/Navigation/AladinSkyPicker';
import { MetadataPanel } from './components/HUD/MetadataPanel';
import { PhotometryDrawer } from './components/HUD/PhotometryDrawer';
import { HelpModal } from './components/HUD/HelpModal';
import { Navbar } from './components/Header/Navbar';
import { Footer } from './components/Footer/Footer';
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

  // Aladin Sky Picker drawer toggle
  const [isAladinOpen, setIsAladinOpen] = useState<boolean>(false);

  // Help & Shortcuts modal toggle
  const [isHelpOpen, setIsHelpOpen] = useState<boolean>(false);

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
  const [stretchScope, setStretchScope] = useState<'sequence' | 'frame'>('sequence');

  // RGB Multi-Band Composite state
  const [rgbRedBand, setRgbRedBand] = useState<SpherexBand>('SPHEREx-D6');
  const [rgbGreenBand, setRgbGreenBand] = useState<SpherexBand>('SPHEREx-D2');
  const [rgbBlueBand, setRgbBlueBand] = useState<SpherexBand>('SPHEREx-D1');
  const [rgbData, setRgbData] = useState<RgbCompositeData | null>(null);
  const [isRgbLoading, setIsRgbLoading] = useState<boolean>(false);
  const [rgbErrorMsg, setRgbErrorMsg] = useState<string | null>(null);
  const [rgbStretchChannel, setRgbStretchChannel] = useState<'all' | 'red' | 'green' | 'blue'>('all');
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

  // Fetch sequence data when target / band / data source changes
  const loadSequence = useCallback(async () => {
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

    // Check in-memory cache to prevent redundant fetches
    const cacheKey = `${ra.toFixed(6)}_${dec.toFixed(6)}_${fov}_${band}_${maxFrames ?? 'default'}`;
    if (cacheRef.current.has(cacheKey)) {
      const cached = cacheRef.current.get(cacheKey)!;
      setSequenceData(cached);
      setCurrentFrameIndex(0);
      setIsLoading(false);
      return;
    }

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
      // Aborted requests are superseded intentionally; do not show error
      if (err.name === 'AbortError') {
        return;
      }
      if (currentReqId === activeReqIdRef.current) {
        setSequenceData(null);
        setErrorMsg(err.message || 'Failed to fetch SPHEREx frames.');
      }
    } finally {
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
            // Bounce
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

  // Determine active frame for canvas display based on viewMode
  let activeDisplayFrame: SpherexFrame | null = null;
  let analysisSlotNotice: string | null = null;

  if (sequenceData && sequenceData.frames.length > 0) {
    const baseFrame = sequenceData.frames[currentFrameIndex];

    if (viewMode === 'blink') {
      activeDisplayFrame = baseFrame;
    } else if (viewMode === 'difference') {
      const f0 = sequenceData.frames[0];
      const diffFlux = computeDifference(f0, baseFrame);

      if (diffFlux) {
        activeDisplayFrame = {
          ...baseFrame,
          flux: diffFlux,
        };
      } else {
        // Fallback display while Member 3 works on analysis
        activeDisplayFrame = baseFrame;
        analysisSlotNotice =
          'Difference View Hook ready for Member 3 function (Checkpoint 5). Showing reference frame.';
      }
    } else if (viewMode === 'stacked') {
      const stackedFlux = stackFrames(sequenceData.frames, 'mean');

      if (stackedFlux) {
        activeDisplayFrame = {
          ...baseFrame,
          flux: stackedFlux,
        };
      } else {
        // Fallback display while Member 3 works on analysis
        activeDisplayFrame = baseFrame;
        analysisSlotNotice =
          'Stacking View Hook ready for Member 3 function (Checkpoint 5). Showing reference frame.';
      }
    } else if (viewMode === 'shift-stack') {
      const shiftedFlux = shiftAndStack(sequenceData.frames, pmRa, pmDec);

      if (shiftedFlux) {
        activeDisplayFrame = {
          ...baseFrame,
          flux: shiftedFlux,
        };
      } else {
        // Fallback display while Member 3 works on analysis
        activeDisplayFrame = baseFrame;
        analysisSlotNotice = `Shift-and-Stack Hook ready for Member 3 function (Checkpoint 5). Passing proper motion: (${pmRa.toFixed(1)}", ${pmDec.toFixed(1)}") / yr.`;
      }
    }
  }

  // When scope is per-frame, calculate frame-level robust display range dynamically
  const effectiveStretch = useMemo(() => {
    if (stretchScope === 'frame' && activeDisplayFrame) {
      const frameRange = computeFrameDisplayRange(activeDisplayFrame, 0.01, 0.99);
      return {
        ...stretch,
        min: frameRange.min,
        max: frameRange.max,
      };
    }
    return stretch;
  }, [stretchScope, stretch, activeDisplayFrame]);

  return (
    <div className="min-h-screen flex flex-col bg-neutral-950 text-neutral-100 font-sans">
      {!isEmbedMode && (
        <Navbar
          onShare={handleShare}
          onOpenHelp={() => setIsHelpOpen(true)}
          onApiUrlChange={() => {
            cacheRef.current.clear();
            loadSequence();
          }}
        />
      )}

      <main className="flex-1 max-w-7xl w-full mx-auto p-4 space-y-4">
        {/* Error notification if Member 1 API fails */}
        {errorMsg && (
          <div className="bg-red-500/10 border border-red-500/40 text-red-300 p-3 rounded-lg text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}

        {/* Target and Detector Navigation (Section 4) */}
        {!isEmbedMode && (
          <TargetBar
            ra={ra}
            dec={dec}
            fovDegrees={fov}
            band={band}
            onTargetChange={handleTargetChange}
            onFovChange={setFov}
            onBandChange={setBand}
            isAladinOpen={isAladinOpen}
            onToggleAladin={() => setIsAladinOpen((prev) => !prev)}
            isLoading={isLoading}
          />
        )}

        {/* Aladin Lite All-Sky Picker Drawer */}
        {!isEmbedMode && (
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
            }}
          />
        )}

        {/* View Mode Selector Tabs (Blink Player / Difference View / Stacked / Shift-and-Stack) */}
        <div className="flex items-center justify-between bg-neutral-900 border border-neutral-800 rounded-lg p-2 text-xs">
          <div className="flex flex-wrap items-center gap-1.5">
            <button
              onClick={() => setViewMode('blink')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md font-medium transition ${
                viewMode === 'blink'
                  ? 'bg-cyan-500 text-neutral-950 shadow-sm'
                  : 'text-neutral-400 hover:text-neutral-200'
              }`}
            >
              <Film className="w-3.5 h-3.5" /> Blink Sequence
            </button>
            <button
              onClick={() => setViewMode('difference')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md font-medium transition ${
                viewMode === 'difference'
                  ? 'bg-cyan-500 text-neutral-950 shadow-sm'
                  : 'text-neutral-400 hover:text-neutral-200'
              }`}
            >
              <SplitSquareVertical className="w-3.5 h-3.5" /> Difference View
            </button>
            <button
              onClick={() => setViewMode('stacked')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md font-medium transition ${
                viewMode === 'stacked'
                  ? 'bg-cyan-500 text-neutral-950 shadow-sm'
                  : 'text-neutral-400 hover:text-neutral-200'
              }`}
            >
              <Layers className="w-3.5 h-3.5" /> Stacking View
            </button>
            <button
              onClick={() => setViewMode('shift-stack')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md font-medium transition ${
                viewMode === 'shift-stack'
                  ? 'bg-cyan-500 text-neutral-950 shadow-sm'
                  : 'text-neutral-400 hover:text-neutral-200'
              }`}
            >
              <Move className="w-3.5 h-3.5" /> Shift-and-Stack
            </button>
            <button
              onClick={() => setViewMode('rgb')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md font-medium transition ${
                viewMode === 'rgb'
                  ? 'bg-amber-400 text-neutral-950 shadow-sm font-semibold'
                  : 'text-neutral-400 hover:text-neutral-200'
              }`}
            >
              <Palette className="w-3.5 h-3.5" /> False-Color RGB
            </button>
          </div>

          <span className="text-[11px] text-neutral-500 hidden sm:inline font-mono">
            {viewMode === 'blink'
              ? 'Multi-epoch blink sequence'
              : viewMode === 'difference'
              ? 'Frame subtraction (Member 3 hook)'
              : viewMode === 'stacked'
              ? 'Co-added stack (Member 3 hook)'
              : viewMode === 'shift-stack'
              ? 'Proper motion co-addition (Idea 1)'
              : 'Multi-band infrared false-color composite'}
          </span>
        </div>

        {/* Shift-and-Stack Proper Motion Controls (Active only in Shift-Stack mode) */}
        {viewMode === 'shift-stack' && (
          <ShiftStackControls
            pmRa={pmRa}
            pmDec={pmDec}
            onChangePm={(newRa, newDec) => {
              setPmRa(newRa);
              setPmDec(newDec);
            }}
            onReset={() => {
              setPmRa(0);
              setPmDec(0);
            }}
          />
        )}

        {/* False-Color RGB Multi-Band Channel Controls */}
        {viewMode === 'rgb' && (
          <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-3 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-3 text-xs">
              <div className="flex flex-wrap items-center gap-4">
                {/* Red Channel Band Selector */}
                <div className="flex items-center gap-1.5 font-mono">
                  <span className="w-2.5 h-2.5 rounded-full bg-red-500 inline-block" />
                  <span className="text-neutral-400">Red:</span>
                  <select
                    value={rgbRedBand}
                    onChange={(e) => setRgbRedBand(e.target.value as SpherexBand)}
                    className="bg-neutral-800 border border-neutral-700 text-neutral-100 rounded px-2 py-1 text-xs focus:outline-none focus:border-red-500"
                  >
                    {Object.keys(SPHEREX_BANDS).map((b) => (
                      <option key={b} value={b}>
                        {SPHEREX_BANDS[b as SpherexBand].label}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Green Channel Band Selector */}
                <div className="flex items-center gap-1.5 font-mono">
                  <span className="w-2.5 h-2.5 rounded-full bg-green-500 inline-block" />
                  <span className="text-neutral-400">Green:</span>
                  <select
                    value={rgbGreenBand}
                    onChange={(e) => setRgbGreenBand(e.target.value as SpherexBand)}
                    className="bg-neutral-800 border border-neutral-700 text-neutral-100 rounded px-2 py-1 text-xs focus:outline-none focus:border-green-500"
                  >
                    {Object.keys(SPHEREX_BANDS).map((b) => (
                      <option key={b} value={b}>
                        {SPHEREX_BANDS[b as SpherexBand].label}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Blue Channel Band Selector */}
                <div className="flex items-center gap-1.5 font-mono">
                  <span className="w-2.5 h-2.5 rounded-full bg-blue-500 inline-block" />
                  <span className="text-neutral-400">Blue:</span>
                  <select
                    value={rgbBlueBand}
                    onChange={(e) => setRgbBlueBand(e.target.value as SpherexBand)}
                    className="bg-neutral-800 border border-neutral-700 text-neutral-100 rounded px-2 py-1 text-xs focus:outline-none focus:border-blue-500"
                  >
                    {Object.keys(SPHEREX_BANDS).map((b) => (
                      <option key={b} value={b}>
                        {SPHEREX_BANDS[b as SpherexBand].label}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Reset Chromatic Defaults */}
                <button
                  onClick={() => {
                    setRgbRedBand('SPHEREx-D6');
                    setRgbGreenBand('SPHEREx-D2');
                    setRgbBlueBand('SPHEREx-D1');
                  }}
                  className="flex items-center gap-1 px-2.5 py-1 bg-neutral-800 hover:bg-neutral-700 text-neutral-300 rounded text-xs transition border border-neutral-700 font-sans"
                  title="Reset to chromatic infrared ordering: Red = D6 (4.7 µm), Green = D2 (1.4 µm), Blue = D1 (0.9 µm)"
                >
                  <RefreshCw className="w-3 h-3 text-cyan-400" />
                  Chromatic Default (D6/D2/D1)
                </button>
              </div>
            </div>

            {/* Scientific notice badge */}
            <div className="text-[11px] text-neutral-400 bg-neutral-950/60 border border-neutral-800/80 rounded p-2 font-mono flex items-start gap-2">
              <span className="text-amber-400 font-semibold shrink-0">ASTROPHYSICAL NOTICE:</span>
              <span>
                {rgbData?.scientificNotice ||
                  'False-color infrared composite: Longer wavelengths (D6, 4.7 µm) map to Red, intermediate wavelengths (D2, 1.4 µm) map to Green, and shorter wavelengths (D1, 0.9 µm) map to Blue. Calibrated flux in MJy/sr is preserved.'}
              </span>
            </div>
          </div>
        )}

        {/* Analysis Hook Notice Banner */}
        {analysisSlotNotice && viewMode !== 'rgb' && (
          <div className="bg-cyan-500/10 border border-cyan-500/30 text-cyan-300 text-xs px-3 py-2 rounded-lg font-mono">
            ℹ {analysisSlotNotice}
          </div>
        )}

        {/* Main Player Display */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* 2D Canvas Viewer (Left 2 columns) */}
          <div className="lg:col-span-2 space-y-4">
            {viewMode === 'rgb' ? (
              isRgbLoading ? (
                <div className="h-[500px] sm:h-[540px] lg:h-[580px] bg-neutral-900 border border-neutral-800 rounded-lg flex flex-col items-center justify-center gap-3">
                  <Loader2 className="w-6 h-6 text-amber-400 animate-spin" />
                  <span className="text-xs text-neutral-400 font-mono">
                    Aligning multi-band SPHEREx cutouts on shared celestial WCS...
                  </span>
                </div>
              ) : rgbErrorMsg ? (
                <div className="h-[500px] sm:h-[540px] lg:h-[580px] bg-neutral-900 border border-red-500/40 rounded-lg flex flex-col items-center justify-center gap-2 p-6 text-center">
                  <AlertCircle className="w-8 h-8 text-red-400" />
                  <span className="text-xs text-red-300 font-mono">{rgbErrorMsg}</span>
                </div>
              ) : rgbData ? (
                <FrameCanvas
                  rgbData={rgbData}
                  stretch={stretch}
                  redStretch={redStretch}
                  greenStretch={greenStretch}
                  blueStretch={blueStretch}
                  aperture={selectedAperture}
                  onSelectAperture={(px, py) => setSelectedAperture({ x: px, y: py })}
                />
              ) : (
                <div className="h-[500px] sm:h-[540px] lg:h-[580px] bg-neutral-900 border border-neutral-800 rounded-lg flex items-center justify-center text-xs text-neutral-500">
                  No RGB composite available
                </div>
              )
            ) : isLoading ? (
              <div className="h-[500px] sm:h-[540px] lg:h-[580px] bg-neutral-900 border border-neutral-800 rounded-lg flex flex-col items-center justify-center gap-3">
                <Loader2 className="w-6 h-6 text-cyan-400 animate-spin" />
                <span className="text-xs text-neutral-400 font-mono">
                  Loading SPHEREx frame sequence...
                </span>
              </div>
            ) : activeDisplayFrame ? (
              <FrameCanvas
                frame={activeDisplayFrame}
                stretch={effectiveStretch}
                isSampleData={sequenceData?.isSampleData}
                aperture={selectedAperture}
                onSelectAperture={(px, py) => setSelectedAperture({ x: px, y: py })}
              />
            ) : (
              <div className="h-[500px] sm:h-[540px] lg:h-[580px] bg-neutral-900 border border-neutral-800 rounded-lg flex items-center justify-center text-xs text-neutral-500">
                No frames available
              </div>
            )}

            {/* Playback Controls (Active in Blink & Difference modes) */}
            {sequenceData && viewMode !== 'stacked' && viewMode !== 'shift-stack' && viewMode !== 'rgb' && (
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
                onLoopModeToggle={() =>
                  setLoopMode((m) => (m === 'loop' ? 'bounce' : 'loop'))
                }
                onRestart={handleRestart}
              />
            )}
          </div>

          {/* Right Column: Stretch Controls & Metadata Panel */}
          <div className="space-y-4">
            {viewMode === 'rgb' ? (
              <div className="space-y-4">
                {/* Channel stretch selection header */}
                <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-2.5 flex items-center justify-between text-xs">
                  <span className="text-neutral-400 font-medium">Channel Stretch:</span>
                  <div className="flex gap-1 font-mono">
                    <button
                      onClick={() => setRgbStretchChannel('all')}
                      className={`px-2 py-0.5 rounded text-xs transition ${
                        rgbStretchChannel === 'all'
                          ? 'bg-neutral-200 text-neutral-950 font-bold'
                          : 'text-neutral-400 hover:text-neutral-200'
                      }`}
                    >
                      All
                    </button>
                    <button
                      onClick={() => setRgbStretchChannel('red')}
                      className={`px-2 py-0.5 rounded text-xs transition ${
                        rgbStretchChannel === 'red'
                          ? 'bg-red-500 text-white font-bold'
                          : 'text-neutral-400 hover:text-red-300'
                      }`}
                    >
                      Red
                    </button>
                    <button
                      onClick={() => setRgbStretchChannel('green')}
                      className={`px-2 py-0.5 rounded text-xs transition ${
                        rgbStretchChannel === 'green'
                          ? 'bg-green-500 text-white font-bold'
                          : 'text-neutral-400 hover:text-green-300'
                      }`}
                    >
                      Green
                    </button>
                    <button
                      onClick={() => setRgbStretchChannel('blue')}
                      className={`px-2 py-0.5 rounded text-xs transition ${
                        rgbStretchChannel === 'blue'
                          ? 'bg-blue-500 text-white font-bold'
                          : 'text-neutral-400 hover:text-blue-300'
                      }`}
                    >
                      Blue
                    </button>
                  </div>
                </div>

                <StretchControls
                  stretch={
                    rgbStretchChannel === 'red'
                      ? redStretch
                      : rgbStretchChannel === 'green'
                      ? greenStretch
                      : rgbStretchChannel === 'blue'
                      ? blueStretch
                      : stretch
                  }
                  minPossible={
                    rgbData
                      ? rgbStretchChannel === 'red'
                        ? rgbData.channels.red.minFlux
                        : rgbStretchChannel === 'green'
                        ? rgbData.channels.green.minFlux
                        : rgbStretchChannel === 'blue'
                        ? rgbData.channels.blue.minFlux
                        : Math.min(
                            rgbData.channels.red.minFlux,
                            rgbData.channels.green.minFlux,
                            rgbData.channels.blue.minFlux
                          )
                      : 0
                  }
                  maxPossible={
                    rgbData
                      ? rgbStretchChannel === 'red'
                        ? rgbData.channels.red.maxFlux
                        : rgbStretchChannel === 'green'
                        ? rgbData.channels.green.maxFlux
                        : rgbStretchChannel === 'blue'
                        ? rgbData.channels.blue.maxFlux
                        : Math.max(
                            rgbData.channels.red.maxFlux,
                            rgbData.channels.green.maxFlux,
                            rgbData.channels.blue.maxFlux
                          )
                      : 10
                  }
                  onChange={(updated) => {
                    if (rgbStretchChannel === 'red') {
                      setRedStretch((prev) => ({ ...prev, ...updated }));
                    } else if (rgbStretchChannel === 'green') {
                      setGreenStretch((prev) => ({ ...prev, ...updated }));
                    } else if (rgbStretchChannel === 'blue') {
                      setBlueStretch((prev) => ({ ...prev, ...updated }));
                    } else {
                      setStretch((prev) => ({ ...prev, ...updated }));
                      setRedStretch((prev) => ({ ...prev, ...updated }));
                      setGreenStretch((prev) => ({ ...prev, ...updated }));
                      setBlueStretch((prev) => ({ ...prev, ...updated }));
                    }
                  }}
                  onAutoMinMax={() => {
                    if (!rgbData) return;
                    if (rgbStretchChannel === 'red') {
                      setRedStretch((prev) => ({
                        ...prev,
                        min: rgbData.channels.red.p1Flux,
                        max: rgbData.channels.red.p99Flux,
                      }));
                    } else if (rgbStretchChannel === 'green') {
                      setGreenStretch((prev) => ({
                        ...prev,
                        min: rgbData.channels.green.p1Flux,
                        max: rgbData.channels.green.p99Flux,
                      }));
                    } else if (rgbStretchChannel === 'blue') {
                      setBlueStretch((prev) => ({
                        ...prev,
                        min: rgbData.channels.blue.p1Flux,
                        max: rgbData.channels.blue.p99Flux,
                      }));
                    } else {
                      setRedStretch((prev) => ({
                        ...prev,
                        min: rgbData.channels.red.p1Flux,
                        max: rgbData.channels.red.p99Flux,
                      }));
                      setGreenStretch((prev) => ({
                        ...prev,
                        min: rgbData.channels.green.p1Flux,
                        max: rgbData.channels.green.p99Flux,
                      }));
                      setBlueStretch((prev) => ({
                        ...prev,
                        min: rgbData.channels.blue.p1Flux,
                        max: rgbData.channels.blue.p99Flux,
                      }));
                    }
                  }}
                />

                {/* RGB Channels Metadata Summary */}
                {rgbData && (
                  <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4 space-y-3 text-xs font-mono">
                    <div className="flex items-center justify-between border-b border-neutral-800/80 pb-2">
                      <span className="font-sans font-medium text-neutral-200">Composite Provenance</span>
                      <span className="text-[11px] text-neutral-500">Release: {rgbData.dataRelease}</span>
                    </div>
                    <div className="space-y-2">
                      <div className="flex justify-between items-center text-red-400">
                        <span>Red ({rgbData.channels.red.band}):</span>
                        <span className="truncate max-w-[140px] text-right">{rgbData.channels.red.obsId}</span>
                      </div>
                      <div className="flex justify-between items-center text-green-400">
                        <span>Green ({rgbData.channels.green.band}):</span>
                        <span className="truncate max-w-[140px] text-right">{rgbData.channels.green.obsId}</span>
                      </div>
                      <div className="flex justify-between items-center text-blue-400">
                        <span>Blue ({rgbData.channels.blue.band}):</span>
                        <span className="truncate max-w-[140px] text-right">{rgbData.channels.blue.obsId}</span>
                      </div>
                      <div className="border-t border-neutral-800/60 pt-2 flex justify-between text-neutral-400 text-[11px]">
                        <span>Shared Tangent Grid:</span>
                        <span>{rgbData.width} × {rgbData.height} px (TAN)</span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <>
                {/* Visual Controls: Stretch & Invert */}
                <StretchControls
                  stretch={effectiveStretch}
                  minPossible={activeDisplayFrame ? Math.min(effectiveStretch.min, activeDisplayFrame.minFlux) : 0}
                  maxPossible={activeDisplayFrame ? Math.max(effectiveStretch.max, activeDisplayFrame.maxFlux) : 10}
                  onChange={(updated) => setStretch((prev) => ({ ...prev, ...updated }))}
                  onAutoMinMax={handleAutoMinMax}
                  scope={stretchScope}
                  onScopeChange={setStretchScope}
                />

                {/* Metadata Panel */}
                {sequenceData && activeDisplayFrame && (
                  <MetadataPanel data={sequenceData} currentFrame={activeDisplayFrame} />
                )}
              </>
            )}
          </div>
        </div>

        {/* Aperture Photometry & Spectrum Drawer (Appears when user clicks canvas) */}
        {selectedAperture && sequenceData && (
          <PhotometryDrawer
            aperture={selectedAperture}
            frames={sequenceData.frames}
            onClose={() => setSelectedAperture(null)}
          />
        )}
      </main>

      {!isEmbedMode && <Footer />}

      {/* Guide & Keyboard Shortcuts Modal */}
      <HelpModal isOpen={isHelpOpen} onClose={() => setIsHelpOpen(false)} />
    </div>
  );
};

export default App;
