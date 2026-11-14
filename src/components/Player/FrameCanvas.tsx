import React, { useEffect, useRef, useState, useCallback } from 'react';
import type { SpherexFrame } from '../../types/spherex';
import type { StretchParams } from '../../utils/stretch';
import { renderFluxToCanvas } from '../../utils/stretch';
import { ZoomIn, ZoomOut, RotateCcw, Crosshair } from 'lucide-react';

interface FrameCanvasProps {
  frame: SpherexFrame;
  stretch: StretchParams;
  isSampleData?: boolean;
}

export const FrameCanvas: React.FC<FrameCanvasProps> = ({
  frame,
  stretch,
  isSampleData = false,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  // Pan & Zoom state
  const [zoom, setZoom] = useState<number>(6.0); // Default 6x zoom for small cutouts
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [dragStart, setDragStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 });

  // Cursor inspection
  const [hoverPixel, setHoverPixel] = useState<{ x: number; y: number; flux: number } | null>(null);
  const [showReticle, setShowReticle] = useState<boolean>(true);

  // Draw frame to canvas whenever frame or stretch changes
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    if (canvas.width !== frame.width || canvas.height !== frame.height) {
      canvas.width = frame.width;
      canvas.height = frame.height;
    }

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const imgData = ctx.createImageData(frame.width, frame.height);
    renderFluxToCanvas(frame.flux, frame.width, frame.height, imgData, stretch);
    ctx.putImageData(imgData, 0, 0);
  }, [frame, stretch]);

  // Handle Wheel Zoom
  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    setZoom((prev) => {
      const delta = e.deltaY < 0 ? 1.2 : 0.8;
      const next = prev * delta;
      return Math.min(25.0, Math.max(1.0, next));
    });
  }, []);

  // Handle Drag Panning
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button !== 0) return; // Left click only
    setIsDragging(true);
    setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
  }, [pan]);

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (isDragging) {
        setPan({
          x: e.clientX - dragStart.x,
          y: e.clientY - dragStart.y,
        });
      }

      // Compute hovered pixel in image coordinates
      const canvas = canvasRef.current;
      if (!canvas) return;
      const rect = canvas.getBoundingClientRect();
      const clientX = e.clientX - rect.left;
      const clientY = e.clientY - rect.top;

      const px = Math.floor((clientX / rect.width) * frame.width);
      const py = Math.floor((clientY / rect.height) * frame.height);

      if (px >= 0 && px < frame.width && py >= 0 && py < frame.height) {
        const fluxVal = frame.flux[py * frame.width + px];
        setHoverPixel({ x: px, y: py, flux: fluxVal });
      } else {
        setHoverPixel(null);
      }
    },
    [isDragging, dragStart, frame]
  );

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  const handleResetView = useCallback(() => {
    setZoom(6.0);
    setPan({ x: 0, y: 0 });
  }, []);

  return (
    <div
      ref={containerRef}
      className="relative w-full h-[480px] bg-neutral-900 border border-neutral-800 rounded-lg overflow-hidden flex items-center justify-center select-none"
      onWheel={handleWheel}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={() => {
        setIsDragging(false);
        setHoverPixel(null);
      }}
      style={{ cursor: isDragging ? 'grabbing' : 'crosshair' }}
    >
      {/* Sample Data Warning Banner */}
      {isSampleData && (
        <div className="absolute top-3 left-3 z-20 bg-amber-500/20 border border-amber-500/50 text-amber-300 text-xs px-2.5 py-1 rounded font-mono">
          SAMPLE FAKE DATA: MOVING DOT (NOT REAL OBSERVATION)
        </div>
      )}

      {/* Frame Metadata HUD (Top Right) */}
      <div className="absolute top-3 right-3 z-20 bg-neutral-950/80 backdrop-blur border border-neutral-800 text-neutral-300 text-xs px-3 py-2 rounded font-mono space-y-1">
        <div className="flex justify-between gap-4">
          <span className="text-neutral-500">Date:</span>
          <span className="text-neutral-200">MJD {frame.mjd.toFixed(2)} ({frame.dateUtc})</span>
        </div>
        <div className="flex justify-between gap-4">
          <span className="text-neutral-500">Wavelength:</span>
          <span className="text-cyan-400 font-semibold">{frame.wavelengthMicrons.toFixed(2)} µm</span>
        </div>
        <div className="flex justify-between gap-4">
          <span className="text-neutral-500">Detector:</span>
          <span className="text-neutral-200">{frame.band}</span>
        </div>
        <div className="flex justify-between gap-4">
          <span className="text-neutral-500">Dimensions:</span>
          <span className="text-neutral-200">{frame.width} × {frame.height} px</span>
        </div>
      </div>

      {/* Pixel Inspector HUD (Bottom Left) */}
      <div className="absolute bottom-3 left-3 z-20 bg-neutral-950/80 backdrop-blur border border-neutral-800 text-neutral-300 text-xs px-3 py-1.5 rounded font-mono flex items-center gap-3">
        {hoverPixel ? (
          <>
            <span>X: <strong className="text-neutral-100">{hoverPixel.x}</strong></span>
            <span>Y: <strong className="text-neutral-100">{hoverPixel.y}</strong></span>
            <span>Flux: <strong className="text-cyan-400">{hoverPixel.flux.toFixed(2)}</strong></span>
          </>
        ) : (
          <span className="text-neutral-500">Hover canvas to inspect flux</span>
        )}
      </div>

      {/* Viewport Zoom / Reset Controls (Bottom Right) */}
      <div className="absolute bottom-3 right-3 z-20 flex items-center gap-1.5 bg-neutral-950/80 backdrop-blur border border-neutral-800 p-1 rounded">
        <button
          onClick={() => setShowReticle((prev) => !prev)}
          title="Toggle Center Reticle"
          className={`p-1.5 rounded text-xs transition ${
            showReticle ? 'bg-cyan-500/20 text-cyan-300' : 'text-neutral-400 hover:text-neutral-200'
          }`}
        >
          <Crosshair className="w-4 h-4" />
        </button>
        <button
          onClick={() => setZoom((z) => Math.min(25.0, z * 1.25))}
          title="Zoom In"
          className="p-1.5 rounded text-neutral-400 hover:text-neutral-100 hover:bg-neutral-800 transition"
        >
          <ZoomIn className="w-4 h-4" />
        </button>
        <button
          onClick={() => setZoom((z) => Math.max(1.0, z * 0.8))}
          title="Zoom Out"
          className="p-1.5 rounded text-neutral-400 hover:text-neutral-100 hover:bg-neutral-800 transition"
        >
          <ZoomOut className="w-4 h-4" />
        </button>
        <button
          onClick={handleResetView}
          title="Reset Zoom & Pan"
          className="p-1.5 rounded text-neutral-400 hover:text-neutral-100 hover:bg-neutral-800 transition"
        >
          <RotateCcw className="w-4 h-4" />
        </button>
        <span className="text-xs text-neutral-500 px-1 font-mono">{zoom.toFixed(1)}×</span>
      </div>

      {/* Main Pixel Canvas */}
      <div
        style={{
          transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
          transformOrigin: 'center center',
          transition: isDragging ? 'none' : 'transform 0.05s ease-out',
        }}
        className="relative"
      >
        <canvas
          ref={canvasRef}
          className="border border-neutral-700/60 shadow-2xl block"
          style={{
            imageRendering: 'pixelated',
          }}
        />

        {/* Center Target Reticle */}
        {showReticle && (
          <div
            className="absolute pointer-events-none inset-0 flex items-center justify-center"
            style={{ transform: 'scale(1)' }}
          >
            <div className="w-3 h-3 border border-red-500/80 rounded-full" />
            <div className="absolute w-5 h-[1px] bg-red-500/60" />
            <div className="absolute h-5 w-[1px] bg-red-500/60" />
          </div>
        )}
      </div>
    </div>
  );
};
