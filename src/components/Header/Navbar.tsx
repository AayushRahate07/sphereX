import React, { useState } from 'react';
import { Share2, Settings, Check, Database, HelpCircle, BookOpen, Info, X } from 'lucide-react';
import { API_CONFIG } from '../../services/apiClient';

interface NavbarProps {
  onShare: () => void;
  onOpenHelp: () => void;
  onOpenScienceDossier?: () => void;
  onApiUrlChange?: (newUrl: string) => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  onShare,
  onOpenHelp,
  onOpenScienceDossier,
  onApiUrlChange,
}) => {
  const [copied, setCopied] = useState(false);
  const [showCredits, setShowCredits] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [apiUrl, setApiUrl] = useState(API_CONFIG.baseUrl);

  const handleShareClick = () => {
    onShare();
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleSaveApiUrl = () => {
    API_CONFIG.baseUrl = apiUrl;
    setShowSettings(false);
    onApiUrlChange?.(apiUrl);
  };

  return (
    <header className="h-12 border-b border-neutral-800 bg-neutral-950/90 backdrop-blur px-4 flex items-center justify-between shrink-0 select-none z-30">
      {/* Left: (i) Credits Button + Logo & App Title */}
      <div className="flex items-center gap-3">
        {/* Small circular "i" Credits Icon in Top-Left Corner */}
        <button
          onClick={() => setShowCredits(true)}
          title="Project Information, Citations & Credits"
          className="w-7 h-7 rounded-full bg-neutral-800/90 hover:bg-neutral-700 text-neutral-300 hover:text-cyan-400 border border-neutral-700/80 flex items-center justify-center transition shadow-sm"
        >
          <Info className="w-3.5 h-3.5" />
        </button>

        {/* Brand / Title */}
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded bg-gradient-to-tr from-cyan-600 to-blue-600 flex items-center justify-center font-bold text-white text-[11px] shadow-sm">
            SX
          </div>
          <span className="font-semibold text-neutral-100 text-sm tracking-tight">
            SPHEREx Sky Viewer
          </span>
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-neutral-800/80 text-neutral-400 border border-neutral-700/60 hidden sm:inline">
            NASA Space Apps 2026
          </span>
        </div>
      </div>

      {/* Right: Actions (Science Dossier, Share, Help, Settings) */}
      <div className="flex items-center gap-2">
        {/* Telemetry Indicator */}
        <div className="hidden md:flex items-center gap-1.5 bg-neutral-900 border border-neutral-800 rounded-md px-2 py-0.5 text-[11px] font-mono text-cyan-300">
          <Database className="w-3 h-3 text-cyan-400" />
          <span>NASA IRSA L2</span>
        </div>

        {/* Science Dossier Button */}
        {onOpenScienceDossier && (
          <button
            onClick={onOpenScienceDossier}
            title="Scientific Verification Dossier & Analysis"
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-cyan-950/40 hover:bg-cyan-900/60 border border-cyan-500/30 text-xs text-cyan-300 font-medium transition"
          >
            <BookOpen className="w-3.5 h-3.5 text-cyan-400" />
            <span className="hidden sm:inline">Science Dossier</span>
          </button>
        )}

        {/* Share Button */}
        <button
          onClick={handleShareClick}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-neutral-800 hover:bg-neutral-700 text-xs text-neutral-300 transition"
        >
          {copied ? (
            <>
              <Check className="w-3.5 h-3.5 text-green-400" />
              <span className="text-green-400">Copied!</span>
            </>
          ) : (
            <>
              <Share2 className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Share</span>
            </>
          )}
        </button>

        {/* Help Button */}
        <button
          onClick={onOpenHelp}
          title="Guide & Shortcuts (?)"
          className="p-1.5 rounded-md text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800 transition"
        >
          <HelpCircle className="w-4 h-4" />
        </button>

        {/* Settings Toggle */}
        <button
          onClick={() => setShowSettings(!showSettings)}
          title="Backend Connection Settings"
          className="p-1.5 rounded-md text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800 transition"
        >
          <Settings className="w-4 h-4" />
        </button>
      </div>

      {/* Settings Dropdown */}
      {showSettings && (
        <div className="absolute right-4 top-14 w-80 bg-neutral-900 border border-neutral-800 rounded-lg p-3 shadow-xl z-50 text-xs space-y-2.5">
          <div className="font-semibold text-neutral-200">API Connection Settings</div>
          <div>
            <label className="text-[11px] text-neutral-400 block mb-1">FastAPI Backend URL:</label>
            <input
              type="text"
              value={apiUrl}
              onChange={(e) => setApiUrl(e.target.value)}
              className="w-full bg-neutral-950 border border-neutral-800 rounded px-2 py-1 font-mono text-xs text-neutral-200 focus:outline-none focus:border-cyan-500"
            />
          </div>
          <div className="flex justify-end gap-2 pt-1">
            <button
              onClick={() => setShowSettings(false)}
              className="px-2.5 py-1 rounded text-neutral-400 hover:text-neutral-200"
            >
              Cancel
            </button>
            <button
              onClick={handleSaveApiUrl}
              className="px-3 py-1 rounded bg-cyan-500 hover:bg-cyan-400 text-neutral-950 font-semibold"
            >
              Apply
            </button>
          </div>
        </div>
      )}

      {/* Credits & Citations Popover Modal (Opened via Top-Left "i" Button) */}
      {showCredits && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-5 max-w-md w-full shadow-2xl space-y-4 text-xs text-neutral-300">
            <div className="flex items-center justify-between border-b border-neutral-800 pb-2.5">
              <div className="flex items-center gap-2 font-semibold text-neutral-100 text-sm">
                <Info className="w-4 h-4 text-cyan-400" />
                <span>Citations, Credits &amp; Mission Data</span>
              </div>
              <button
                onClick={() => setShowCredits(false)}
                className="text-neutral-400 hover:text-neutral-200 p-1 rounded"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3 leading-relaxed text-[11px] text-neutral-300">
              <div className="p-3 bg-neutral-950 rounded-lg border border-neutral-800 space-y-1">
                <div className="font-semibold text-neutral-100 text-xs">NASA Space Apps Challenge 2026</div>
                <p className="text-neutral-400">
                  Challenge: <em>&quot;Planet X and SPHEREx: Exploring the Infrared Sky&quot;</em>.
                  An interactive open-science web viewer and research tool designed for the general public and astronomers alike.
                </p>
              </div>

              <div className="p-3 bg-neutral-950 rounded-lg border border-neutral-800 space-y-1">
                <div className="font-semibold text-neutral-100 text-xs">Data Archive Citation</div>
                <p className="text-neutral-400">
                  This application uses real observation data from the <strong>NASA/IPAC Infrared Science Archive (IRSA)</strong>,
                  operated by the Jet Propulsion Laboratory, California Institute of Technology, under contract with the National Aeronautics and Space Administration.
                </p>
              </div>

              <div className="p-3 bg-neutral-950 rounded-lg border border-neutral-800 space-y-1">
                <div className="font-semibold text-neutral-100 text-xs">SPHEREx Mission Specs</div>
                <div className="text-neutral-400 font-mono text-[10px] space-y-0.5">
                  <div>• Mission: NASA MIDEX (Spectro-Photometer for the History of the Universe)</div>
                  <div>• Orbit: 700 km Sun-Synchronous LEO</div>
                  <div>• Bands: 6 All-Sky Infrared Detectors (0.75 to 5.0 µm)</div>
                  <div>• Pixel Scale: ~6.2 arcseconds / pixel</div>
                </div>
              </div>
            </div>

            <div className="pt-2 border-t border-neutral-800 flex justify-end">
              <button
                onClick={() => setShowCredits(false)}
                className="px-4 py-1.5 bg-neutral-800 hover:bg-neutral-700 text-neutral-200 font-medium rounded-lg transition"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </header>
  );
};
