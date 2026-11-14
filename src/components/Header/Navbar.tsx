import React, { useState } from 'react';
import { Share2, Settings, Check, Database } from 'lucide-react';
import { API_CONFIG } from '../../services/apiClient';

interface NavbarProps {
  useSampleFile: boolean;
  onToggleDataSource: (useSample: boolean) => void;
  onShare: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  useSampleFile,
  onToggleDataSource,
  onShare,
}) => {
  const [copied, setCopied] = useState(false);
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
  };

  return (
    <header className="border-b border-neutral-800 bg-neutral-950/80 backdrop-blur sticky top-0 z-30 px-4 py-3">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        {/* Logo and Title */}
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-cyan-600 to-blue-500 flex items-center justify-center font-bold text-white shadow-lg shadow-cyan-500/20">
            SX
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="font-semibold text-neutral-100 text-base leading-tight">
                SPHEREx Sky Viewer
              </h1>
              <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-neutral-800 text-neutral-400 border border-neutral-700">
                NASA Space Apps 2026
              </span>
            </div>
            <p className="text-xs text-neutral-500">
              Interactive Multi-Epoch Blink Player (Member 2)
            </p>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-3">
          {/* Data Source Selector */}
          <div className="flex items-center gap-2 bg-neutral-900 border border-neutral-800 rounded-md p-1 text-xs">
            <span className="text-neutral-500 pl-1 text-[11px] flex items-center gap-1">
              <Database className="w-3 h-3" /> Data:
            </span>
            <button
              onClick={() => onToggleDataSource(true)}
              className={`px-2 py-0.5 rounded font-mono transition ${
                useSampleFile
                  ? 'bg-amber-500/20 text-amber-300 font-semibold border border-amber-500/40'
                  : 'text-neutral-400 hover:text-neutral-200'
              }`}
            >
              Sample File
            </button>
            <button
              onClick={() => onToggleDataSource(false)}
              className={`px-2 py-0.5 rounded font-mono transition ${
                !useSampleFile
                  ? 'bg-cyan-500/20 text-cyan-300 font-semibold border border-cyan-500/40'
                  : 'text-neutral-400 hover:text-neutral-200'
              }`}
            >
              Member 1 API
            </button>
          </div>

          {/* Share Button */}
          <button
            onClick={handleShareClick}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-neutral-900 hover:bg-neutral-800 border border-neutral-800 text-xs text-neutral-300 transition"
          >
            {copied ? (
              <>
                <Check className="w-3.5 h-3.5 text-green-400" />
                <span className="text-green-400">Copied!</span>
              </>
            ) : (
              <>
                <Share2 className="w-3.5 h-3.5" />
                <span>Share URL</span>
              </>
            )}
          </button>

          {/* Settings Modal Toggle */}
          <button
            onClick={() => setShowSettings(!showSettings)}
            title="Configure Member 1 API Endpoint"
            className="p-1.5 rounded-md bg-neutral-900 hover:bg-neutral-800 border border-neutral-800 text-neutral-400 hover:text-neutral-200 transition"
          >
            <Settings className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Settings Modal */}
      {showSettings && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-5 max-w-md w-full space-y-4 shadow-2xl">
            <h3 className="font-semibold text-neutral-100 text-sm">
              Member 1 Backend Configuration
            </h3>
            <p className="text-xs text-neutral-400 leading-relaxed">
              When ready, Member 1 will provide the live FastAPI address. All cutout requests will be directed to <code className="bg-neutral-800 px-1 py-0.5 rounded text-cyan-400 font-mono">/api/frames</code>.
            </p>

            <div className="space-y-1.5">
              <label className="text-xs text-neutral-300 font-medium">
                Member 1 API Base URL:
              </label>
              <input
                type="text"
                value={apiUrl}
                onChange={(e) => setApiUrl(e.target.value)}
                placeholder="http://localhost:8000"
                className="w-full bg-neutral-950 border border-neutral-800 rounded px-3 py-1.5 text-xs text-neutral-200 font-mono focus:outline-none focus:border-cyan-500"
              />
              <span className="text-[11px] text-neutral-500 block font-mono">
                Full endpoint: {apiUrl}/api/frames
              </span>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setShowSettings(false)}
                className="px-3 py-1.5 rounded text-xs text-neutral-400 hover:text-neutral-200"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveApiUrl}
                className="px-3 py-1.5 rounded text-xs bg-cyan-500 hover:bg-cyan-400 text-neutral-950 font-medium"
              >
                Save Settings
              </button>
            </div>
          </div>
        </div>
      )}
    </header>
  );
};
