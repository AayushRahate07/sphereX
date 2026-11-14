import React, { useState, useMemo } from 'react';
import type { SpherexFrame } from '../../types/spherex';
import { computeLightCurve, computeSpectrum } from '../../analysis';
import {
  LineChart,
  Radio,
  Crosshair,
  CircleDot,
  Info,
  RotateCcw,
} from 'lucide-react';

interface ApertureAnalysisTabProps {
  selectedAperture: { x: number; y: number } | null;
  onSelectAperture: (x: number, y: number) => void;
  onClearAperture: () => void;
  frames: SpherexFrame[];
  activeFrame: SpherexFrame | null;
}

export const ApertureAnalysisTab: React.FC<ApertureAnalysisTabProps> = ({
  selectedAperture,
  onSelectAperture,
  onClearAperture,
  frames,
  activeFrame,
}) => {
  const [plotMode, setPlotMode] = useState<'lightcurve' | 'spectrum'>('lightcurve');
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  // Manual pixel input state
  const defaultCenter = useMemo(() => {
    if (!activeFrame) return { x: 18, y: 18 };
    return {
      x: Math.floor(activeFrame.width / 2),
      y: Math.floor(activeFrame.height / 2),
    };
  }, [activeFrame]);

  const [inputX, setInputX] = useState<string>(
    selectedAperture ? selectedAperture.x.toString() : defaultCenter.x.toString()
  );
  const [inputY, setInputY] = useState<string>(
    selectedAperture ? selectedAperture.y.toString() : defaultCenter.y.toString()
  );

  // Keep manual inputs synced if user clicks canvas
  React.useEffect(() => {
    if (selectedAperture) {
      setInputX(selectedAperture.x.toString());
      setInputY(selectedAperture.y.toString());
    }
  }, [selectedAperture]);

  // Compute multi-epoch light curve using Member 3's algorithm
  const lightCurveData = useMemo(() => {
    if (!selectedAperture || frames.length === 0) return [];
    const result = computeLightCurve(frames, selectedAperture.x, selectedAperture.y);
    if (!result) return [];

    return result.map((pt, idx) => ({
      mjd: pt.mjd,
      flux: pt.flux,
      wavelength: frames[idx]?.wavelengthMicrons ?? 0,
      date: frames[idx]?.dateUtc ?? '',
    }));
  }, [selectedAperture, frames]);

  // Compute multi-wavelength spectrum
  const spectrumData = useMemo(() => {
    if (!selectedAperture || frames.length === 0) return [];
    const result = computeSpectrum(frames, selectedAperture.x, selectedAperture.y);
    if (!result) return [];
    return result;
  }, [selectedAperture, frames]);

  // Current frame photometry details for the selected pixel
  const activeMetrics = useMemo(() => {
    if (!selectedAperture || !activeFrame) return null;

    const width = activeFrame.width;
    const height = activeFrame.height;
    const px = Math.round(selectedAperture.x);
    const py = Math.round(selectedAperture.y);

    if (px < 0 || px >= width || py < 0 || py >= height) return null;

    const rawPixelFlux = activeFrame.flux[py * width + px];

    // 2.5 px circular aperture & 3.5-5.5 px annulus
    const rApSq = 2.5 * 2.5;
    const rAnnInSq = 3.5 * 3.5;
    const rAnnOutSq = 5.5 * 5.5;

    let apSum = 0;
    let apCount = 0;
    let annSum = 0;
    let annCount = 0;

    for (let dy = -6; dy <= 6; dy++) {
      const cy = py + dy;
      if (cy < 0 || cy >= height) continue;
      for (let dx = -6; dx <= 6; dx++) {
        const cx = px + dx;
        if (cx < 0 || cx >= width) continue;

        const distSq = dx * dx + dy * dy;
        const val = activeFrame.flux[cy * width + cx];

        if (distSq <= rApSq) {
          apSum += val;
          apCount++;
        } else if (distSq >= rAnnInSq && distSq <= rAnnOutSq) {
          annSum += val;
          annCount++;
        }
      }
    }

    const bkgPerPixel = annCount > 0 ? annSum / annCount : 0;
    const netFlux = apSum - bkgPerPixel * apCount;

    return {
      rawPixelFlux,
      netFlux: Math.max(0, netFlux),
      bkgPerPixel,
      apCount,
      annCount,
    };
  }, [selectedAperture, activeFrame]);

  const handleApplyCoordinates = (e: React.FormEvent) => {
    e.preventDefault();
    const x = parseInt(inputX, 10);
    const y = parseInt(inputY, 10);
    if (!isNaN(x) && !isNaN(y) && activeFrame) {
      const clampedX = Math.max(0, Math.min(activeFrame.width - 1, x));
      const clampedY = Math.max(0, Math.min(activeFrame.height - 1, y));
      onSelectAperture(clampedX, clampedY);
    }
  };

  // SVG Chart Dimensions
  const chartWidth = 340;
  const chartHeight = 150;
  const padding = { top: 18, right: 18, bottom: 28, left: 40 };

  const currentDataset = useMemo(() => {
    if (plotMode === 'lightcurve') {
      return lightCurveData.map((d) => ({
        xVal: d.mjd,
        yVal: d.flux,
        label: `MJD ${d.mjd.toFixed(1)} (${d.date})`,
        sublabel: `${d.flux.toFixed(2)} MJy/sr`,
      }));
    } else {
      return spectrumData.map((d) => ({
        xVal: d.wavelengthMicrons,
        yVal: d.flux,
        label: `${d.wavelengthMicrons.toFixed(2)} µm`,
        sublabel: `${d.flux.toFixed(2)} MJy/sr`,
      }));
    }
  }, [plotMode, lightCurveData, spectrumData]);

  const xMin = currentDataset.length > 0 ? Math.min(...currentDataset.map((d) => d.xVal)) : 0;
  const xMax = currentDataset.length > 0 ? Math.max(...currentDataset.map((d) => d.xVal)) : 1;
  const rawYMin = currentDataset.length > 0 ? Math.min(...currentDataset.map((d) => d.yVal)) : 0;
  const rawYMax = currentDataset.length > 0 ? Math.max(...currentDataset.map((d) => d.yVal)) : 10;
  const yMin = Math.max(0, rawYMin * 0.9);
  const yMax = Math.max(rawYMax * 1.1, yMin + 1.0);

  const getX = (val: number) => {
    if (xMax <= xMin) return padding.left;
    return padding.left + ((val - xMin) / (xMax - xMin)) * (chartWidth - padding.left - padding.right);
  };

  const getY = (val: number) => {
    if (yMax <= yMin) return chartHeight - padding.bottom;
    return (
      chartHeight -
      padding.bottom -
      ((val - yMin) / (yMax - yMin)) * (chartHeight - padding.top - padding.bottom)
    );
  };

  const pointsPath =
    currentDataset.length > 0
      ? currentDataset.map((d, i) => `${i === 0 ? 'M' : 'L'} ${getX(d.xVal)} ${getY(d.yVal)}`).join(' ')
      : '';

  const areaPath =
    currentDataset.length > 0
      ? `${pointsPath} L ${getX(currentDataset[currentDataset.length - 1].xVal)} ${
          chartHeight - padding.bottom
        } L ${getX(currentDataset[0].xVal)} ${chartHeight - padding.bottom} Z`
      : '';

  return (
    <div className="space-y-3">
      {/* 1. Header & Pixel Coordinate Selection */}
      <div className="p-3 bg-neutral-950/60 rounded-xl border border-neutral-800/80 space-y-2.5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5 font-medium text-xs text-neutral-200">
            <CircleDot className="w-4 h-4 text-cyan-400" />
            <span>Aperture Target at Pixel</span>
          </div>

          {selectedAperture && (
            <button
              onClick={onClearAperture}
              className="text-[11px] text-neutral-400 hover:text-rose-400 flex items-center gap-1 transition"
              title="Clear Aperture Selection"
            >
              <RotateCcw className="w-3 h-3" />
              <span>Clear</span>
            </button>
          )}
        </div>

        {/* Selected Pixel Badge or Prompt */}
        {selectedAperture ? (
          <div className="flex items-center justify-between p-2 rounded-lg bg-neutral-900 border border-neutral-800 text-xs">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
              <span className="font-mono text-cyan-300 font-semibold">
                Pixel (X: {selectedAperture.x}, Y: {selectedAperture.y})
              </span>
            </div>
            <span className="text-[10px] text-neutral-400 font-mono">r = 2.5 px</span>
          </div>
        ) : (
          <div className="p-2.5 rounded-lg bg-neutral-900/60 border border-neutral-800/60 text-xs text-neutral-400 space-y-2">
            <p className="leading-relaxed text-[11px]">
              Click any star or pixel on the viewer image to extract its time-series light curve and infrared spectrum.
            </p>
            <button
              type="button"
              onClick={() => onSelectAperture(defaultCenter.x, defaultCenter.y)}
              className="w-full py-1.5 px-3 bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-300 border border-cyan-500/40 rounded-lg text-xs font-medium flex items-center justify-center gap-1.5 transition"
            >
              <Crosshair className="w-3.5 h-3.5" />
              <span>Inspect Center Target ({defaultCenter.x}, {defaultCenter.y})</span>
            </button>
          </div>
        )}

        {/* Manual Pixel Coordinate Form */}
        <form onSubmit={handleApplyCoordinates} className="grid grid-cols-5 gap-2 pt-1 items-center">
          <div className="col-span-2 flex items-center gap-1 bg-neutral-900 border border-neutral-800 rounded px-2 py-1">
            <span className="text-[10px] text-neutral-500 font-mono">X:</span>
            <input
              type="number"
              value={inputX}
              onChange={(e) => setInputX(e.target.value)}
              className="w-full bg-transparent font-mono text-xs text-neutral-200 focus:outline-none"
              placeholder="18"
            />
          </div>
          <div className="col-span-2 flex items-center gap-1 bg-neutral-900 border border-neutral-800 rounded px-2 py-1">
            <span className="text-[10px] text-neutral-500 font-mono">Y:</span>
            <input
              type="number"
              value={inputY}
              onChange={(e) => setInputY(e.target.value)}
              className="w-full bg-transparent font-mono text-xs text-neutral-200 focus:outline-none"
              placeholder="18"
            />
          </div>
          <button
            type="submit"
            className="col-span-1 py-1 bg-neutral-800 hover:bg-neutral-700 text-neutral-200 text-xs rounded font-medium transition text-center"
          >
            Go
          </button>
        </form>
      </div>

      {/* 2. Real-Time Photometry Metrics */}
      {selectedAperture && activeMetrics && activeFrame && (
        <div className="p-3 bg-neutral-950/60 rounded-xl border border-neutral-800/80 space-y-2 text-xs">
          <div className="text-neutral-300 font-medium text-[11px] flex items-center justify-between">
            <span>Photometry on Current Epoch</span>
            <span className="text-[10px] text-cyan-400 font-mono">
              {activeFrame.wavelengthMicrons.toFixed(2)} µm
            </span>
          </div>

          <div className="grid grid-cols-2 gap-2 text-[11px] font-mono">
            <div className="bg-neutral-900/80 border border-neutral-800 p-2 rounded-lg">
              <span className="text-neutral-500 block text-[10px]">Net Aperture Flux</span>
              <span className="text-cyan-300 text-sm font-bold font-mono">
                {activeMetrics.netFlux.toFixed(2)}
              </span>
              <span className="text-[9px] text-neutral-500 block">MJy/sr (bkg-sub)</span>
            </div>

            <div className="bg-neutral-900/80 border border-neutral-800 p-2 rounded-lg">
              <span className="text-neutral-500 block text-[10px]">Center Peak Flux</span>
              <span className="text-neutral-200 text-sm font-bold font-mono">
                {activeMetrics.rawPixelFlux.toFixed(2)}
              </span>
              <span className="text-[9px] text-neutral-500 block">MJy/sr (pixel)</span>
            </div>
          </div>
        </div>
      )}

      {/* 3. Interactive Chart & Sub-Tab Switcher */}
      {selectedAperture && currentDataset.length > 0 && (
        <div className="p-3 bg-neutral-950/60 rounded-xl border border-neutral-800/80 space-y-2.5">
          <div className="flex items-center justify-between">
            <div className="flex rounded-md bg-neutral-900 p-0.5 border border-neutral-800 text-xs">
              <button
                type="button"
                onClick={() => setPlotMode('lightcurve')}
                className={`flex items-center gap-1 px-2.5 py-1 rounded transition text-[11px] ${
                  plotMode === 'lightcurve'
                    ? 'bg-cyan-500 text-neutral-950 font-semibold'
                    : 'text-neutral-400 hover:text-neutral-200'
                }`}
              >
                <LineChart className="w-3 h-3" /> Light Curve
              </button>
              <button
                type="button"
                onClick={() => setPlotMode('spectrum')}
                className={`flex items-center gap-1 px-2.5 py-1 rounded transition text-[11px] ${
                  plotMode === 'spectrum'
                    ? 'bg-cyan-500 text-neutral-950 font-semibold'
                    : 'text-neutral-400 hover:text-neutral-200'
                }`}
              >
                <Radio className="w-3 h-3" /> Spectrum
              </button>
            </div>

            <span className="text-[10px] text-neutral-500 font-mono">
              {currentDataset.length} points
            </span>
          </div>

          {/* SVG Canvas Plot */}
          <div className="relative bg-neutral-900/90 rounded-lg border border-neutral-800 p-2 select-none overflow-hidden">
            <svg
              viewBox={`0 0 ${chartWidth} ${chartHeight}`}
              className="w-full h-[150px] overflow-visible"
            >
              <defs>
                <linearGradient id="apertureGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#06b6d4" stopOpacity="0.3" />
                  <stop offset="100%" stopColor="#06b6d4" stopOpacity="0.0" />
                </linearGradient>
              </defs>

              {/* Grid Lines */}
              <line
                x1={padding.left}
                y1={padding.top}
                x2={padding.left}
                y2={chartHeight - padding.bottom}
                stroke="#333333"
                strokeWidth="1"
              />
              <line
                x1={padding.left}
                y1={chartHeight - padding.bottom}
                x2={chartWidth - padding.right}
                y2={chartHeight - padding.bottom}
                stroke="#333333"
                strokeWidth="1"
              />

              {/* Y Axis Labels */}
              <text
                x={padding.left - 6}
                y={padding.top + 4}
                textAnchor="end"
                className="fill-neutral-500 text-[9px] font-mono"
              >
                {yMax.toFixed(1)}
              </text>
              <text
                x={padding.left - 6}
                y={chartHeight - padding.bottom}
                textAnchor="end"
                className="fill-neutral-500 text-[9px] font-mono"
              >
                {yMin.toFixed(1)}
              </text>

              {/* X Axis Labels */}
              <text
                x={padding.left}
                y={chartHeight - 10}
                textAnchor="start"
                className="fill-neutral-500 text-[9px] font-mono"
              >
                {plotMode === 'lightcurve' ? `MJD ${xMin.toFixed(0)}` : `${xMin.toFixed(1)} µm`}
              </text>
              <text
                x={chartWidth - padding.right}
                y={chartHeight - 10}
                textAnchor="end"
                className="fill-neutral-500 text-[9px] font-mono"
              >
                {plotMode === 'lightcurve' ? `MJD ${xMax.toFixed(0)}` : `${xMax.toFixed(1)} µm`}
              </text>

              {/* Area fill */}
              {areaPath && <path d={areaPath} fill="url(#apertureGradient)" />}

              {/* Connecting Line */}
              {pointsPath && (
                <path
                  d={pointsPath}
                  fill="none"
                  stroke="#22d3ee"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              )}

              {/* Data Points */}
              {currentDataset.map((d, i) => {
                const cx = getX(d.xVal);
                const cy = getY(d.yVal);
                const isHovered = hoveredIndex === i;

                return (
                  <g key={i}>
                    <circle
                      cx={cx}
                      cy={cy}
                      r={isHovered ? 6 : 3.5}
                      className={`cursor-pointer transition-all duration-150 ${
                        isHovered ? 'fill-cyan-300 stroke-white stroke-2' : 'fill-cyan-400 stroke-neutral-900 stroke-1'
                      }`}
                      onMouseEnter={() => setHoveredIndex(i)}
                      onMouseLeave={() => setHoveredIndex(null)}
                    />
                  </g>
                );
              })}
            </svg>

            {/* Hover Tooltip Readout */}
            {hoveredIndex !== null && currentDataset[hoveredIndex] && (
              <div className="absolute top-2 right-2 bg-neutral-950/95 border border-cyan-500/40 px-2 py-1 rounded text-[10px] font-mono text-cyan-300 shadow-md">
                <div>{currentDataset[hoveredIndex].label}</div>
                <div className="text-white font-bold">{currentDataset[hoveredIndex].sublabel}</div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 4. Multi-Epoch Observation Table */}
      {selectedAperture && lightCurveData.length > 0 && (
        <div className="p-3 bg-neutral-950/60 rounded-xl border border-neutral-800/80 space-y-2 text-xs">
          <div className="flex items-center justify-between text-neutral-300 font-medium text-[11px]">
            <span>Epoch Measurements</span>
            <span className="text-[10px] text-neutral-500 font-mono">Net Flux</span>
          </div>

          <div className="max-h-36 overflow-y-auto space-y-1 font-mono text-[10px]">
            {lightCurveData.map((d, idx) => (
              <div
                key={idx}
                className="flex items-center justify-between p-1.5 rounded bg-neutral-900/60 border border-neutral-800/40 text-neutral-300"
              >
                <div>
                  <span className="text-cyan-400 font-semibold mr-1.5">E{idx + 1}</span>
                  <span className="text-neutral-400">{d.date}</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-neutral-500">{d.wavelength.toFixed(2)} µm</span>
                  <span className="text-neutral-100 font-bold">{d.flux.toFixed(2)} MJy/sr</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 5. Educational Context Box */}
      <div className="p-3 bg-cyan-950/20 border border-cyan-500/20 rounded-xl text-neutral-300 text-[11px] leading-relaxed space-y-1">
        <div className="flex items-center gap-1.5 font-medium text-cyan-300 text-xs">
          <Info className="w-3.5 h-3.5 text-cyan-400" />
          <span>Aperture Photometry Explained</span>
        </div>
        <p className="text-neutral-400">
          Measures all infrared light inside a target circle (radius = 2.5 px) and subtracts background noise from an outer ring (radius 3.5–5.5 px). This isolates faint moving objects and stars from cosmic zodiacal dust.
        </p>
      </div>
    </div>
  );
};
