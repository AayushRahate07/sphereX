import React, { useState } from 'react';
import type { SpherexBand } from '../../types/spherex';
import { SPHEREX_BANDS, TEST_TARGETS } from '../../types/spherex';
import { Target, Search, Globe, Loader2 } from 'lucide-react';
import { resolveTargetQuery } from '../../utils/resolver';

interface TargetBarProps {
  ra: number;
  dec: number;
  fovDegrees: number;
  band: SpherexBand;
  onTargetChange: (ra: number, dec: number, name?: string) => void;
  onFovChange: (fov: number) => void;
  onBandChange: (band: SpherexBand) => void;
  isAladinOpen: boolean;
  onToggleAladin: () => void;
  isLoading: boolean;
}

export const TargetBar: React.FC<TargetBarProps> = ({
  ra,
  dec,
  fovDegrees,
  band,
  onTargetChange,
  onFovChange,
  onBandChange,
  isAladinOpen,
  onToggleAladin,
  isLoading,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [isResolving, setIsResolving] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  const handleSearchSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;

    setIsResolving(true);
    setSearchError(null);

    const result = await resolveTargetQuery(searchQuery);
    setIsResolving(false);

    if (result) {
      onTargetChange(result.ra, result.dec, result.name);
      setSearchQuery('');
    } else {
      setSearchError(`Could not resolve "${searchQuery}". Enter RA, Dec or try another name.`);
    }
  };

  return (
    <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4 space-y-3">
      {/* Top Row: Search Box & Sky Map Picker Button */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        {/* Name / Coordinate Search */}
        <form onSubmit={handleSearchSubmit} className="flex-1 flex items-center gap-2">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-neutral-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setSearchError(null);
              }}
              placeholder="Search object name (e.g. WISE 0855, M31) or coordinates (RA, Dec)..."
              className="w-full bg-neutral-950 border border-neutral-800 rounded-md pl-8 pr-3 py-1.5 text-xs text-neutral-200 placeholder:text-neutral-500 focus:outline-none focus:border-cyan-500 font-mono"
            />
          </div>
          <button
            type="submit"
            disabled={isResolving || !searchQuery.trim()}
            className="px-3 py-1.5 rounded-md bg-cyan-500 hover:bg-cyan-400 disabled:opacity-50 text-neutral-950 font-medium text-xs transition flex items-center gap-1.5 shrink-0"
          >
            {isResolving ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" /> Resolving
              </>
            ) : (
              'Find'
            )}
          </button>
        </form>

        {/* Aladin Lite Picker Toggle */}
        <button
          onClick={onToggleAladin}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs transition border shrink-0 ${
            isAladinOpen
              ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/50 font-semibold'
              : 'bg-neutral-800 hover:bg-neutral-700 text-neutral-300 border-neutral-700/60'
          }`}
        >
          <Globe className="w-3.5 h-3.5 text-cyan-400" />
          <span>{isAladinOpen ? 'Close Sky Map' : 'Aladin Sky Map'}</span>
        </button>
      </div>

      {searchError && (
        <div className="text-[11px] text-red-400 bg-red-500/10 px-2.5 py-1 rounded border border-red-500/20 font-mono">
          {searchError}
        </div>
      )}

      {/* Target Presets from Challenge Section 3 */}
      <div className="flex flex-wrap items-center gap-2 pt-1">
        <span className="text-xs text-neutral-400 font-medium flex items-center gap-1.5 mr-1">
          <Target className="w-3.5 h-3.5 text-cyan-400" /> Challenge Presets:
        </span>
        {TEST_TARGETS.map((target) => {
          const isSelected =
            Math.abs(target.ra - ra) < 0.001 && Math.abs(target.dec - dec) < 0.001;
          return (
            <button
              key={target.name}
              disabled={isLoading}
              onClick={() => onTargetChange(target.ra, target.dec, target.name)}
              className={`px-2.5 py-1 rounded text-xs transition border ${
                isSelected
                  ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/50 font-semibold'
                  : 'bg-neutral-800/80 hover:bg-neutral-800 text-neutral-300 border-neutral-700/60'
              } ${isLoading ? 'opacity-60 cursor-not-allowed' : ''}`}
            >
              {target.name}
            </button>
          );
        })}
      </div>

      {/* Numerical Coordinate & Band Controls */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 pt-2 border-t border-neutral-800/80 text-xs">
        {/* RA */}
        <div className="space-y-1">
          <label className="text-neutral-400 block">RA (deg):</label>
          <input
            type="number"
            step="0.0001"
            value={ra}
            disabled={isLoading}
            onChange={(e) => onTargetChange(parseFloat(e.target.value) || 0, dec)}
            className="w-full bg-neutral-950 border border-neutral-800 rounded px-2.5 py-1.5 font-mono text-neutral-200 focus:outline-none focus:border-cyan-500 disabled:opacity-50"
          />
        </div>

        {/* Dec */}
        <div className="space-y-1">
          <label className="text-neutral-400 block">Dec (deg):</label>
          <input
            type="number"
            step="0.0001"
            value={dec}
            disabled={isLoading}
            onChange={(e) => onTargetChange(ra, parseFloat(e.target.value) || 0)}
            className="w-full bg-neutral-950 border border-neutral-800 rounded px-2.5 py-1.5 font-mono text-neutral-200 focus:outline-none focus:border-cyan-500 disabled:opacity-50"
          />
        </div>

        {/* FOV */}
        <div className="space-y-1">
          <label className="text-neutral-400 block">Field of View:</label>
          <select
            value={fovDegrees}
            disabled={isLoading}
            onChange={(e) => onFovChange(parseFloat(e.target.value))}
            className="w-full bg-neutral-950 border border-neutral-800 rounded px-2.5 py-1.5 text-neutral-200 focus:outline-none focus:border-cyan-500 disabled:opacity-50"
          >
            <option value={0.02}>0.02° (~1.2 arcmin)</option>
            <option value={0.05}>0.05° (~3.0 arcmin)</option>
            <option value={0.1}>0.10° (~6.0 arcmin)</option>
            <option value={0.2}>0.20° (~12.0 arcmin)</option>
            <option value={0.25}>0.25° (~15.0 arcmin, Default)</option>
            <option value={0.5}>0.50° (~30.0 arcmin)</option>
          </select>
        </div>

        {/* Detector / Bandpass */}
        <div className="space-y-1">
          <label className="text-neutral-400 block flex items-center justify-between">
            <span>Detector / Band:</span>
            <span className="text-[10px] text-neutral-500">1 per sequence</span>
          </label>
          <select
            value={band}
            disabled={isLoading}
            onChange={(e) => onBandChange(e.target.value as SpherexBand)}
            className="w-full bg-neutral-950 border border-neutral-800 rounded px-2.5 py-1.5 text-cyan-300 font-medium focus:outline-none focus:border-cyan-500 disabled:opacity-50"
          >
            {Object.entries(SPHEREX_BANDS).map(([key, info]) => (
              <option key={key} value={key}>
                {info.label}
              </option>
            ))}
          </select>
        </div>
      </div>
    </div>
  );
};
