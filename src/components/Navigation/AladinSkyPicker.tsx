import React, { useEffect, useRef, useState, useCallback } from 'react';
import { RefreshCw, AlertTriangle, Layers } from 'lucide-react';
import A from 'aladin-lite';

interface AladinSkyPickerProps {
  ra: number;
  dec: number;
  fovDegrees: number;
  onSelectPosition: (ra: number, dec: number) => void;
  isOpen: boolean;
  onClose?: () => void;
}

export const AladinSkyPicker: React.FC<AladinSkyPickerProps> = ({
  ra,
  dec,
  fovDegrees,
  onSelectPosition,
  isOpen,
  onClose: _onClose,
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const aladinInstanceRef = useRef<any>(null);
  const onSelectRef = useRef(onSelectPosition);
  const [isAladinLoaded, setIsAladinLoaded] = useState<boolean>(false);
  const [aladinError, setAladinError] = useState<string | null>(null);
  const [currentSurvey, setCurrentSurvey] = useState<string>('P/DSS2/color');
  const [liveCoords, setLiveCoords] = useState<{ ra: number; dec: number }>({ ra, dec });

  // Keep callback ref current without retriggering the init effect
  useEffect(() => {
    onSelectRef.current = onSelectPosition;
  }, [onSelectPosition]);

  useEffect(() => {
    setLiveCoords({ ra, dec });
  }, [ra, dec]);

  // Initialize Aladin Lite v3 when panel opens
  useEffect(() => {
    if (!isOpen) return;

    let cancelled = false;

    // Use native npm-bundled Aladin Lite v3 engine
    A.init
      .then(() => {
        if (cancelled || !containerRef.current) return;

        try {
          if (aladinInstanceRef.current) {
            try {
              if (typeof aladinInstanceRef.current.destroy === 'function') {
                aladinInstanceRef.current.destroy();
              }
            } catch {
              // ignore
            }
            aladinInstanceRef.current = null;
          }

          // Clear container for fresh mount
          containerRef.current.innerHTML = '';

          const aladin = A.aladin(containerRef.current, {
            target: `${ra} ${dec}`,
            fov: Math.max(0.2, fovDegrees * 8),
            survey: currentSurvey,
            showReticle: true,
            showZoomControl: true,
            showFullscreenControl: false,
            showLayersControl: true,
            showGotoControl: false,
            cooFrame: 'J2000',
          });

          aladinInstanceRef.current = aladin;

          // Position change listener to update live Reticle coordinates
          if (typeof aladin.on === 'function') {
            aladin.on('positionChanged', () => {
              try {
                const coords = aladin.getRaDec();
                if (Array.isArray(coords) && typeof coords[0] === 'number') {
                  setLiveCoords({ ra: coords[0], dec: coords[1] });
                }
              } catch {
                // ignore
              }
            });

            aladin.on('click', (object: any) => {
              if (object && typeof object.ra === 'number' && typeof object.dec === 'number') {
                onSelectRef.current(object.ra, object.dec);
              }
            });
          }

          setIsAladinLoaded(true);
          setAladinError(null);
        } catch (err: any) {
          console.warn('Aladin Lite initialization failed:', err);
          setAladinError(
            `Aladin Lite initialization error: ${err?.message || 'Unknown error'}. You can still use coordinate entry or presets.`
          );
        }
      })
      .catch((err: any) => {
        if (cancelled) return;
        console.warn('A.init error:', err);
        setAladinError(
          'WebGL2 context could not be initialized for Aladin Lite in this browser.'
        );
      });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  // Update Aladin position when RA/Dec changes externally
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
    if (aladinInstanceRef.current) {
      try {
        aladinInstanceRef.current.setImageSurvey(newSurvey);
      } catch {
        // ignore
      }
    }
  }, []);

  // Select the current reticle center position
  const handleSelectReticlePosition = useCallback(() => {
    if (!aladinInstanceRef.current) {
      onSelectRef.current(liveCoords.ra, liveCoords.dec);
      return;
    }
    try {
      const coords = aladinInstanceRef.current.getRaDec();
      if (Array.isArray(coords) && typeof coords[0] === 'number') {
        onSelectRef.current(coords[0], coords[1]);
        return;
      }
    } catch {
      // fallback
    }
    onSelectRef.current(liveCoords.ra, liveCoords.dec);
  }, [liveCoords]);

  // Clean up instance when modal closes
  useEffect(() => {
    if (!isOpen && aladinInstanceRef.current) {
      try {
        if (typeof aladinInstanceRef.current.destroy === 'function') {
          aladinInstanceRef.current.destroy();
        }
      } catch {
        // ignore
      }
      aladinInstanceRef.current = null;
      setIsAladinLoaded(false);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="h-full flex flex-col">
      {/* Toolbar */}
      <div className="shrink-0 px-4 py-2.5 flex items-center justify-between border-b border-neutral-800 bg-neutral-950/80">
        <p className="text-xs text-neutral-400">
          Pan the sky map and click <strong className="text-neutral-200">Explore Reticle Location</strong> to center SPHEREx cutouts.
        </p>

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
            onClick={handleSelectReticlePosition}
            className="px-3 py-1 bg-cyan-500 hover:bg-cyan-400 text-neutral-950 font-semibold text-xs rounded transition cursor-pointer"
          >
            Explore Reticle
          </button>
        </div>
      </div>

      {/* Aladin Container — fills remaining space */}
      <div className="flex-1 min-h-0 relative bg-neutral-950">
        {aladinError ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center p-6 text-center text-xs text-neutral-400 space-y-3">
            <AlertTriangle className="w-6 h-6 text-amber-400" />
            <span className="max-w-md">{aladinError}</span>
            <span className="text-[11px] text-neutral-500 max-w-sm">
              You can still enter any RA/Dec coordinates or choose from the challenge target presets in the sidebar.
            </span>
          </div>
        ) : (
          <>
            <div
              ref={containerRef}
              id="aladin-lite-div"
              className="w-full h-full min-h-[360px]"
            />
            {!isAladinLoaded && (
              <div className="absolute inset-0 bg-neutral-950/80 flex items-center justify-center gap-2 text-xs text-neutral-400 font-mono">
                <RefreshCw className="w-4 h-4 animate-spin text-cyan-400" />
                Initializing Aladin Lite (WebGL)...
              </div>
            )}
          </>
        )}
      </div>

      {/* Footer status bar with live Reticle coordinates */}
      <div className="shrink-0 px-4 py-2 flex items-center justify-between text-[11px] text-neutral-400 font-mono border-t border-neutral-800 bg-neutral-950/90">
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1.5 text-cyan-400 font-semibold">
            <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
            Reticle Center: RA {liveCoords.ra.toFixed(4)}°, Dec {liveCoords.dec.toFixed(4)}°
          </span>
          <span className="text-neutral-600 hidden sm:inline">|</span>
          <span className="text-neutral-400 hidden sm:inline">SPHEREx FOV: {fovDegrees}°</span>
        </div>

        <button
          onClick={handleSelectReticlePosition}
          className="px-3.5 py-1 bg-cyan-500 hover:bg-cyan-400 text-neutral-950 font-semibold text-xs rounded-lg transition cursor-pointer"
        >
          Explore Reticle Location
        </button>
      </div>
    </div>
  );
};
