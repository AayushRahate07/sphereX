import React, { useState, useMemo } from 'react';
import type { SpherexFrame } from '../../types/spherex';
import { computeLightCurve, computeSpectrum } from '../../analysis';
import { LineChart, X, Activity, Radio } from 'lucide-react';

interface PhotometryDrawerProps {
  aperture: { x: number; y: number } | null;
  frames: SpherexFrame[];
  onClose: () => void;
}

export const PhotometryDrawer: React.FC<PhotometryDrawerProps> = ({
  aperture,
  frames,
  onClose,
}) => {
  const [activeTab, setActiveTab] = useState<'lightcurve' | 'spectrum'>('lightcurve');
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  // Compute or fallback light curve data
  const lightCurveData = useMemo(() => {
    if (!aperture || frames.length === 0) return [];

    // Try Member 3's hook
    const m3Result = computeLightCurve(frames, aperture.x, aperture.y);
    if (m3Result && m3Result.length > 0) {
      return m3Result.map((pt, idx) => ({
        mjd: pt.mjd,
        flux: pt.flux,
        wavelength: frames[idx]?.wavelengthMicrons ?? 0,
        date: frames[idx]?.dateUtc ?? '',
      }));
    }

    // Client default 2.5-pixel circular aperture sum for immediate testing
    const rSq = 2.5 * 2.5;
    return frames.map((f) => {
      let sum = 0;
      let count = 0;
      for (let dy = -3; dy <= 3; dy++) {
        const y = Math.round(aperture.y) + dy;
        if (y < 0 || y >= f.height) continue;
        for (let dx = -3; dx <= 3; dx++) {
          const x = Math.round(aperture.x) + dx;
          if (x < 0 || x >= f.width) continue;
          if (dx * dx + dy * dy <= rSq) {
            sum += f.flux[y * f.width + x];
            count++;
          }
        }
      }
      return {
        mjd: f.mjd,
        flux: +(sum / Math.max(1, count)).toFixed(2),
        wavelength: f.wavelengthMicrons,
        date: f.dateUtc,
      };
    });
  }, [aperture, frames]);

  // Compute or fallback spectrum data
  const spectrumData = useMemo(() => {
    if (!aperture || frames.length === 0) return [];

    // Try Member 3's hook
    const m3Result = computeSpectrum(frames, aperture.x, aperture.y);
    if (m3Result && m3Result.length > 0) {
      return m3Result;
    }

    // Default: group by wavelength
    return lightCurveData.map((d) => ({
      wavelengthMicrons: d.wavelength,
      flux: d.flux,
    }));
  }, [aperture, frames, lightCurveData]);

  if (!aperture) return null;

  // Chart dimensions & scaling
  const chartWidth = 520;
  const chartHeight = 160;
  const padding = { top: 15, right: 20, bottom: 30, left: 45 };

  const currentDataset = activeTab === 'lightcurve'
    ? lightCurveData.map((d) => ({ xVal: d.mjd, yVal: d.flux, label: `MJD ${d.mjd.toFixed(1)} (${d.date})` }))
    : spectrumData.map((d) => ({ xVal: d.wavelengthMicrons, yVal: d.flux, label: `${d.wavelengthMicrons.toFixed(2)} µm` }));

  const xMin = currentDataset.length > 0 ? Math.min(...currentDataset.map((d) => d.xVal)) : 0;
  const xMax = currentDataset.length > 0 ? Math.max(...currentDataset.map((d) => d.xVal)) : 1;
  const yMin = currentDataset.length > 0 ? Math.max(0, Math.min(...currentDataset.map((d) => d.yVal)) * 0.9) : 0;
  const yMax = currentDataset.length > 0 ? Math.max(...currentDataset.map((d) => d.yVal)) * 1.1 : 10;

  const getX = (val: number) => {
    if (xMax <= xMin) return padding.left;
    return padding.left + ((val - xMin) / (xMax - xMin)) * (chartWidth - padding.left - padding.right);
  };

  const getY = (val: number) => {
    if (yMax <= yMin) return chartHeight - padding.bottom;
    return chartHeight - padding.bottom - ((val - yMin) / (yMax - yMin)) * (chartHeight - padding.top - padding.bottom);
  };

  const pointsPath = currentDataset.map((d, i) => `${i === 0 ? 'M' : 'L'} ${getX(d.xVal)} ${getY(d.yVal)}`).join(' ');

  return (
    <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4 space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-neutral-800/80 pb-2">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-cyan-400" />
          <span className="text-sm font-medium text-neutral-200">
            Aperture Analysis at Pixel ({aperture.x}, {aperture.y})
          </span>
          <span className="text-[10px] bg-neutral-800 text-neutral-400 px-1.5 py-0.5 rounded font-mono">
            r = 2.5 px
          </span>
        </div>

        <div className="flex items-center gap-3">
          {/* Tab buttons */}
          <div className="flex rounded-md bg-neutral-950 p-0.5 border border-neutral-800 text-xs">
            <button
              onClick={() => setActiveTab('lightcurve')}
              className={`flex items-center gap-1 px-2.5 py-1 rounded transition ${
                activeTab === 'lightcurve'
                  ? 'bg-cyan-500 text-neutral-950 font-medium'
                  : 'text-neutral-400 hover:text-neutral-200'
              }`}
            >
              <LineChart className="w-3 h-3" /> Light Curve
            </button>
            <button
              onClick={() => setActiveTab('spectrum')}
              className={`flex items-center gap-1 px-2.5 py-1 rounded transition ${
                activeTab === 'spectrum'
                  ? 'bg-cyan-500 text-neutral-950 font-medium'
                  : 'text-neutral-400 hover:text-neutral-200'
              }`}
            >
              <Radio className="w-3 h-3" /> Spectrum
            </button>
          </div>

          <button
            onClick={onClose}
            className="p-1 rounded text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800 transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* SVG Chart */}
      <div className="relative bg-neutral-950 rounded-lg border border-neutral-800/80 p-2 overflow-x-auto">
        <svg
          viewBox={`0 0 ${chartWidth} ${chartHeight}`}
          className="w-full h-[180px] overflow-visible select-none"
        >
          {/* Grid lines */}
          <line
            x1={padding.left}
            y1={padding.top}
            x2={padding.left}
            y2={chartHeight - padding.bottom}
            stroke="#262626"
            strokeWidth="1"
          />
          <line
            x1={padding.left}
            y1={chartHeight - padding.bottom}
            x2={chartWidth - padding.right}
            y2={chartHeight - padding.bottom}
            stroke="#262626"
            strokeWidth="1"
          />

          {/* Y Axis ticks */}
          <text
            x={padding.left - 6}
            y={padding.top + 5}
            textAnchor="end"
            fill="#737373"
            fontSize="9"
            fontFamily="monospace"
          >
            {yMax.toFixed(1)}
          </text>
          <text
            x={padding.left - 6}
            y={chartHeight - padding.bottom}
            textAnchor="end"
            fill="#737373"
            fontSize="9"
            fontFamily="monospace"
          >
            {yMin.toFixed(1)}
          </text>

          {/* Connecting Line */}
          {currentDataset.length > 1 && (
            <path
              d={pointsPath}
              fill="none"
              stroke="#06b6d4"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          )}

          {/* Data Points */}
          {currentDataset.map((d, idx) => {
            const cx = getX(d.xVal);
            const cy = getY(d.yVal);
            const isHovered = hoveredIndex === idx;

            return (
              <g key={idx}>
                <circle
                  cx={cx}
                  cy={cy}
                  r={isHovered ? 5 : 3.5}
                  fill={isHovered ? '#38bdf8' : '#06b6d4'}
                  stroke="#09090b"
                  strokeWidth="1.5"
                  className="cursor-pointer transition-all"
                  onMouseEnter={() => setHoveredIndex(idx)}
                  onMouseLeave={() => setHoveredIndex(null)}
                />

                {/* X Axis Tick Labels */}
                <text
                  x={cx}
                  y={chartHeight - padding.bottom + 14}
                  textAnchor="middle"
                  fill="#737373"
                  fontSize="8"
                  fontFamily="monospace"
                >
                  {activeTab === 'lightcurve' ? d.xVal.toFixed(0) : `${d.xVal.toFixed(2)}µm`}
                </text>
              </g>
            );
          })}
        </svg>

        {/* Hover Readout Tooltip */}
        {hoveredIndex !== null && currentDataset[hoveredIndex] && (
          <div className="absolute top-3 right-3 bg-neutral-900/90 border border-neutral-700 px-2.5 py-1 rounded text-xs font-mono text-cyan-300">
            {currentDataset[hoveredIndex].label} &rarr; Flux:{' '}
            <strong className="text-white">{currentDataset[hoveredIndex].yVal}</strong>
          </div>
        )}
      </div>

      <div className="flex items-center justify-between text-[11px] text-neutral-500 font-mono">
        <span>
          X Axis: {activeTab === 'lightcurve' ? 'Modified Julian Date (MJD)' : 'Wavelength (µm)'}
        </span>
        <span>Y Axis: Aperture Mean Flux</span>
      </div>
    </div>
  );
};
