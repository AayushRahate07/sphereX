import React, { useState, useEffect, useCallback, useRef } from 'react';
import type { SpherexApiResponse, SpherexBand, SpherexFrame } from './types/spherex';
import { DEFAULT_BAND, TEST_TARGETS } from './types/spherex';
import { fetchSpherexSequence } from './services/apiClient';
import { parseUrlState, syncUrlState, getShareableUrl } from './utils/urlState';
import type { StretchParams } from './utils/stretch';
import { FrameCanvas } from './components/Player/FrameCanvas';
import { PlayerControls } from './components/Player/PlayerControls';
import { StretchControls } from './components/Controls/StretchControls';
import { TargetBar } from './components/Navigation/TargetBar';
import { AladinSkyPicker } from './components/Navigation/AladinSkyPicker';
import { MetadataPanel } from './components/HUD/MetadataPanel';
import { Navbar } from './components/Header/Navbar';
import { Footer } from './components/Footer/Footer';
import { computeDifference, stackFrames } from './analysis';
import { AlertCircle, Loader2, Layers, Film, SplitSquareVertical } from 'lucide-react';

export type ViewMode = 'blink' | 'difference' | 'stacked';

export const App: React.FC = () => {
  // Parse initial state from URL query parameters
  const initialUrl = parseUrlState();

  const [ra, setRa] = useState<number>(initialUrl.ra ?? TEST_TARGETS[0].ra);
  const [dec, setDec] = useState<number>(initialUrl.dec ?? TEST_TARGETS[0].dec);
  const [fov, setFov] = useState<number>(initialUrl.size ?? 0.05);
  const [band, setBand] = useState<SpherexBand>(initialUrl.band ?? DEFAULT_BAND);
  const [maxFrames] = useState<number | undefined>(initialUrl.maxFrames);
  const [isEmbedMode] = useState<boolean>(initialUrl.embed ?? false);

  // Aladin Sky Picker drawer toggle
  const [isAladinOpen, setIsAladinOpen] = useState<boolean>(false);

  // View Mode: Blink sequence vs Difference vs Stacked
  const [viewMode, setViewMode] = useState<ViewMode>('blink');

  // Playback state
  const [currentFrameIndex, setCurrentFrameIndex] = useState<number>(0);
  const [isPlaying, setIsPlaying] = useState<boolean>(true);
  const [fps, setFps] = useState<number>(initialUrl.speed ?? 4);
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
    min: initialUrl.min ?? 4.0,
    max: initialUrl.max ?? 50.0,
    invert: initialUrl.invert ?? false,
  });

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

      // Auto-set min/max if not specified in URL
      if (data.frames.length > 0) {
        const f0 = data.frames[0];
        setStretch((prev) => ({
          ...prev,
          min: initialUrl.min ?? Math.max(0, f0.minFlux),
          max: initialUrl.max ?? f0.maxFlux,
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
    loadSequence();
  }, [loadSequence]);

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
    setStretch((prev) => ({
      ...prev,
      min: Math.max(0, cur.minFlux),
      max: cur.maxFlux,
    }));
  }, [sequenceData, currentFrameIndex]);

  const handleTargetChange = (newRa: number, newDec: number) => {
    setRa(newRa);
    setDec(newDec);
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
    }
  }

  return (
    <div className="min-h-screen flex flex-col bg-neutral-950 text-neutral-100 font-sans">
      {!isEmbedMode && (
        <Navbar
          onShare={handleShare}
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
            }}
          />
        )}

        {/* View Mode Selector Tabs (Blink Player / Difference View / Stacked) */}
        <div className="flex items-center justify-between bg-neutral-900 border border-neutral-800 rounded-lg p-2 text-xs">
          <div className="flex items-center gap-1.5">
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
          </div>

          <span className="text-[11px] text-neutral-500 hidden sm:inline font-mono">
            {viewMode === 'blink'
              ? 'Multi-epoch blink sequence'
              : viewMode === 'difference'
              ? 'Frame subtraction (Member 3 hook)'
              : 'Co-added stack (Member 3 hook)'}
          </span>
        </div>

        {/* Analysis Hook Notice Banner */}
        {analysisSlotNotice && (
          <div className="bg-cyan-500/10 border border-cyan-500/30 text-cyan-300 text-xs px-3 py-2 rounded-lg font-mono">
            ℹ {analysisSlotNotice}
          </div>
        )}

        {/* Main Player Display */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* 2D Canvas Viewer (Left 2 columns) */}
          <div className="lg:col-span-2 space-y-4">
            {isLoading ? (
              <div className="h-[480px] bg-neutral-900 border border-neutral-800 rounded-lg flex flex-col items-center justify-center gap-3">
                <Loader2 className="w-6 h-6 text-cyan-400 animate-spin" />
                <span className="text-xs text-neutral-400 font-mono">
                  Loading SPHEREx frame sequence...
                </span>
              </div>
            ) : activeDisplayFrame ? (
              <FrameCanvas
                frame={activeDisplayFrame}
                stretch={stretch}
                isSampleData={sequenceData?.isSampleData}
              />
            ) : (
              <div className="h-[480px] bg-neutral-900 border border-neutral-800 rounded-lg flex items-center justify-center text-xs text-neutral-500">
                No frames available
              </div>
            )}

            {/* Playback Controls (Active in Blink & Difference modes) */}
            {sequenceData && viewMode !== 'stacked' && (
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
            {/* Visual Controls: Stretch & Invert */}
            <StretchControls
              stretch={stretch}
              minPossible={activeDisplayFrame?.minFlux ?? 0}
              maxPossible={activeDisplayFrame?.maxFlux ?? 100}
              onChange={(updated) => setStretch((prev) => ({ ...prev, ...updated }))}
              onAutoMinMax={handleAutoMinMax}
            />

            {/* Metadata Panel */}
            {sequenceData && activeDisplayFrame && (
              <MetadataPanel data={sequenceData} currentFrame={activeDisplayFrame} />
            )}
          </div>
        </div>
      </main>

      {!isEmbedMode && <Footer />}
    </div>
  );
};

export default App;
