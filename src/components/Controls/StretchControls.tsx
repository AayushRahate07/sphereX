import React from 'react';
import type { StretchParams } from '../../utils/stretch';
import { Sliders, SunMedium, Moon } from 'lucide-react';

interface StretchControlsProps {
  stretch: StretchParams;
  minPossible: number;
  maxPossible: number;
  onChange: (updated: Partial<StretchParams>) => void;
  onAutoMinMax: () => void;
  scope?: 'sequence' | 'frame';
  onScopeChange?: (scope: 'sequence' | 'frame') => void;
}

export const StretchControls: React.FC<StretchControlsProps> = ({
  stretch,
  minPossible,
  maxPossible,
  onChange,
  onAutoMinMax,
  scope = 'sequence',
  onScopeChange,
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

      {/* Stretch Type Selection (Linear vs Log vs Asinh) */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-neutral-400 min-w-[70px]">Algorithm:</span>
        <div className="flex rounded-md bg-neutral-800/80 p-0.5 border border-neutral-700/60">
          <button
            onClick={() => onChange({ type: 'linear' })}
            className={`px-2.5 py-1 text-xs rounded transition font-medium ${
              stretch.type === 'linear'
                ? 'bg-cyan-500 text-neutral-950 shadow-sm'
                : 'text-neutral-400 hover:text-neutral-200'
            }`}
          >
            Linear
          </button>
          <button
            onClick={() => onChange({ type: 'log' })}
            className={`px-2.5 py-1 text-xs rounded transition font-medium ${
              stretch.type === 'log'
                ? 'bg-cyan-500 text-neutral-950 shadow-sm'
                : 'text-neutral-400 hover:text-neutral-200'
            }`}
          >
            Log
          </button>
          <button
            onClick={() => onChange({ type: 'asinh' })}
            className={`px-2.5 py-1 text-xs rounded transition font-medium ${
              stretch.type === 'asinh'
                ? 'bg-cyan-500 text-neutral-950 shadow-sm'
                : 'text-neutral-400 hover:text-neutral-200'
            }`}
          >
            Asinh
          </button>
        </div>

        <button
          onClick={onAutoMinMax}
          title="Compute robust 1st-99th percentile limits over clean pixels (rejects cosmic rays and defects)"
          className="ml-auto text-xs px-2.5 py-1 rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-300 transition"
        >
          Auto Min/Max
        </button>
      </div>

      {/* Scope Selection (Sequence / Shared vs Frame / Local) */}
      {onScopeChange && (
        <div className="flex items-center gap-2">
          <span className="text-xs text-neutral-400 min-w-[70px]">Scope:</span>
          <div className="flex rounded-md bg-neutral-800/80 p-0.5 border border-neutral-700/60">
            <button
              onClick={() => onScopeChange('sequence')}
              title="Shared sequence-wide dynamic range: preserves absolute brightness comparison across blink epochs"
              className={`px-2.5 py-1 text-xs rounded transition font-medium ${
                scope === 'sequence'
                  ? 'bg-cyan-500 text-neutral-950 shadow-sm'
                  : 'text-neutral-400 hover:text-neutral-200'
              }`}
            >
              Sequence (Shared)
            </button>
            <button
              onClick={() => onScopeChange('frame')}
              title="Per-frame adaptive range: prevents bright stars or defects in other epochs from crushing faint structures"
              className={`px-2.5 py-1 text-xs rounded transition font-medium ${
                scope === 'frame'
                  ? 'bg-cyan-500 text-neutral-950 shadow-sm'
                  : 'text-neutral-400 hover:text-neutral-200'
              }`}
            >
              Frame (Adaptive)
            </button>
          </div>
        </div>
      )}

      {/* Min / Max Cut Sliders */}
      {(() => {
        const span = Math.max(0.01, maxPossible - minPossible);
        const step = Math.min(0.5, Math.max(0.001, span / 200));
        const decimals = span < 1 ? 3 : span < 10 ? 2 : 1;
        return (
          <div className="space-y-2 pt-1">
            {/* Min Cut */}
            <div className="flex items-center gap-3">
              <span className="text-xs text-neutral-400 min-w-[65px]">Min Cut:</span>
              <input
                type="range"
                min={minPossible}
                max={maxPossible}
                step={step}
                value={stretch.min}
                onChange={(e) => onChange({ min: Number(e.target.value) })}
                className="flex-1 h-1.5 bg-neutral-800 rounded appearance-none cursor-pointer"
              />
              <span className="font-mono text-xs text-neutral-300 min-w-[55px] text-right">
                {stretch.min.toFixed(decimals)}
              </span>
            </div>

            {/* Max Cut */}
            <div className="flex items-center gap-3">
              <span className="text-xs text-neutral-400 min-w-[65px]">Max Cut:</span>
              <input
                type="range"
                min={minPossible}
                max={maxPossible}
                step={step}
                value={stretch.max}
                onChange={(e) => onChange({ max: Number(e.target.value) })}
                className="flex-1 h-1.5 bg-neutral-800 rounded appearance-none cursor-pointer"
              />
              <span className="font-mono text-xs text-neutral-300 min-w-[55px] text-right">
                {stretch.max.toFixed(decimals)}
              </span>
            </div>
          </div>
        );
      })()}
    </div>
  );
};
