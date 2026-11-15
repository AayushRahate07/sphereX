import React, { useEffect } from 'react';
import { Play, Pause, ChevronLeft, ChevronRight, Repeat, RotateCcw } from 'lucide-react';
import type { SpherexFrame } from '../../types/spherex';

interface PlayerControlsProps {
  currentFrame: number;
  totalFrames: number;
  isPlaying: boolean;
  fps: number;
  loopMode: 'loop' | 'bounce';
  onPlayToggle: () => void;
  onStepForward: () => void;
  onStepBackward: () => void;
  onSeek: (frameIndex: number) => void;
  onFpsChange: (fps: number) => void;
  onLoopModeToggle: () => void;
  onRestart: () => void;
  frames?: SpherexFrame[];
}

export const PlayerControls: React.FC<PlayerControlsProps> = ({
  currentFrame,
  totalFrames,
  isPlaying,
  fps,
  loopMode,
  onPlayToggle,
  onStepForward,
  onStepBackward,
  onSeek,
  onFpsChange,
  onLoopModeToggle,
  onRestart,
  frames = [],
}) => {
  // Keyboard navigation shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (['INPUT', 'SELECT', 'TEXTAREA'].includes((e.target as HTMLElement)?.tagName)) {
        return;
      }

      if (e.code === 'Space') {
        e.preventDefault();
        onPlayToggle();
      } else if (e.code === 'ArrowRight') {
        e.preventDefault();
        onStepForward();
      } else if (e.code === 'ArrowLeft') {
        e.preventDefault();
        onStepBackward();
      } else if (e.code === 'Home') {
        e.preventDefault();
        onRestart();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onPlayToggle, onStepForward, onStepBackward, onRestart]);

  // Current active frame date
  const activeFrame = frames[currentFrame];
  const activeDateFormatted = activeFrame?.dateUtc
    ? new Date(activeFrame.dateUtc).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      })
    : null;

  // Generate timeline date labels matching user Image 2 (e.g. May 2025, Jul 2025, etc.)
  const timelineDateLabels = React.useMemo(() => {
    if (frames.length > 0) {
      return frames.map((f, idx) => {
        try {
          const d = new Date(f.dateUtc);
          const month = d.toLocaleString('en-US', { month: 'short' });
          const year = d.getFullYear();
          return { label: `${month}`, sub: `${year}`, idx };
        } catch {
          return { label: `Epoch ${idx + 1}`, sub: '', idx };
        }
      });
    }
    // Default fallback ticks
    return [
      { label: 'May', sub: '2025', idx: 0 },
      { label: 'Jul', sub: '2025', idx: 1 },
      { label: 'Sep', sub: '2025', idx: 2 },
      { label: 'Nov', sub: '2025', idx: 3 },
      { label: 'Jan', sub: '2026', idx: 4 },
    ];
  }, [frames]);

  return (
    <div className="bg-neutral-900/90 border border-neutral-800 rounded-xl p-3 space-y-2.5 text-xs text-neutral-300 shadow-md">
      {/* 1. TIMELINE SCRUBBER & DATE RULER (Directly matching user Image 2) */}
      <div className="space-y-1 bg-neutral-950/60 rounded-lg p-2.5 border border-neutral-800/80">
        {/* Scrubber slider track with custom bright blue thumb */}
        <div className="relative flex items-center px-1">
          <input
            type="range"
            min={0}
            max={Math.max(0, totalFrames - 1)}
            value={currentFrame}
            onChange={(e) => onSeek(Number(e.target.value))}
            className="w-full h-1.5 bg-neutral-700/80 rounded-lg appearance-none cursor-pointer accent-blue-500 hover:accent-blue-400 focus:outline-none"
          />
        </div>

        {/* Date labels spaced underneath track (matching Image 2) */}
        <div className="flex justify-between px-1 text-[10px] text-neutral-400 font-sans pt-0.5">
          {timelineDateLabels.map((item, idx) => {
            const isCurrent = idx === currentFrame;
            return (
              <div
                key={idx}
                onClick={() => onSeek(idx)}
                className={`flex flex-col items-center cursor-pointer transition select-none ${
                  isCurrent ? 'text-blue-400 font-bold scale-105' : 'hover:text-neutral-200'
                }`}
              >
                <span>{item.label}</span>
                <span className="text-[9px] text-neutral-500">{item.sub}</span>
              </div>
            );
          })}
        </div>

        {/* Fine tick-mark ruler track (matching bottom ruler in Image 2) */}
        <div className="relative h-2 w-full flex justify-between items-end px-1.5 opacity-60">
          {Array.from({ length: 25 }).map((_, i) => (
            <div
              key={i}
              className={`w-[1px] bg-neutral-600 ${
                i % 4 === 0 ? 'h-2 bg-blue-400/80' : 'h-1 bg-neutral-700'
              }`}
            />
          ))}
        </div>
      </div>

      {/* 2. PLAYBACK CONTROLS ROW */}
      <div className="flex items-center justify-between gap-2 pt-0.5">
        {/* Playback Buttons Group */}
        <div className="flex items-center gap-1.5">
          {/* Step Back */}
          <button
            onClick={onStepBackward}
            title="Step Backward (Left Arrow)"
            className="p-1.5 rounded-lg bg-neutral-800 hover:bg-neutral-700 text-neutral-300 transition"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>

          {/* Play / Pause Toggle */}
          <button
            onClick={onPlayToggle}
            title="Play / Pause (Space)"
            className={`px-3 py-1.5 rounded-lg font-semibold flex items-center gap-1.5 text-xs transition ${
              isPlaying
                ? 'bg-amber-500 hover:bg-amber-400 text-neutral-950'
                : 'bg-blue-600 hover:bg-blue-500 text-white shadow-sm'
            }`}
          >
            {isPlaying ? (
              <>
                <Pause className="w-3.5 h-3.5" /> Pause
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5 fill-current" /> Play
              </>
            )}
          </button>

          {/* Step Forward */}
          <button
            onClick={onStepForward}
            title="Step Forward (Right Arrow)"
            className="p-1.5 rounded-lg bg-neutral-800 hover:bg-neutral-700 text-neutral-300 transition"
          >
            <ChevronRight className="w-4 h-4" />
          </button>

          {/* Restart */}
          <button
            onClick={onRestart}
            title="Restart to first frame"
            className="p-1.5 rounded-lg bg-neutral-800 hover:bg-neutral-700 text-neutral-400 hover:text-neutral-200 transition ml-0.5"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Current Frame & Date Badge */}
        <div className="flex items-center gap-2 font-mono text-[11px] text-neutral-400">
          {activeDateFormatted && (
            <span className="text-neutral-200 hidden sm:inline">
              📅 {activeDateFormatted}
            </span>
          )}
          <span className="px-2 py-0.5 rounded bg-neutral-800 border border-neutral-700 text-neutral-200 font-semibold">
            {currentFrame + 1} / {totalFrames}
          </span>
        </div>

        {/* Speed & Loop Controls Group */}
        <div className="flex items-center gap-2">
          {/* Speed Selector */}
          <div className="flex items-center gap-1.5">
            <span className="text-[11px] text-neutral-400">Speed:</span>
            <select
              value={fps}
              onChange={(e) => onFpsChange(Number(e.target.value))}
              className="bg-neutral-800 border border-neutral-700 rounded px-1.5 py-0.5 text-[11px] font-mono text-neutral-200 focus:outline-none"
            >
              <option value={0.33}>0.33 fps (3.0s)</option>
              <option value={0.5}>0.5 fps (2.0s)</option>
              <option value={1}>1 fps (1.0s)</option>
              <option value={2}>2 fps</option>
              <option value={4}>4 fps (Default)</option>
              <option value={8}>8 fps (Fast)</option>
              <option value={15}>15 fps</option>
            </select>
          </div>

          {/* Loop / Bounce Toggle */}
          <button
            onClick={onLoopModeToggle}
            title={`Playback Mode: ${loopMode === 'loop' ? 'Continuous Loop' : 'Bounce Back-and-Forth'}`}
            className={`p-1.5 rounded-lg border transition ${
              loopMode === 'bounce'
                ? 'bg-blue-500/20 text-blue-300 border-blue-500/40'
                : 'bg-neutral-800 text-neutral-400 hover:text-neutral-200 border-neutral-700'
            }`}
          >
            <Repeat className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
};
