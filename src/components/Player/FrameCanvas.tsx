import React, { useEffect, useRef, useState, useCallback } from 'react';
import type { SpherexFrame } from '../../types/spherex';
import type { StretchParams } from '../../utils/stretch';
import { renderFluxToCanvas } from '../../utils/stretch';
import { ZoomIn, ZoomOut, RotateCcw, Crosshair } from 'lucide-react';

interface FrameCanvasProps {
  frame: SpherexFrame;
  stretch: StretchParams;
  isSampleData?: boolean;
  aperture?: { x: number; y: number } | null;
  onSelectAperture?: (x: number, y: number) => void;
}

export const FrameCanvas: React.FC<FrameCanvasProps> = ({
  frame,
  stretch,
  isSampleData = false,
  aperture,
  onSelectAperture,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  // Pan & Zoom state
  const [zoom, setZoom] = useState<number>(6.0); // Default 6x zoom for small cutouts
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [dragStart, setDragStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [dragDistance, setDragDistance] = useState<number>(0);

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

  // Native non-passive wheel event listener: zoom in/out only when scrolling over canvas, nothing else
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const handleNativeWheel = (e: WheelEvent) => {
      // Prevent browser page zoom, pinch zoom, and document scroll
      e.preventDefault();
      e.stopPropagation();

      // Smooth, responsive zoom calculation based on scroll delta
      const zoomSensitivity = 0.0015;
      const clampedDelta = Math.max(-100, Math.min(100, e.deltaY));
      const factor = Math.exp(-clampedDelta * zoomSensitivity);

      setZoom((prev) => {
        const next = prev * factor;
        return Math.min(30.0, Math.max(1.0, next));
      });
    };

    container.addEventListener('wheel', handleNativeWheel, { passive: false });
    return () => {
      container.removeEventListener('wheel', handleNativeWheel);
    };
  }, []);

  const handleZoomIn = useCallback(() => {
    setZoom((z) => Math.min(30.0, Number((z * 1.25).toFixed(2))));
  }, []);

  const handleZoomOut = useCallback(() => {
    setZoom((z) => Math.max(1.0, Number((z * 0.8).toFixed(2))));
  }, []);

  // Handle Drag Panning
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button !== 0) return; // Left click only
    setIsDragging(true);
    setDragDistance(0);
    setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
  }, [pan]);

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (isDragging) {
        const dx = e.clientX - dragStart.x - pan.x;
        const dy = e.clientY - dragStart.y - pan.y;
        setDragDistance((prev) => prev + Math.abs(dx) + Math.abs(dy));
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
    [isDragging, dragStart, pan, frame]
  );

  const handleMouseUp = useCallback(
    (e: React.MouseEvent) => {
      setIsDragging(false);

      // If user clicked without dragging (drag distance < 5px), treat as aperture target selection
      if (dragDistance < 5 && onSelectAperture && canvasRef.current) {
        const rect = canvasRef.current.getBoundingClientRect();
        const clientX = e.clientX - rect.left;
        const clientY = e.clientY - rect.top;

        const px = Math.floor((clientX / rect.width) * frame.width);
        const py = Math.floor((clientY / rect.height) * frame.height);

        if (px >= 0 && px < frame.width && py >= 0 && py < frame.height) {
          onSelectAperture(px, py);
        }
      }
    },
    [dragDistance, onSelectAperture, frame]
  );

  const handleResetView = useCallback(() => {
    setZoom(6.0);
    setPan({ x: 0, y: 0 });
  }, []);

  return (
    <div
      ref={containerRef}
      className="relative w-full flex-1 h-full min-h-[340px] bg-neutral-900 border border-neutral-800 rounded-xl overflow-hidden flex items-center justify-center select-none shadow-lg"
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onDoubleClick={(e) => e.preventDefault()}
      onMouseLeave={() => {
        setIsDragging(false);
        setHoverPixel(null);
      }}
      style={{ cursor: isDragging ? 'grabbing' : 'crosshair', touchAction: 'none' }}
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
        {frame.obsId && (
          <div className="flex justify-between gap-4 border-t border-neutral-800/60 pt-1">
            <span className="text-neutral-500">Obs ID:</span>
            <span className="text-cyan-400 font-semibold">{frame.obsId}</span>
          </div>
        )}
      </div>

      {/* Pixel Inspector HUD (Bottom Left) */}
      <div className="absolute bottom-3 left-3 z-20 bg-neutral-950/80 backdrop-blur border border-neutral-800 text-neutral-300 text-xs px-3 py-1.5 rounded font-mono flex items-center gap-3">
        {hoverPixel ? (
          <>
            <span>X: <strong className="text-neutral-100">{hoverPixel.x}</strong></span>
            <span>Y: <strong className="text-neutral-100">{hoverPixel.y}</strong></span>
            <span>Flux: <strong className="text-cyan-400">{hoverPixel.flux.toFixed(2)}</strong></span>
            <span className="text-[10px] text-neutral-500 hidden sm:inline">(Click to plot light curve)</span>
          </>
        ) : (
          <span className="text-neutral-500">Click any pixel to inspect light curve &amp; spectrum</span>
        )}
      </div>

      {/* Viewport Zoom & Reticle Controls (Bottom Right) */}
      <div className="absolute bottom-3 right-3 z-20 flex items-center gap-1.5 bg-neutral-950/85 backdrop-blur border border-neutral-800 px-2 py-1 rounded-lg shadow-lg">
        <button
          onClick={() => setShowReticle((prev) => !prev)}
          title="Toggle Center Reticle"
          className={`p-1.5 rounded text-xs transition ${
            showReticle ? 'bg-cyan-500/20 text-cyan-300' : 'text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800'
          }`}
        >
          <Crosshair className="w-3.5 h-3.5" />
        </button>

        <div className="h-3.5 w-px bg-neutral-800 mx-0.5" />

        <button
          onClick={handleZoomOut}
          title="Zoom Out (or scroll down over canvas)"
          className="p-1.5 rounded text-neutral-300 hover:text-white hover:bg-neutral-800 transition cursor-pointer"
        >
          <ZoomOut className="w-3.5 h-3.5" />
        </button>

        <span className="text-[11px] text-neutral-300 min-w-[38px] text-center font-mono font-medium">
          {zoom.toFixed(1)}×
        </span>

        <button
          onClick={handleZoomIn}
          title="Zoom In (or scroll up over canvas)"
          className="p-1.5 rounded text-neutral-300 hover:text-white hover:bg-neutral-800 transition cursor-pointer"
        >
          <ZoomIn className="w-3.5 h-3.5" />
        </button>

        <div className="h-3.5 w-px bg-neutral-800 mx-0.5" />

        <button
          onClick={handleResetView}
          title="Reset Zoom to Default (6.0×)"
          className="flex items-center gap-1 px-2 py-1 rounded text-[11px] font-medium text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800 transition cursor-pointer"
        >
          <RotateCcw className="w-3 h-3" />
          <span>Reset</span>
        </button>
      </div>

      {/* Main Pixel Canvas Container */}
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

        {/* User Clicked Photometry Aperture Ring */}
        {aperture && (
          <div
            className="absolute pointer-events-none"
            style={{
              left: `${((aperture.x + 0.5) / frame.width) * 100}%`,
              top: `${((aperture.y + 0.5) / frame.height) * 100}%`,
              transform: 'translate(-50%, -50%)',
            }}
          >
            {/* 2.5 pixel radius circle on image grid */}
            <div
              className="border-2 border-cyan-400 border-dashed rounded-full animate-pulse"
              style={{
                width: `${(5.0 / frame.width) * 100 * (frame.width / 36)}px`,
                height: `${(5.0 / frame.height) * 100 * (frame.height / 36)}px`,
              }}
            />
          </div>
        )}
      </div>
    </div>
  );
};
