import React from 'react';
import type { SpherexApiResponse, SpherexFrame } from '../../types/spherex';
import { Info, HelpCircle } from 'lucide-react';

interface MetadataPanelProps {
  data: SpherexApiResponse;
  currentFrame: SpherexFrame;
}

export const MetadataPanel: React.FC<MetadataPanelProps> = ({
  data,
  currentFrame,
}) => {
  return (
    <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4 space-y-3 text-xs">
      <div className="flex items-center justify-between border-b border-neutral-800/80 pb-2">
        <div className="flex items-center gap-2 font-medium text-neutral-200">
          <Info className="w-4 h-4 text-cyan-400" />
          <span>Observation & Frame Metadata</span>
        </div>
        <div className="flex items-center gap-2">
          {currentFrame.obsId && (
            <span
              className="font-mono text-[11px] text-cyan-300 bg-cyan-950/60 px-1.5 py-0.5 rounded border border-cyan-800/40"
              title="SPHEREx Observation ID"
            >
              Obs: {currentFrame.obsId}
            </span>
          )}
          <span className="font-mono text-[11px] text-neutral-500">
            Release: {data.dataRelease}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono">
        <div>
          <span className="text-neutral-500 block text-[11px]">Target RA / Dec:</span>
          <span className="text-neutral-200">
            {data.target.ra.toFixed(4)}°, {data.target.dec.toFixed(4)}°
          </span>
        </div>

        <div>
          <span className="text-neutral-500 block text-[11px]">Observation Epoch:</span>
          <span className="text-neutral-200">
            MJD {currentFrame.mjd.toFixed(2)} ({currentFrame.dateUtc})
          </span>
        </div>

        <div>
          <span className="text-neutral-500 block text-[11px]">Central Wavelength:</span>
          <span className="text-cyan-400 font-semibold">
            {currentFrame.wavelengthMicrons.toFixed(2)} µm ({currentFrame.band})
          </span>
        </div>

        <div>
          <span className="text-neutral-500 block text-[11px]">Pixel Flux Range:</span>
          <span className="text-neutral-200">
            [{currentFrame.minFlux.toFixed(1)}, {currentFrame.maxFlux.toFixed(1)}]
          </span>
        </div>
      </div>

      {/* Scientific Notice from Build Plan Section 6, Step 4 */}
      <div className="bg-neutral-950/60 border border-neutral-800/80 rounded p-2.5 text-neutral-400 text-[11px] leading-relaxed flex items-start gap-2">
        <HelpCircle className="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" />
        <div>
          <strong className="text-neutral-300">Astronomer Notice:</strong> Each SPHEREx frame is acquired at a slightly different spectral wavelength within the detector bandpass. Brightness changes between frames are partly spectral in nature and not only spatial motion.
        </div>
      </div>
    </div>
  );
};
