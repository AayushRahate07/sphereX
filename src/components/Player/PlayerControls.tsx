import React, { useEffect } from 'react';
import { Play, Pause, ChevronLeft, ChevronRight, Repeat, RotateCcw } from 'lucide-react';

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
}) => {
  // Keyboard navigation shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't trigger if user is typing in an input
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

  return (
    <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4 space-y-3">
      {/* Top row: Playback Buttons & Scrubber */}
      <div className="flex items-center gap-3">
        {/* Step Backward */}
        <button
          onClick={onStepBackward}
          title="Step Backward (Left Arrow)"
          className="p-2 rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-200 transition"
        >
          <ChevronLeft className="w-4 h-4" />
        </button>

        {/* Play / Pause Toggle */}
        <button
          onClick={onPlayToggle}
          title="Play / Pause (Space)"
          className={`px-4 py-2 rounded font-medium flex items-center gap-2 transition ${
            isPlaying
              ? 'bg-amber-500 hover:bg-amber-400 text-neutral-950 font-semibold'
              : 'bg-cyan-500 hover:bg-cyan-400 text-neutral-950 font-semibold'
          }`}
        >
          {isPlaying ? (
            <>
              <Pause className="w-4 h-4" /> Pause
            </>
          ) : (
            <>
              <Play className="w-4 h-4" /> Play
            </>
          )}
        </button>

        {/* Step Forward */}
        <button
          onClick={onStepForward}
          title="Step Forward (Right Arrow)"
          className="p-2 rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-200 transition"
        >
          <ChevronRight className="w-4 h-4" />
        </button>

        {/* Restart */}
        <button
          onClick={onRestart}
          title="Restart from Frame 0 (Home)"
          className="p-2 rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-400 hover:text-neutral-200 transition"
        >
          <RotateCcw className="w-4 h-4" />
        </button>

        {/* Timeline Scrubber */}
        <div className="flex-1 flex items-center gap-3 px-2">
          <input
            type="range"
            min={0}
            max={Math.max(0, totalFrames - 1)}
            value={currentFrame}
            onChange={(e) => onSeek(Number(e.target.value))}
            className="w-full h-2 bg-neutral-800 rounded-lg appearance-none cursor-pointer"
          />
          <span className="font-mono text-xs text-neutral-400 whitespace-nowrap min-w-[70px] text-right">
            Frame <strong className="text-neutral-100">{currentFrame + 1}</strong> / {totalFrames}
          </span>
        </div>
      </div>

      {/* Bottom row: Playback Speed & Loop Mode */}
      <div className="flex items-center justify-between border-t border-neutral-800/80 pt-3 text-xs text-neutral-400">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <span>Interval:</span>
            <input
              type="range"
              min={250}
              max={3500}
              step={50}
              value={Math.round(1000 / Math.max(0.01, fps))}
              onChange={(e) => onFpsChange(1000 / Math.max(1, Number(e.target.value)))}
              className="w-28 h-1.5 bg-neutral-800 rounded-lg appearance-none cursor-pointer"
            />
            <span className="font-mono text-neutral-200 font-medium min-w-[125px]">
              {Math.round(1000 / Math.max(0.01, fps))} ms ({fps < 1 ? fps.toFixed(2) : fps % 1 === 0 ? fps : fps.toFixed(1)} fps)
            </span>
          </div>

          {/* Quick Interval Presets */}
          <div className="flex items-center gap-1">
            {[
              { label: '3000ms', intervalMs: 3000, fps: 1000 / 3000, title: '3000 ms / frame (0.33 fps)' },
              { label: '2500ms', intervalMs: 2500, fps: 1000 / 2500, title: '2500 ms / frame (0.40 fps)' },
              { label: '2000ms', intervalMs: 2000, fps: 0.5, title: '2000 ms / frame (0.50 fps - Default)' },
              { label: '1500ms', intervalMs: 1500, fps: 1000 / 1500, title: '1500 ms / frame (0.67 fps)' },
              { label: '1000ms', intervalMs: 1000, fps: 1.0, title: '1000 ms / frame (1.0 fps)' },
              { label: '500ms', intervalMs: 500, fps: 2.0, title: 'Fast blink (500 ms / frame)' },
            ].map((preset) => {
              const currentMs = Math.round(1000 / Math.max(0.01, fps));
              const isActive = Math.abs(currentMs - preset.intervalMs) <= 30;
              return (
                <button
                  key={preset.label}
                  onClick={() => onFpsChange(preset.fps)}
                  title={preset.title}
                  className={`px-1.5 py-0.5 rounded text-[11px] font-mono transition ${
                    isActive
                      ? 'bg-neutral-700 text-cyan-300 font-semibold'
                      : 'bg-neutral-800/60 hover:bg-neutral-800 text-neutral-400'
                  }`}
                >
                  {preset.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Loop Mode Toggle */}
        <button
          onClick={onLoopModeToggle}
          title={`Mode: ${loopMode === 'loop' ? 'Continuous Loop' : 'Bounce (Back and Forth)'}`}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded transition text-xs ${
            loopMode === 'bounce'
              ? 'bg-neutral-800 text-amber-400 border border-amber-500/30'
              : 'bg-neutral-800 text-neutral-300 hover:text-neutral-100'
          }`}
        >
          <Repeat className="w-3.5 h-3.5" />
          <span className="capitalize">{loopMode}</span>
        </button>
      </div>
    </div>
  );
};
