import React, { useState, useEffect, useCallback, useRef } from 'react';
import type { SpherexApiResponse, SpherexBand, SpherexFrame } from './types/spherex';
import { DEFAULT_BAND, TEST_TARGETS } from './types/spherex';
import { fetchSpherexSequence, API_CONFIG } from './services/apiClient';
import { parseUrlState, syncUrlState, getShareableUrl } from './utils/urlState';
import type { StretchParams } from './utils/stretch';
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
import { AlertCircle, Loader2, Layers, Film, SplitSquareVertical, Move } from 'lucide-react';

export type ViewMode = 'blink' | 'difference' | 'stacked' | 'shift-stack';

export const App: React.FC = () => {
  // Parse initial state from URL query parameters
  const initialUrl = parseUrlState();

  const [ra, setRa] = useState<number>(initialUrl.ra ?? TEST_TARGETS[0].ra);
  const [dec, setDec] = useState<number>(initialUrl.dec ?? TEST_TARGETS[0].dec);
  const [fov, setFov] = useState<number>(initialUrl.size ?? 0.05);
  const [band, setBand] = useState<SpherexBand>(initialUrl.band ?? DEFAULT_BAND);
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
  const [fps, setFps] = useState<number>(initialUrl.speed ?? 4);
  const [loopMode, setLoopMode] = useState<'loop' | 'bounce'>('loop');
  const bounceDirectionRef = useRef<1 | -1>(1);

  // Data & loading state
  const [sequenceData, setSequenceData] = useState<SpherexApiResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [useSampleFile, setUseSampleFile] = useState<boolean>(API_CONFIG.useSampleFile);

  // Stretch & contrast state
  const [stretch, setStretch] = useState<StretchParams>({
    type: initialUrl.stretch ?? 'linear',
    min: initialUrl.min ?? 4.0,
    max: initialUrl.max ?? 50.0,
    invert: initialUrl.invert ?? false,
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
    setIsLoading(true);
    setErrorMsg(null);
    try {
      API_CONFIG.useSampleFile = useSampleFile;
      const data = await fetchSpherexSequence({
        ra,
        dec,
        size: fov,
        band,
      });

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
      setErrorMsg(err.message || 'Failed to fetch SPHEREx frames.');
    } finally {
      setIsLoading(false);
    }
  }, [ra, dec, fov, band, useSampleFile]);

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
    });
  }, [ra, dec, fov, band, fps, stretch, isEmbedMode]);

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
    setSelectedAperture(null);
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

  return (
    <div className="min-h-screen flex flex-col bg-neutral-950 text-neutral-100 font-sans">
      {!isEmbedMode && (
        <Navbar
          useSampleFile={useSampleFile}
          onToggleDataSource={(useSample) => {
            setUseSampleFile(useSample);
            API_CONFIG.useSampleFile = useSample;
          }}
          onShare={handleShare}
          onOpenHelp={() => setIsHelpOpen(true)}
        />
      )}

      <main className="flex-1 max-w-7xl w-full mx-auto p-4 space-y-4">
        {/* Error notification if Member 1 API fails */}
        {errorMsg && (
          <div className="bg-red-500/10 border border-red-500/40 text-red-300 p-3 rounded-lg text-xs flex items-center justify-between">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />
              <span>{errorMsg}</span>
            </div>
            <button
              onClick={() => {
                setUseSampleFile(true);
                API_CONFIG.useSampleFile = true;
              }}
              className="px-2 py-1 rounded bg-red-500/20 hover:bg-red-500/30 text-red-200 transition font-mono"
            >
              Switch to Sample File
            </button>
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
          </div>

          <span className="text-[11px] text-neutral-500 hidden sm:inline font-mono">
            {viewMode === 'blink'
              ? 'Multi-epoch blink sequence'
              : viewMode === 'difference'
              ? 'Frame subtraction (Member 3 hook)'
              : viewMode === 'stacked'
              ? 'Co-added stack (Member 3 hook)'
              : 'Proper motion co-addition (Idea 1)'}
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
                aperture={selectedAperture}
                onSelectAperture={(px, py) => setSelectedAperture({ x: px, y: py })}
              />
            ) : (
              <div className="h-[480px] bg-neutral-900 border border-neutral-800 rounded-lg flex items-center justify-center text-xs text-neutral-500">
                No frames available
              </div>
            )}

            {/* Playback Controls (Active in Blink & Difference modes) */}
            {sequenceData && viewMode !== 'stacked' && viewMode !== 'shift-stack' && (
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
