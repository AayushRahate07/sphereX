import React, { useState, useEffect, useCallback, useRef } from 'react';
import type { SpherexApiResponse, SpherexBand } from './types/spherex';
import { DEFAULT_BAND, TEST_TARGETS } from './types/spherex';
import { fetchSpherexSequence, API_CONFIG } from './services/apiClient';
import { parseUrlState, syncUrlState, getShareableUrl } from './utils/urlState';
import type { StretchParams } from './utils/stretch';
import { FrameCanvas } from './components/Player/FrameCanvas';
import { PlayerControls } from './components/Player/PlayerControls';
import { StretchControls } from './components/Controls/StretchControls';
import { TargetBar } from './components/Navigation/TargetBar';
import { MetadataPanel } from './components/HUD/MetadataPanel';
import { Navbar } from './components/Header/Navbar';
import { Footer } from './components/Footer/Footer';
import { AlertCircle, Loader2 } from 'lucide-react';

export const App: React.FC = () => {
  // Parse initial state from URL query parameters
  const initialUrl = parseUrlState();

  const [ra, setRa] = useState<number>(initialUrl.ra ?? TEST_TARGETS[0].ra);
  const [dec, setDec] = useState<number>(initialUrl.dec ?? TEST_TARGETS[0].dec);
  const [fov, setFov] = useState<number>(initialUrl.size ?? 0.05);
  const [band, setBand] = useState<SpherexBand>(initialUrl.band ?? DEFAULT_BAND);
  const [isEmbedMode] = useState<boolean>(initialUrl.embed ?? false);

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
    if (!isPlaying || !sequenceData || sequenceData.frames.length <= 1) {
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
  }, [isPlaying, fps, loopMode, sequenceData]);

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

  const currentFrame =
    sequenceData && sequenceData.frames.length > 0
      ? sequenceData.frames[currentFrameIndex]
      : null;

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
            isLoading={isLoading}
          />
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
            ) : currentFrame ? (
              <FrameCanvas
                frame={currentFrame}
                stretch={stretch}
                isSampleData={sequenceData?.isSampleData}
              />
            ) : (
              <div className="h-[480px] bg-neutral-900 border border-neutral-800 rounded-lg flex items-center justify-center text-xs text-neutral-500">
                No frames available
              </div>
            )}

            {/* Playback Controls */}
            {sequenceData && (
              <PlayerControls
                currentFrame={currentFrameIndex}
                totalFrames={sequenceData.frameCount}
                isPlaying={isPlaying}
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
              minPossible={currentFrame?.minFlux ?? 0}
              maxPossible={currentFrame?.maxFlux ?? 100}
              onChange={(updated) => setStretch((prev) => ({ ...prev, ...updated }))}
              onAutoMinMax={handleAutoMinMax}
            />

            {/* Metadata Panel */}
            {sequenceData && currentFrame && (
              <MetadataPanel data={sequenceData} currentFrame={currentFrame} />
            )}
          </div>
        </div>
      </main>

      {!isEmbedMode && <Footer />}
    </div>
  );
};

export default App;
