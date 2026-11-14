import React from 'react';
import { Move, RotateCcw, Zap } from 'lucide-react';

interface ShiftStackControlsProps {
  pmRa: number;
  pmDec: number;
  onChangePm: (pmRa: number, pmDec: number) => void;
  onReset: () => void;
}

export const ShiftStackControls: React.FC<ShiftStackControlsProps> = ({
  pmRa,
  pmDec,
  onChangePm,
  onReset,
}) => {
  return (
    <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4 space-y-4 text-xs">
      <div className="flex items-center justify-between border-b border-neutral-800/80 pb-2">
        <div className="flex items-center gap-2 font-medium text-neutral-200">
          <Move className="w-4 h-4 text-cyan-400" />
          <span>Shift-and-Stack Motion Controls</span>
        </div>
        <button
          onClick={onReset}
          title="Reset Proper Motion to 0"
          className="flex items-center gap-1 text-[11px] text-neutral-400 hover:text-neutral-200 px-2 py-0.5 rounded bg-neutral-800 transition"
        >
          <RotateCcw className="w-3 h-3" /> Reset
        </button>
      </div>

      <p className="text-neutral-400 text-[11px] leading-relaxed">
        Adjust hypothesized proper motion in arcseconds per year. Each frame is shifted by{' '}
        <span className="font-mono text-cyan-400">&Delta;t &times; &mu;</span> before stacking, causing
        objects moving at that velocity to add constructively while stationary stars streak.
      </p>

      {/* Preset Proper Motions */}
      <div className="space-y-1.5">
        <span className="text-neutral-400 text-[11px] font-medium flex items-center gap-1">
          <Zap className="w-3 h-3 text-amber-400" /> Target Motion Presets:
        </span>
        <div className="flex flex-wrap gap-1.5">
          <button
            onClick={() => onChangePm(0, 0)}
            className={`px-2 py-1 rounded border transition ${
              pmRa === 0 && pmDec === 0
                ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/50 font-semibold'
                : 'bg-neutral-800 hover:bg-neutral-700 text-neutral-300 border-neutral-700/60'
            }`}
          >
            Zero Motion (Stars)
          </button>
          <button
            onClick={() => onChangePm(-8.1, 0.6)}
            className={`px-2 py-1 rounded border transition ${
              pmRa === -8.1 && pmDec === 0.6
                ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/50 font-semibold'
                : 'bg-neutral-800 hover:bg-neutral-700 text-neutral-300 border-neutral-700/60'
            }`}
          >
            WISE 0855 (-8.1, +0.6 &quot;/yr)
          </button>
          <button
            onClick={() => onChangePm(-0.8, 10.36)}
            className={`px-2 py-1 rounded border transition ${
              pmRa === -0.8 && pmDec === 10.36
                ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/50 font-semibold'
                : 'bg-neutral-800 hover:bg-neutral-700 text-neutral-300 border-neutral-700/60'
            }`}
          >
            Barnard&apos;s Star (-0.8, +10.36 &quot;/yr)
          </button>
          <button
            onClick={() => onChangePm(3.96, -2.54)}
            className={`px-2 py-1 rounded border transition ${
              pmRa === 3.96 && pmDec === -2.54
                ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/50 font-semibold'
                : 'bg-neutral-800 hover:bg-neutral-700 text-neutral-300 border-neutral-700/60'
            }`}
          >
            Eps Indi B (+3.96, -2.54 &quot;/yr)
          </button>
        </div>
      </div>

      {/* RA Motion Slider */}
      <div className="space-y-1.5 pt-1">
        <div className="flex items-center justify-between">
          <label className="text-neutral-300">
            &mu;<sub>&alpha;</sub> cos &delta; (RA Motion):
          </label>
          <span className="font-mono text-cyan-400 font-semibold">
            {pmRa > 0 ? `+${pmRa.toFixed(1)}` : pmRa.toFixed(1)} &quot;/yr
          </span>
        </div>
        <input
          type="range"
          min={-20}
          max={20}
          step={0.1}
          value={pmRa}
          onChange={(e) => onChangePm(parseFloat(e.target.value), pmDec)}
          className="w-full h-1.5 bg-neutral-800 rounded appearance-none cursor-pointer"
        />
        <div className="flex justify-between text-[10px] text-neutral-500 font-mono">
          <span>-20 &quot;/yr</span>
          <span>0</span>
          <span>+20 &quot;/yr</span>
        </div>
      </div>

      {/* Dec Motion Slider */}
      <div className="space-y-1.5 pt-1">
        <div className="flex items-center justify-between">
          <label className="text-neutral-300">&mu;<sub>&delta;</sub> (Dec Motion):</label>
          <span className="font-mono text-cyan-400 font-semibold">
            {pmDec > 0 ? `+${pmDec.toFixed(1)}` : pmDec.toFixed(1)} &quot;/yr
          </span>
        </div>
        <input
          type="range"
          min={-20}
          max={20}
          step={0.1}
          value={pmDec}
          onChange={(e) => onChangePm(pmRa, parseFloat(e.target.value))}
          className="w-full h-1.5 bg-neutral-800 rounded appearance-none cursor-pointer"
        />
        <div className="flex justify-between text-[10px] text-neutral-500 font-mono">
          <span>-20 &quot;/yr</span>
          <span>0</span>
          <span>+20 &quot;/yr</span>
        </div>
      </div>

      <div className="bg-neutral-950/60 border border-neutral-800 rounded p-2.5 text-[11px] text-neutral-400 font-mono">
        Active Vector: [&mu;<sub>&alpha;</sub> = {pmRa.toFixed(2)}, &mu;<sub>&delta;</sub> = {pmDec.toFixed(2)}] &quot;/yr
      </div>
    </div>
  );
};
