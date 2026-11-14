import React from 'react';
import { X, HelpCircle, Keyboard, Info } from 'lucide-react';
import { SPHEREX_BANDS } from '../../types/spherex';

interface HelpModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const HelpModal: React.FC<HelpModalProps> = ({ isOpen, onClose }) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-6 max-w-2xl w-full max-h-[90vh] overflow-y-auto space-y-5 shadow-2xl text-xs text-neutral-300">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-neutral-800 pb-3">
          <div className="flex items-center gap-2">
            <HelpCircle className="w-5 h-5 text-cyan-400" />
            <h2 className="text-base font-semibold text-neutral-100">
              SPHEREx Sky Viewer Guide &amp; Shortcuts
            </h2>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded text-neutral-400 hover:text-neutral-100 hover:bg-neutral-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Keyboard Shortcuts Section */}
        <div className="space-y-2">
          <div className="flex items-center gap-1.5 font-medium text-neutral-100 text-xs">
            <Keyboard className="w-4 h-4 text-cyan-400" />
            <span>Keyboard Shortcuts</span>
          </div>
          <div className="grid grid-cols-2 gap-2 bg-neutral-950 p-3 rounded-lg border border-neutral-800 font-mono text-[11px]">
            <div className="flex justify-between py-1 border-b border-neutral-900">
              <span className="text-neutral-400">Play / Pause:</span>
              <kbd className="bg-neutral-800 px-1.5 py-0.5 rounded text-neutral-200">Space</kbd>
            </div>
            <div className="flex justify-between py-1 border-b border-neutral-900">
              <span className="text-neutral-400">Step Frames:</span>
              <kbd className="bg-neutral-800 px-1.5 py-0.5 rounded text-neutral-200">&larr; / &rarr;</kbd>
            </div>
            <div className="flex justify-between py-1 border-b border-neutral-900">
              <span className="text-neutral-400">Restart Sequence:</span>
              <kbd className="bg-neutral-800 px-1.5 py-0.5 rounded text-neutral-200">Home</kbd>
            </div>
            <div className="flex justify-between py-1 border-b border-neutral-900">
              <span className="text-neutral-400">Invert Colors:</span>
              <kbd className="bg-neutral-800 px-1.5 py-0.5 rounded text-neutral-200">I</kbd>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-neutral-400">Reset Zoom &amp; Pan:</span>
              <kbd className="bg-neutral-800 px-1.5 py-0.5 rounded text-neutral-200">R</kbd>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-neutral-400">Toggle Sky Map:</span>
              <kbd className="bg-neutral-800 px-1.5 py-0.5 rounded text-neutral-200">M</kbd>
            </div>
          </div>
        </div>

        {/* SPHEREx Mission & Spectral Dispersion */}
        <div className="space-y-2">
          <div className="flex items-center gap-1.5 font-medium text-neutral-100 text-xs">
            <Info className="w-4 h-4 text-cyan-400" />
            <span>Understanding SPHEREx Images</span>
          </div>
          <div className="bg-neutral-950 p-3.5 rounded-lg border border-neutral-800 space-y-2 leading-relaxed text-neutral-300">
            <p>
              NASA&apos;s <strong>SPHEREx</strong> (Spectro-Photometer for the History of the Universe, Epoch of Reionization and Ices Explorer) maps the entire sky in 102 near-infrared spectral bands.
            </p>
            <p className="text-neutral-400">
              <strong className="text-neutral-200">Spectral vs. Spatial Motion:</strong> Each frame within a sequence is captured at a slightly shifted central wavelength. Because astronomical targets have distinct spectral slopes and absorption features, brightness fluctuations across frames are often <em>spectral signatures</em> rather than solely spatial motion or variability.
            </p>
          </div>
        </div>

        {/* 6 SPHEREx Detectors Table */}
        <div className="space-y-2">
          <span className="font-medium text-neutral-100 block text-xs">
            The 6 SPHEREx Detectors &amp; Wavelength Ranges:
          </span>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-[11px] font-mono">
            {Object.values(SPHEREX_BANDS).map((b) => (
              <div key={b.id} className="bg-neutral-950 border border-neutral-800 p-2 rounded">
                <span className="text-cyan-400 font-semibold block">{b.id}</span>
                <span className="text-neutral-400">
                  {b.wavelengthRange[0]} &ndash; {b.wavelengthRange[1]} &mu;m
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Mandatory IRSA Acknowledgement */}
        <div className="bg-neutral-950/80 border border-neutral-800/80 p-3 rounded-lg text-[11px] text-neutral-400 leading-relaxed">
          <strong className="text-neutral-300 block mb-1">IRSA Acknowledgment:</strong>
          &ldquo;This publication makes use of data products from the Spectro-Photometer for the History of the Universe, Epoch of Reionization and Ices Explorer (SPHEREx), which is a joint project of the Jet Propulsion Laboratory and the California Institute of Technology, and is funded by the National Aeronautics and Space Administration.&rdquo;
        </div>

        <div className="flex justify-end pt-1">
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded bg-cyan-500 hover:bg-cyan-400 text-neutral-950 font-medium text-xs transition"
          >
            Got it
          </button>
        </div>
      </div>
    </div>
  );
};
