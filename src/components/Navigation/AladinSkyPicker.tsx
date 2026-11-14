import React, { useEffect, useRef, useState, useCallback } from 'react';
import { Globe, RefreshCw, AlertTriangle, Layers } from 'lucide-react';

declare global {
  interface Window {
    A?: any;
  }
}

interface AladinSkyPickerProps {
  ra: number;
  dec: number;
  fovDegrees: number;
  onSelectPosition: (ra: number, dec: number) => void;
  isOpen: boolean;
  onClose: () => void;
}

export const AladinSkyPicker: React.FC<AladinSkyPickerProps> = ({
  ra,
  dec,
  fovDegrees,
  onSelectPosition,
  isOpen,
  onClose,
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const aladinInstanceRef = useRef<any>(null);
  const [isAladinLoaded, setIsAladinLoaded] = useState<boolean>(false);
  const [aladinError, setAladinError] = useState<string | null>(null);
  const [currentSurvey, setCurrentSurvey] = useState<string>('P/DSS2/color');

  // Initialize Aladin Lite when panel opens
  useEffect(() => {
    if (!isOpen) return;

    let checkInterval: any;
    let attempts = 0;

    const initAladin = () => {
      if (!containerRef.current) return;

      if (window.A && window.A.aladin) {
        clearInterval(checkInterval);
        try {
          if (!aladinInstanceRef.current) {
            // Clear previous children just in case
            containerRef.current.innerHTML = '';

            const aladin = window.A.aladin(containerRef.current, {
              target: `${ra} ${dec}`,
              fov: Math.max(0.1, fovDegrees * 6),
              survey: currentSurvey,
              showReticle: true,
              showZoomControl: true,
              showFullscreenControl: false,
              showLayersControl: true,
              showGotoControl: false,
            });

            aladinInstanceRef.current = aladin;

            // Handle user clicks on the sky map
            if (aladin.on) {
              aladin.on('click', (position: any) => {
                if (position && position.ra !== undefined && position.dec !== undefined) {
                  onSelectPosition(position.ra, position.dec);
                }
              });
            }
          } else {
            aladinInstanceRef.current.gotoRaDec(ra, dec);
          }
          setIsAladinLoaded(true);
        } catch (err: any) {
          console.warn('Failed to initialize Aladin Lite:', err);
          setAladinError('Aladin Lite initialization error. Using coordinate fallback.');
        }
      } else {
        attempts++;
        if (attempts > 30) {
          // 3 seconds timeout
          clearInterval(checkInterval);
          setAladinError('Aladin Lite library could not be loaded from CDS CDN. Using offline coordinate fallback.');
        }
      }
    };

    checkInterval = setInterval(initAladin, 100);

    return () => {
      clearInterval(checkInterval);
    };
  }, [isOpen, onSelectPosition]);

  // Update Aladin position when RA/Dec changes
  useEffect(() => {
    if (aladinInstanceRef.current && isAladinLoaded) {
      try {
        aladinInstanceRef.current.gotoRaDec(ra, dec);
      } catch {
        // ignore
      }
    }
  }, [ra, dec, isAladinLoaded]);

  // Handle survey change
  const handleSurveyChange = useCallback((newSurvey: string) => {
    setCurrentSurvey(newSurvey);
    if (aladinInstanceRef.current && aladinInstanceRef.current.setImageSurvey) {
      aladinInstanceRef.current.setImageSurvey(newSurvey);
    }
  }, []);

  if (!isOpen) return null;

  return (
    <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4 space-y-3">
      <div className="flex items-center justify-between border-b border-neutral-800 pb-2">
        <div className="flex items-center gap-2 text-sm font-medium text-neutral-200">
          <Globe className="w-4 h-4 text-cyan-400" />
          <span>Aladin Lite All-Sky Target Picker</span>
        </div>

        <div className="flex items-center gap-2">
          {/* Survey switch */}
          <div className="flex items-center gap-1 text-xs">
            <Layers className="w-3.5 h-3.5 text-neutral-400" />
            <select
              value={currentSurvey}
              onChange={(e) => handleSurveyChange(e.target.value)}
              className="bg-neutral-950 border border-neutral-800 rounded px-2 py-0.5 text-xs text-neutral-300 focus:outline-none focus:border-cyan-500"
            >
              <option value="P/DSS2/color">DSS2 Color (Optical)</option>
              <option value="P/2MASS/color">2MASS (Near-IR)</option>
              <option value="P/allWISE/color">AllWISE (Mid-IR)</option>
            </select>
          </div>

          <button
            onClick={onClose}
            className="text-xs text-neutral-400 hover:text-neutral-200 px-2 py-1 rounded bg-neutral-800"
          >
            Hide Map
          </button>
        </div>
      </div>

      <p className="text-xs text-neutral-400">
        Click anywhere on the sky map to center the SPHEREx cutouts on that position.
      </p>

      {/* Aladin Container */}
      <div className="relative w-full h-[360px] bg-neutral-950 rounded-lg overflow-hidden border border-neutral-800">
        {aladinError ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center p-6 text-center text-xs text-neutral-400 space-y-3">
            <AlertTriangle className="w-6 h-6 text-amber-400" />
            <span>{aladinError}</span>
            <span className="text-[11px] text-neutral-500 max-w-sm">
              You can still enter any RA/Dec coordinates or choose from the challenge target presets above.
            </span>
          </div>
        ) : (
          <>
            <div
              ref={containerRef}
              id="aladin-lite-div"
              className="w-full h-full"
              style={{ minHeight: '360px' }}
            />
            {!isAladinLoaded && (
              <div className="absolute inset-0 bg-neutral-950/80 flex items-center justify-center gap-2 text-xs text-neutral-400 font-mono">
                <RefreshCw className="w-4 h-4 animate-spin text-cyan-400" />
                Connecting to CDS Aladin Lite...
              </div>
            )}
          </>
        )}
      </div>

      <div className="flex items-center justify-between text-[11px] text-neutral-500 font-mono">
        <span>Current Reticle: RA {ra.toFixed(4)}°, Dec {dec.toFixed(4)}°</span>
        <span>SPHEREx FOV: {fovDegrees}°</span>
      </div>
    </div>
  );
};
