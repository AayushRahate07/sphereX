import React, { useEffect, useRef, useState, useCallback } from 'react';
import type { SpherexFrame, RgbCompositeData } from '../../types/spherex';
import type { StretchParams } from '../../utils/stretch';
import { renderFluxToCanvas, renderRgbToCanvas } from '../../utils/stretch';
import { computeFitScale } from '../../utils/zoom';
import { ZoomIn, ZoomOut, RotateCcw, Crosshair, Blend, Grid } from 'lucide-react';

interface FrameCanvasProps {
  frame?: SpherexFrame;
  stretch: StretchParams;
  isSampleData?: boolean;
  aperture?: { x: number; y: number } | null;
  onSelectAperture?: (x: number, y: number) => void;
  rgbData?: RgbCompositeData | null;
  redStretch?: StretchParams;
  greenStretch?: StretchParams;
  blueStretch?: StretchParams;
}

export const FrameCanvas: React.FC<FrameCanvasProps> = ({
  frame,
  stretch,
  isSampleData = false,
  aperture,
  onSelectAperture,
  rgbData,
  redStretch,
  greenStretch,
  blueStretch,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  const width = rgbData ? rgbData.width : (frame?.width ?? 29);
  const height = rgbData ? rgbData.height : (frame?.height ?? 29);

  // Measure usable container dimensions
  const [containerDims, setContainerDims] = useState<{ width: number; height: number }>({
    width: 750,
    height: 560,
  });

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const updateDims = () => {
      const rect = container.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0) {
        setContainerDims({ width: rect.width, height: rect.height });
      }
    };

    updateDims();

    if (typeof ResizeObserver !== 'undefined') {
      const observer = new ResizeObserver((entries) => {
        for (const entry of entries) {
          const { width: w, height: h } = entry.contentRect;
          if (w > 0 && h > 0) {
            setContainerDims({ width: w, height: h });
          }
        }
      });
      observer.observe(container);
      return () => observer.disconnect();
    } else {
      window.addEventListener('resize', updateDims);
      return () => window.removeEventListener('resize', updateDims);
    }
  }, []);

  const fitScale = computeFitScale(width, height, containerDims.width, containerDims.height, 24);

  const baseWidth = Math.max(1, Math.round(width * fitScale));
  const baseHeight = Math.max(1, Math.round(height * fitScale));

  // User zoom multiplier: 1.0 means 100% Fit to Viewport
  const [zoom, setZoom] = useState<number>(1.0);
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [dragStart, setDragStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [dragDistance, setDragDistance] = useState<number>(0);

  // Adaptively reset to 1.0 (Fit) and center pan when image dimensions change (e.g. FOV selector change)
  const [prevDims, setPrevDims] = useState<{ w: number; h: number }>({ w: width, h: height });
  if (prevDims.w !== width || prevDims.h !== height) {
    setPrevDims({ w: width, h: height });
    setZoom(1.0);
    setPan({ x: 0, y: 0 });
  }

  // Cursor inspection
  const [hoverPixel, setHoverPixel] = useState<{
    x: number;
    y: number;
    flux?: number;
    r?: number;
    g?: number;
    b?: number;
  } | null>(null);
  const [showReticle, setShowReticle] = useState<boolean>(true);
  const [interpolation, setInterpolation] = useState<'smooth' | 'pixelated'>('smooth');

  // Draw frame or RGB composite to canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    if (canvas.width !== width || canvas.height !== height) {
      canvas.width = width;
      canvas.height = height;
    }

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const imgData = ctx.createImageData(width, height);

    if (rgbData) {
      const rStr = redStretch ?? stretch;
      const gStr = greenStretch ?? stretch;
      const bStr = blueStretch ?? stretch;
      renderRgbToCanvas(
        rgbData.channels.red.flux,
        rgbData.channels.green.flux,
        rgbData.channels.blue.flux,
        width,
        height,
        imgData,
        rStr,
        gStr,
        bStr,
        rgbData.channels.red.flags,
        rgbData.channels.green.flags,
        rgbData.channels.blue.flags
      );
    } else if (frame) {
      renderFluxToCanvas(frame.flux, width, height, imgData, stretch, frame.flags);
    }

    ctx.putImageData(imgData, 0, 0);
  }, [frame, stretch, rgbData, redStretch, greenStretch, blueStretch, width, height]);

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
        return Math.min(30.0, Math.max(0.5, next));
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
    setZoom((z) => Math.max(0.5, Number((z * 0.8).toFixed(2))));
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

      const px = Math.floor((clientX / rect.width) * width);
      const py = Math.floor((clientY / rect.height) * height);

      if (px >= 0 && px < width && py >= 0 && py < height) {
        const idx = py * width + px;
        if (rgbData) {
          setHoverPixel({
            x: px,
            y: py,
            r: rgbData.channels.red.flux[idx],
            g: rgbData.channels.green.flux[idx],
            b: rgbData.channels.blue.flux[idx],
          });
        } else if (frame) {
          setHoverPixel({ x: px, y: py, flux: frame.flux[idx] });
        }
      } else {
        setHoverPixel(null);
      }
    },
    [isDragging, dragStart, pan, width, height, rgbData, frame]
  );

  const handleMouseUp = useCallback(
    (e: React.MouseEvent) => {
      setIsDragging(false);

      // If user clicked without dragging (drag distance < 5px), treat as aperture target selection
      if (dragDistance < 5 && onSelectAperture && canvasRef.current) {
        const rect = canvasRef.current.getBoundingClientRect();
        const clientX = e.clientX - rect.left;
        const clientY = e.clientY - rect.top;

        const px = Math.floor((clientX / rect.width) * width);
        const py = Math.floor((clientY / rect.height) * height);

        if (px >= 0 && px < width && py >= 0 && py < height) {
          onSelectAperture(px, py);
        }
      }
    },
    [dragDistance, onSelectAperture, width, height]
  );

  const handleResetView = useCallback(() => {
    setZoom(1.0);
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

      {/* Frame / RGB Metadata HUD (Top Right) */}
      <div className="absolute top-3 right-3 z-20 bg-neutral-950/80 backdrop-blur border border-neutral-800 text-neutral-300 text-xs px-3 py-2 rounded font-mono space-y-1">
        {rgbData ? (
          <>
            <div className="flex justify-between gap-4">
              <span className="text-neutral-500">Mode:</span>
              <span className="text-amber-400 font-semibold">RGB False-Color IR</span>
            </div>
            <div className="flex justify-between gap-4">
              <span className="text-red-400 font-medium">R: {rgbData.channels.red.band}</span>
              <span className="text-neutral-200">{rgbData.channels.red.wavelengthMicrons.toFixed(2)} µm</span>
            </div>
            <div className="flex justify-between gap-4">
              <span className="text-green-400 font-medium">G: {rgbData.channels.green.band}</span>
              <span className="text-neutral-200">{rgbData.channels.green.wavelengthMicrons.toFixed(2)} µm</span>
            </div>
            <div className="flex justify-between gap-4">
              <span className="text-blue-400 font-medium">B: {rgbData.channels.blue.band}</span>
              <span className="text-neutral-200">{rgbData.channels.blue.wavelengthMicrons.toFixed(2)} µm</span>
            </div>
            <div className="flex justify-between gap-4 border-t border-neutral-800/60 pt-1">
              <span className="text-neutral-500">Grid:</span>
              <span className="text-neutral-200">{width} × {height} px</span>
            </div>
            <div className="flex justify-between gap-4">
              <span className="text-neutral-500">Display:</span>
              <span className="text-neutral-200" title="Display interpolation only; raw scientific flux array and WCS coordinates are strictly preserved">
                {interpolation === 'smooth' ? 'Bilinear (Smoothed)' : 'Nearest (Native)'}
              </span>
            </div>
          </>
        ) : frame ? (
          <>
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
            <div className="flex justify-between gap-4">
              <span className="text-neutral-500">Display:</span>
              <span className="text-neutral-200" title="Display interpolation only; raw scientific flux array and WCS coordinates are strictly preserved">
                {interpolation === 'smooth' ? 'Bilinear (Smoothed)' : 'Nearest (Native)'}
              </span>
            </div>
            {frame.obsId && (
              <div className="flex justify-between gap-4 border-t border-neutral-800/60 pt-1">
                <span className="text-neutral-500">Obs ID:</span>
                <span className="text-cyan-400 font-semibold">{frame.obsId}</span>
              </div>
            )}
          </>
        ) : null}
      </div>

      {/* Pixel Inspector HUD (Bottom Left) */}
      <div className="absolute bottom-3 left-3 z-20 bg-neutral-950/80 backdrop-blur border border-neutral-800 text-neutral-300 text-xs px-3 py-1.5 rounded font-mono flex items-center gap-3">
        {hoverPixel ? (
          <>
            <span>X: <strong className="text-neutral-100">{hoverPixel.x}</strong></span>
            <span>Y: <strong className="text-neutral-100">{hoverPixel.y}</strong></span>
            {hoverPixel.flux !== undefined ? (
              <span>Flux: <strong className="text-cyan-400">{hoverPixel.flux.toFixed(2)}</strong></span>
            ) : (
              <span className="flex items-center gap-2">
                <span className="text-red-400">R: <strong>{hoverPixel.r?.toFixed(2)}</strong></span>
                <span className="text-green-400">G: <strong>{hoverPixel.g?.toFixed(2)}</strong></span>
                <span className="text-blue-400">B: <strong>{hoverPixel.b?.toFixed(2)}</strong></span>
                <span className="text-neutral-500 text-[10px]">MJy/sr</span>
              </span>
            )}
            {!rgbData && (
              <span className="text-[10px] text-neutral-500 hidden sm:inline">(Click to plot light curve)</span>
            )}
          </>
        ) : (
          <span className="text-neutral-500">
            {rgbData ? 'Hover to inspect calibrated R/G/B surface brightness' : 'Click any pixel to inspect light curve & spectrum'}
          </span>
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
          onClick={() => setInterpolation((prev) => (prev === 'smooth' ? 'pixelated' : 'smooth'))}
          title={
            interpolation === 'smooth'
              ? 'Interpolation: Smooth Bilinear (Display only) - Click for Native Pixels'
              : 'Interpolation: Native Detector Pixels (Nearest Neighbor) - Click for Smooth Bilinear'
          }
          className={`p-1.5 rounded text-xs transition ${
            interpolation === 'smooth' ? 'bg-indigo-500/20 text-indigo-300' : 'text-neutral-400 hover:text-neutral-200'
          }`}
        >
          {interpolation === 'smooth' ? <Blend className="w-4 h-4" /> : <Grid className="w-4 h-4" />}
        </button>

        <button
          onClick={handleZoomOut}
          title="Zoom Out (or scroll down over canvas)"
          className="p-1.5 rounded text-neutral-300 hover:text-white hover:bg-neutral-800 transition cursor-pointer"
        >
          <ZoomOut className="w-3.5 h-3.5" />
        </button>

        <span className="text-[11px] text-neutral-300 min-w-[38px] text-center font-mono font-medium">
          {zoom === 1 ? '1.0× (Fit)' : `${zoom.toFixed(1)}×`}
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
          title="Reset Zoom & Pan (Fit to Viewport)"
          className="flex items-center gap-1 px-2 py-1 rounded text-[11px] font-medium text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800 transition cursor-pointer"
        >
          <RotateCcw className="w-3 h-3" />
          <span>Reset</span>
        </button>
      </div>

      {/* Main Pixel Canvas Container (Fits Available Viewport Area) */}
      <div
        style={{
          width: `${baseWidth}px`,
          height: `${baseHeight}px`,
          transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
          transformOrigin: 'center center',
          transition: isDragging ? 'none' : 'transform 0.05s ease-out',
        }}
        className="relative shadow-2xl shrink-0"
      >
        <canvas
          ref={canvasRef}
          className="w-full h-full border border-neutral-700/60 block"
          style={{
            imageRendering: interpolation === 'smooth' ? 'auto' : 'pixelated',
          }}
        />

        {/* Center Target Reticle */}
        {showReticle && (
          <div
            className="absolute pointer-events-none inset-0 flex items-center justify-center"
          >
            <div className="w-4 h-4 border border-red-500/90 rounded-full" />
            <div className="absolute w-6 h-[1px] bg-red-500/70" />
            <div className="absolute h-6 w-[1px] bg-red-500/70" />
          </div>
        )}

        {/* User Clicked Photometry Aperture Ring */}
        {aperture && (
          <div
            className="absolute pointer-events-none"
            style={{
              left: `${((aperture.x + 0.5) / width) * 100}%`,
              top: `${((aperture.y + 0.5) / height) * 100}%`,
              transform: 'translate(-50%, -50%)',
            }}
          >
            {/* 2.5 pixel radius (5.0 px diameter) aperture ring on image grid */}
            <div
              className="border border-cyan-400 border-dashed rounded-full animate-pulse"
              style={{
                width: `${Math.max(6, Math.round(5.0 * fitScale))}px`,
                height: `${Math.max(6, Math.round(5.0 * fitScale))}px`,
              }}
            />
          </div>
        )}
      </div>
    </div>
  );
};
