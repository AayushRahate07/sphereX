import React from 'react';
import type { StretchParams } from '../../utils/stretch';
import { Sliders, SunMedium, Moon } from 'lucide-react';

interface StretchControlsProps {
  stretch: StretchParams;
  minPossible: number;
  maxPossible: number;
  onChange: (updated: Partial<StretchParams>) => void;
  onAutoMinMax: () => void;
}

export const StretchControls: React.FC<StretchControlsProps> = ({
  stretch,
  minPossible,
  maxPossible,
  onChange,
  onAutoMinMax,
}) => {
  return (
    <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm font-medium text-neutral-200">
          <Sliders className="w-4 h-4 text-cyan-400" />
          <span>Brightness Stretch & Contrast</span>
        </div>

        {/* Invert Toggle */}
        <button
          onClick={() => onChange({ invert: !stretch.invert })}
          title="Invert Colors (Toggle Dark-on-Light / Light-on-Dark)"
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-xs transition border ${
            stretch.invert
              ? 'bg-neutral-100 text-neutral-950 font-medium border-neutral-200'
              : 'bg-neutral-800 text-neutral-300 hover:text-neutral-100 border-neutral-700'
          }`}
        >
          {stretch.invert ? (
            <>
              <SunMedium className="w-3.5 h-3.5" /> Inverted (Dark on Light)
            </>
          ) : (
            <>
              <Moon className="w-3.5 h-3.5" /> Standard (Light on Dark)
            </>
          )}
        </button>
      </div>

      {/* Stretch Type Selection (Linear vs Log) */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-neutral-400 min-w-[70px]">Algorithm:</span>
        <div className="flex rounded-md bg-neutral-800/80 p-0.5 border border-neutral-700/60">
          <button
            onClick={() => onChange({ type: 'linear' })}
            className={`px-3 py-1 text-xs rounded transition font-medium ${
              stretch.type === 'linear'
                ? 'bg-cyan-500 text-neutral-950 shadow-sm'
                : 'text-neutral-400 hover:text-neutral-200'
            }`}
          >
            Linear
          </button>
          <button
            onClick={() => onChange({ type: 'log' })}
            className={`px-3 py-1 text-xs rounded transition font-medium ${
              stretch.type === 'log'
                ? 'bg-cyan-500 text-neutral-950 shadow-sm'
                : 'text-neutral-400 hover:text-neutral-200'
            }`}
          >
            Logarithmic
          </button>
        </div>

        <button
          onClick={onAutoMinMax}
          className="ml-auto text-xs px-2.5 py-1 rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-300 transition"
        >
          Auto Min/Max
        </button>
      </div>

      {/* Min / Max Cut Sliders */}
      <div className="space-y-2 pt-1">
        {/* Min Cut */}
        <div className="flex items-center gap-3">
          <span className="text-xs text-neutral-400 min-w-[65px]">Min Cut:</span>
          <input
            type="range"
            min={Math.floor(minPossible)}
            max={Math.ceil(maxPossible)}
            step={0.5}
            value={stretch.min}
            onChange={(e) => onChange({ min: Number(e.target.value) })}
            className="flex-1 h-1.5 bg-neutral-800 rounded appearance-none cursor-pointer"
          />
          <span className="font-mono text-xs text-neutral-300 min-w-[50px] text-right">
            {stretch.min.toFixed(1)}
          </span>
        </div>

        {/* Max Cut */}
        <div className="flex items-center gap-3">
          <span className="text-xs text-neutral-400 min-w-[65px]">Max Cut:</span>
          <input
            type="range"
            min={Math.floor(minPossible)}
            max={Math.ceil(maxPossible)}
            step={0.5}
            value={stretch.max}
            onChange={(e) => onChange({ max: Number(e.target.value) })}
            className="flex-1 h-1.5 bg-neutral-800 rounded appearance-none cursor-pointer"
          />
          <span className="font-mono text-xs text-neutral-300 min-w-[50px] text-right">
            {stretch.max.toFixed(1)}
          </span>
        </div>
      </div>
    </div>
  );
};
