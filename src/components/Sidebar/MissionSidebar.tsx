import React, { useState, useEffect } from 'react';
import type { SpherexApiResponse, SpherexBand, SpherexFrame } from '../../types/spherex';
import { SPHEREX_BANDS } from '../../types/spherex';
import type { StretchParams } from '../../utils/stretch';
import { resolveTargetQuery } from '../../utils/resolver';
import {
  Search,
  Sliders,
  SunMedium,
  Moon,
  Move,
  BookOpen,
  Compass,
  Orbit,
  Info,
  ChevronDown,
  ChevronUp,
  Loader2,
  StopCircle,
  CircleDot,
} from 'lucide-react';
import { ApertureAnalysisTab } from './ApertureAnalysisTab';

interface MissionSidebarProps {
  ra: number;
  dec: number;
  fovDegrees: number;
  band: SpherexBand;
  onTargetChange: (ra: number, dec: number, name?: string) => void;
  onFovChange: (fov: number) => void;
  onBandChange: (band: SpherexBand) => void;
  isLoading: boolean;
  onCancelSearch?: () => void;
  stretch: StretchParams;
  onStretchChange: (updated: Partial<StretchParams>) => void;
  onAutoMinMax: () => void;
  minPossible: number;
  maxPossible: number;
  pmRa: number;
  pmDec: number;
  onChangePm: (pmRa: number, pmDec: number) => void;
  onResetPm: () => void;
  sequenceData: SpherexApiResponse | null;
  activeDisplayFrame: SpherexFrame | null;
  onOpenInfrared101: () => void;
  selectedAperture?: { x: number; y: number } | null;
  onSelectAperture?: (x: number, y: number) => void;
  onClearAperture?: () => void;
}

export type SidebarTab = 'targets' | 'telescope' | 'aperture' | 'motion' | 'story';

interface SpaceObjectCard {
  name: string;
  badge: string;
  badgeColor: string;
  avatarBg: string;
  avatarBorder: string;
  description: string;
  metrics: string;
  ra: number;
  dec: number;
  isPlanetX?: boolean;
}

const FEATURED_OBJECTS: SpaceObjectCard[] = [
  {
    name: 'WISE 0855',
    badge: 'Coldest',
    badgeColor: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20',
    avatarBg: 'bg-cyan-500/20',
    avatarBorder: 'border-cyan-400',
    description: "The coldest known brown dwarf, as frosty as Earth's North Pole (-10°C) with water ice clouds...",
    metrics: 'Dist: 7.2 ly • Speed: 8.1"/yr • Y-Dwarf',
    ra: 133.795129,
    dec: -7.245147,
  },
  {
    name: "Barnard's Star",
    badge: 'M-Dwarf',
    badgeColor: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    avatarBg: 'bg-amber-500/20',
    avatarBorder: 'border-amber-400',
    description: 'The fastest moving star in our night sky, racing across the constellation Ophiuchus...',
    metrics: 'Dist: 5.96 ly • Speed: 10.3"/yr • Exoplanet Host',
    ra: 269.452075,
    dec: 4.693364,
  },
  {
    name: 'Planet X Hypothesis',
    badge: 'Predicted',
    badgeColor: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
    avatarBg: 'bg-blue-500/20',
    avatarBorder: 'border-blue-400',
    description: 'Hypothetical 9th planet lurking at the frozen fringes of our solar system, perturbing Kuiper Belt orbits...',
    metrics: 'Est: ~400 AU • Slow Drift • Survey Goal',
    ra: 133.795129, // Points to deep survey field
    dec: -7.245147,
    isPlanetX: true,
  },
  {
    name: 'RW Aurigae',
    badge: 'Binary',
    badgeColor: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
    avatarBg: 'bg-rose-500/20',
    avatarBorder: 'border-rose-400',
    description: 'Young erratic binary star surrounded by a turbulent planet-forming dust disk undergoing tidal disruption...',
    metrics: 'Dist: 530 ly • Variable Gas • T Tauri Star',
    ra: 77.1082,
    dec: 30.4014,
  },
  {
    name: 'R Draconis',
    badge: 'Mira Var',
    badgeColor: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
    avatarBg: 'bg-purple-500/20',
    avatarBorder: 'border-purple-400',
    description: 'Pulsating asymptotic giant branch red giant with dramatic multi-magnitude thermal pulsation cycles...',
    metrics: 'Dist: ~2,100 ly • Mira Class • AGB Giant',
    ra: 247.5544,
    dec: 66.7029,
  },
  {
    name: 'Epsilon Indi B',
    badge: 'T-Binary',
    badgeColor: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    avatarBg: 'bg-emerald-500/20',
    avatarBorder: 'border-emerald-400',
    description: 'Cool benchmark brown dwarf binary showing strong 3.3 µm methane absorption band suppression...',
    metrics: 'Dist: ~11.8 ly • Speed: 4.7"/yr • T-Dwarf',
    ra: 330.8402,
    dec: -56.7865,
  },
];

export const MissionSidebar: React.FC<MissionSidebarProps> = ({
  ra,
  dec,
  fovDegrees,
  band,
  onTargetChange,
  onFovChange,
  onBandChange,
  isLoading,
  onCancelSearch,
  stretch,
  onStretchChange,
  onAutoMinMax,
  minPossible,
  maxPossible,
  pmRa,
  pmDec,
  onChangePm,
  onResetPm,
  sequenceData,
  activeDisplayFrame,
  onOpenInfrared101,
  selectedAperture,
  onSelectAperture,
  onClearAperture,
}) => {
  const [activeTab, setActiveTab] = useState<SidebarTab>('targets');

  // Auto-switch to aperture tab when user clicks a pixel on the canvas
  useEffect(() => {
    if (selectedAperture) {
      setActiveTab('aperture');
    }
  }, [selectedAperture]);
  const [searchQuery, setSearchQuery] = useState('');
  const [isResolving, setIsResolving] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  // Custom coordinates accordion
  const [showCoordinatesInput, setShowCoordinatesInput] = useState<boolean>(false);
  const [raInput, setRaInput] = useState<string>(ra.toString());
  const [decInput, setDecInput] = useState<string>(dec.toString());

  useEffect(() => {
    setRaInput(ra.toString());
  }, [ra]);

  useEffect(() => {
    setDecInput(dec.toString());
  }, [dec]);

  const commitCoordinates = () => {
    const parsedRa = parseFloat(raInput);
    const parsedDec = parseFloat(decInput);
    if (!isNaN(parsedRa) && !isNaN(parsedDec)) {
      if (Math.abs(parsedRa - ra) > 1e-6 || Math.abs(parsedDec - dec) > 1e-6) {
        onTargetChange(parsedRa, parsedDec);
      }
    }
  };

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
      setSearchError(`Could not find "${searchQuery}". Enter coordinates or try another name.`);
    }
  };

  return (
    <div className="h-full flex flex-col bg-neutral-900/90 border border-neutral-800 rounded-xl overflow-hidden shadow-xl text-neutral-200 select-none">
      {/* 1. Top Badges Header (matching user Image 1) */}
      <div className="px-3 pt-2.5 pb-2 flex items-center justify-between border-b border-neutral-800/80 bg-neutral-950/40">
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-neutral-800/70 border border-neutral-700/60 text-[11px] font-medium text-neutral-300">
          <Orbit className="w-3.5 h-3.5 text-cyan-400" />
          <span>Orbit: 700km LEO</span>
        </div>

        <button
          onClick={onOpenInfrared101}
          className="flex items-center gap-1 px-2.5 py-1 rounded-full bg-cyan-950/40 hover:bg-cyan-900/50 border border-cyan-500/30 text-[11px] font-medium text-cyan-300 transition"
        >
          <Info className="w-3.5 h-3.5" />
          <span>INFRARED 101</span>
        </button>
      </div>

      {/* 2. 5-Tab Navigation Bar */}
      <div className="grid grid-cols-5 border-b border-neutral-800 bg-neutral-950/60 text-xs">
        <button
          onClick={() => setActiveTab('targets')}
          className={`py-2.5 flex flex-col items-center gap-1 transition border-b-2 ${
            activeTab === 'targets'
              ? 'border-cyan-400 text-cyan-300 font-semibold bg-neutral-900/80'
              : 'border-transparent text-neutral-400 hover:text-neutral-200 hover:bg-neutral-900/40'
          }`}
        >
          <Search className="w-3.5 h-3.5" />
          <span className="text-[10px]">Target</span>
        </button>

        <button
          onClick={() => setActiveTab('telescope')}
          className={`py-2.5 flex flex-col items-center gap-1 transition border-b-2 ${
            activeTab === 'telescope'
              ? 'border-cyan-400 text-cyan-300 font-semibold bg-neutral-900/80'
              : 'border-transparent text-neutral-400 hover:text-neutral-200 hover:bg-neutral-900/40'
          }`}
        >
          <Sliders className="w-3.5 h-3.5" />
          <span className="text-[10px]">Telescope</span>
        </button>

        <button
          onClick={() => setActiveTab('aperture')}
          className={`py-2.5 flex flex-col items-center gap-1 transition border-b-2 relative ${
            activeTab === 'aperture'
              ? 'border-cyan-400 text-cyan-300 font-semibold bg-neutral-900/80'
              : 'border-transparent text-neutral-400 hover:text-neutral-200 hover:bg-neutral-900/40'
          }`}
        >
          <CircleDot className="w-3.5 h-3.5" />
          <span className="text-[10px]">Aperture</span>
          {selectedAperture && (
            <span className="absolute top-1 right-2 w-1.5 h-1.5 rounded-full bg-cyan-400" />
          )}
        </button>

        <button
          onClick={() => setActiveTab('motion')}
          className={`py-2.5 flex flex-col items-center gap-1 transition border-b-2 ${
            activeTab === 'motion'
              ? 'border-cyan-400 text-cyan-300 font-semibold bg-neutral-900/80'
              : 'border-transparent text-neutral-400 hover:text-neutral-200 hover:bg-neutral-900/40'
          }`}
        >
          <Move className="w-3.5 h-3.5" />
          <span className="text-[10px]">Motion</span>
        </button>

        <button
          onClick={() => setActiveTab('story')}
          className={`py-2.5 flex flex-col items-center gap-1 transition border-b-2 ${
            activeTab === 'story'
              ? 'border-cyan-400 text-cyan-300 font-semibold bg-neutral-900/80'
              : 'border-transparent text-neutral-400 hover:text-neutral-200 hover:bg-neutral-900/40'
          }`}
        >
          <BookOpen className="w-3.5 h-3.5" />
          <span className="text-[10px]">Story</span>
        </button>
      </div>

      {/* 3. Tab Contents Container (Scrolls cleanly inside itself; no page scroll) */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {/* ================= TAB 1: FIND TARGET ================= */}
        {activeTab === 'targets' && (
          <div className="space-y-3">
            {/* Search Input Box */}
            <form onSubmit={handleSearchSubmit} className="relative flex items-center">
              <Search className="w-4 h-4 text-neutral-400 absolute left-3" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  setSearchError(null);
                }}
                placeholder="Search star, planet, or coordinates..."
                className="w-full bg-neutral-950 border border-neutral-800 rounded-lg pl-9 pr-20 py-2 text-xs text-neutral-200 placeholder:text-neutral-500 focus:outline-none focus:border-cyan-500 font-sans"
              />
              <button
                type="submit"
                disabled={isLoading || isResolving || !searchQuery.trim()}
                className="absolute right-1.5 px-3 py-1 bg-cyan-500 hover:bg-cyan-400 disabled:opacity-50 text-neutral-950 font-semibold text-xs rounded transition flex items-center gap-1"
              >
                {isLoading || isResolving ? (
                  <>
                    <Loader2 className="w-3 h-3 animate-spin" />
                    <span>{isResolving ? 'Resolving...' : 'Loading...'}</span>
                  </>
                ) : (
                  'Explore'
                )}
              </button>
            </form>

            {isLoading && onCancelSearch && (
              <div className="flex justify-end">
                <button
                  type="button"
                  onClick={onCancelSearch}
                  className="text-[11px] text-rose-400 hover:text-rose-300 flex items-center gap-1 transition"
                >
                  <StopCircle className="w-3 h-3" /> Stop request
                </button>
              </div>
            )}

            {searchError && (
              <div className="text-[11px] text-red-400 bg-red-500/10 px-2.5 py-1.5 rounded border border-red-500/20">
                {searchError}
              </div>
            )}

            {/* Custom Coordinates Accordion Toggle (User explicitly requested keeping this) */}
            <div className="border border-neutral-800/80 rounded-lg bg-neutral-950/60 overflow-hidden">
              <button
                type="button"
                onClick={() => setShowCoordinatesInput((prev) => !prev)}
                className="w-full px-3 py-2 flex items-center justify-between text-xs text-neutral-300 hover:text-neutral-100 transition"
              >
                <span className="flex items-center gap-1.5 font-medium">
                  <Compass className="w-3.5 h-3.5 text-cyan-400" /> Enter Custom Coordinates (RA / Dec)
                </span>
                {showCoordinatesInput ? <ChevronUp className="w-3.5 h-3.5 text-neutral-400" /> : <ChevronDown className="w-3.5 h-3.5 text-neutral-400" />}
              </button>

              {showCoordinatesInput && (
                <div className="p-3 border-t border-neutral-800/80 space-y-2.5 bg-neutral-950/80">
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div>
                      <label className="text-[11px] text-neutral-400 block mb-1">RA (degrees):</label>
                      <input
                        type="number"
                        step="0.0001"
                        value={raInput}
                        onChange={(e) => setRaInput(e.target.value)}
                        onBlur={commitCoordinates}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') commitCoordinates();
                        }}
                        className="w-full bg-neutral-900 border border-neutral-800 rounded px-2.5 py-1.5 font-mono text-neutral-200 focus:outline-none focus:border-cyan-500"
                      />
                    </div>
                    <div>
                      <label className="text-[11px] text-neutral-400 block mb-1">Dec (degrees):</label>
                      <input
                        type="number"
                        step="0.0001"
                        value={decInput}
                        onChange={(e) => setDecInput(e.target.value)}
                        onBlur={commitCoordinates}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') commitCoordinates();
                        }}
                        className="w-full bg-neutral-900 border border-neutral-800 rounded px-2.5 py-1.5 font-mono text-neutral-200 focus:outline-none focus:border-cyan-500"
                      />
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={commitCoordinates}
                    className="w-full py-1.5 rounded bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-300 font-medium text-xs border border-cyan-500/40 transition"
                  >
                    Apply Coordinates
                  </button>
                </div>
              )}
            </div>

            {/* Section Header: Featured Space Objects */}
            <div className="flex items-center justify-between pt-1 text-[11px] font-semibold text-neutral-400 uppercase tracking-wider">
              <span>Featured Space Objects</span>
              <span className="text-[10px] text-neutral-500 lowercase font-mono">SPHEREx Sky Vault</span>
            </div>

            {/* List of Featured Objects (Matching user Image 1 card styling) */}
            <div className="space-y-2">
              {FEATURED_OBJECTS.map((obj) => {
                const isSelected = Math.abs(obj.ra - ra) < 0.001 && Math.abs(obj.dec - dec) < 0.001;

                return (
                  <div
                    key={obj.name}
                    onClick={() => onTargetChange(obj.ra, obj.dec, obj.name)}
                    className={`p-3 rounded-xl border transition-all cursor-pointer ${
                      isSelected
                        ? 'bg-neutral-800/90 border-cyan-500/60 shadow-lg shadow-cyan-950/40'
                        : 'bg-neutral-950/60 hover:bg-neutral-800/50 border-neutral-800/80 hover:border-neutral-700'
                    }`}
                  >
                    <div className="flex items-start gap-2.5">
                      {/* Avatar circle with glow border */}
                      <div className={`w-6 h-6 rounded-full shrink-0 flex items-center justify-center border ${obj.avatarBg} ${obj.avatarBorder} mt-0.5`}>
                        <div className="w-2 h-2 rounded-full bg-white shadow-sm" />
                      </div>

                      {/* Content */}
                      <div className="flex-1 min-w-0 space-y-1">
                        <div className="flex items-center justify-between">
                          <span className="font-semibold text-xs text-neutral-100 truncate pr-2">
                            {obj.name}
                          </span>
                          <span className={`text-[10px] px-1.5 py-0.5 rounded border font-medium whitespace-nowrap ${obj.badgeColor}`}>
                            {isSelected ? 'Active' : obj.badge}
                          </span>
                        </div>

                        <p className="text-[11px] text-neutral-400 leading-snug line-clamp-2">
                          {obj.description}
                        </p>

                        <div className="text-[10px] text-neutral-500 font-mono pt-0.5">
                          {obj.metrics}
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* ================= TAB 2: TELESCOPE & DISPLAY ================= */}
        {activeTab === 'telescope' && (
          <div className="space-y-3.5 text-xs">
            {/* Brightness Stretch & Contrast */}
            <div className="p-3 bg-neutral-950/60 rounded-xl border border-neutral-800/80 space-y-3">
              <div className="flex items-center justify-between font-medium">
                <span className="text-neutral-200">Image Stretch &amp; Contrast</span>
                <button
                  onClick={() => onStretchChange({ invert: !stretch.invert })}
                  className={`flex items-center gap-1 px-2 py-0.5 rounded text-[11px] border transition ${
                    stretch.invert ? 'bg-neutral-200 text-neutral-950 border-neutral-300 font-medium' : 'bg-neutral-800 text-neutral-300 border-neutral-700'
                  }`}
                >
                  {stretch.invert ? <SunMedium className="w-3 h-3" /> : <Moon className="w-3 h-3" />}
                  <span>{stretch.invert ? 'Inverted' : 'Standard'}</span>
                </button>
              </div>

              {/* Stretch Mode (Linear vs Log) */}
              <div className="flex items-center gap-2">
                <span className="text-[11px] text-neutral-400">Scale:</span>
                <div className="flex rounded-md bg-neutral-800 p-0.5 border border-neutral-700">
                  <button
                    onClick={() => onStretchChange({ type: 'linear' })}
                    className={`px-2.5 py-0.5 rounded text-xs transition ${
                      stretch.type === 'linear' ? 'bg-cyan-500 text-neutral-950 font-semibold' : 'text-neutral-400 hover:text-neutral-200'
                    }`}
                  >
                    Linear
                  </button>
                  <button
                    onClick={() => onStretchChange({ type: 'log' })}
                    className={`px-2.5 py-0.5 rounded text-xs transition ${
                      stretch.type === 'log' ? 'bg-cyan-500 text-neutral-950 font-semibold' : 'text-neutral-400 hover:text-neutral-200'
                    }`}
                  >
                    Logarithmic
                  </button>
                </div>
                <button
                  onClick={onAutoMinMax}
                  className="ml-auto text-[11px] px-2 py-1 rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-300 transition"
                >
                  Auto Min/Max
                </button>
              </div>

              {/* Sliders */}
              <div className="space-y-2 pt-1">
                <div className="flex items-center gap-2">
                  <span className="text-[11px] text-neutral-400 min-w-[50px]">Min Cut:</span>
                  <input
                    type="range"
                    min={Math.floor(minPossible)}
                    max={Math.ceil(maxPossible)}
                    step={0.5}
                    value={stretch.min}
                    onChange={(e) => onStretchChange({ min: Number(e.target.value) })}
                    className="flex-1 h-1.5 bg-neutral-800 rounded appearance-none cursor-pointer"
                  />
                  <span className="font-mono text-[11px] text-neutral-300 min-w-[40px] text-right">
                    {stretch.min.toFixed(1)}
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  <span className="text-[11px] text-neutral-400 min-w-[50px]">Max Cut:</span>
                  <input
                    type="range"
                    min={Math.floor(minPossible)}
                    max={Math.ceil(maxPossible)}
                    step={0.5}
                    value={stretch.max}
                    onChange={(e) => onStretchChange({ max: Number(e.target.value) })}
                    className="flex-1 h-1.5 bg-neutral-800 rounded appearance-none cursor-pointer"
                  />
                  <span className="font-mono text-[11px] text-neutral-300 min-w-[40px] text-right">
                    {stretch.max.toFixed(1)}
                  </span>
                </div>
              </div>
            </div>

            {/* Detector Bandpass & Field of View */}
            <div className="p-3 bg-neutral-950/60 rounded-xl border border-neutral-800/80 space-y-2.5">
              <span className="text-neutral-200 font-medium block">SPHEREx Instrument Configuration</span>

              <div>
                <label className="text-[11px] text-neutral-400 block mb-1">Detector Bandpass:</label>
                <select
                  value={band}
                  onChange={(e) => onBandChange(e.target.value as SpherexBand)}
                  className="w-full bg-neutral-900 border border-neutral-800 rounded px-2.5 py-1.5 text-xs text-neutral-200 focus:outline-none focus:border-cyan-500"
                >
                  {Object.entries(SPHEREX_BANDS).map(([key, info]) => (
                    <option key={key} value={key}>
                      {info.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-[11px] text-neutral-400 block mb-1">Field of View (FOV):</label>
                <select
                  value={fovDegrees}
                  onChange={(e) => onFovChange(parseFloat(e.target.value))}
                  className="w-full bg-neutral-900 border border-neutral-800 rounded px-2.5 py-1.5 text-xs text-neutral-200 focus:outline-none focus:border-cyan-500"
                >
                  <option value={0.02}>0.02° (~1.2 arcmin)</option>
                  <option value={0.05}>0.05° (~3.0 arcmin — Default)</option>
                  <option value={0.1}>0.10° (~6.0 arcmin)</option>
                  <option value={0.2}>0.20° (~12.0 arcmin)</option>
                </select>
              </div>
            </div>

            {/* Target Metadata details */}
            {sequenceData && activeDisplayFrame && (
              <div className="p-3 bg-neutral-950/60 rounded-xl border border-neutral-800/80 text-[11px] space-y-1.5 font-mono text-neutral-400">
                <div className="text-neutral-300 font-sans font-medium mb-1">Observation Telemetry</div>
                <div className="flex justify-between">
                  <span>Wavelength:</span>
                  <span className="text-cyan-400 font-bold">{activeDisplayFrame.wavelengthMicrons.toFixed(2)} µm</span>
                </div>
                <div className="flex justify-between">
                  <span>Pixel Scale:</span>
                  <span>~6.16″ / pixel</span>
                </div>
                <div className="flex justify-between">
                  <span>Dimensions:</span>
                  <span>{activeDisplayFrame.width} × {activeDisplayFrame.height} px</span>
                </div>
                <div className="flex justify-between">
                  <span>Epoch Count:</span>
                  <span className="text-neutral-200">{sequenceData.frameCount} frames</span>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ================= TAB: APERTURE ANALYSIS AT PIXEL ================= */}
        {activeTab === 'aperture' && (
          <ApertureAnalysisTab
            selectedAperture={selectedAperture ?? null}
            onSelectAperture={onSelectAperture ?? (() => {})}
            onClearAperture={onClearAperture ?? (() => {})}
            frames={sequenceData?.frames ?? []}
            activeFrame={activeDisplayFrame}
          />
        )}

        {/* ================= TAB 4: MOTION & PLANET X ================= */}
        {activeTab === 'motion' && (
          <div className="space-y-3.5 text-xs">
            <div className="p-3 bg-neutral-950/60 rounded-xl border border-neutral-800/80 space-y-3">
              <div className="flex items-center justify-between">
                <span className="font-medium text-neutral-200 flex items-center gap-1.5">
                  <Move className="w-3.5 h-3.5 text-cyan-400" /> Shift-and-Stack Proper Motion
                </span>
                <button
                  onClick={onResetPm}
                  className="text-[11px] text-neutral-400 hover:text-neutral-200 px-2 py-0.5 rounded bg-neutral-800 transition"
                >
                  Reset
                </button>
              </div>

              <p className="text-[11px] text-neutral-400 leading-relaxed">
                Applies sub-pixel bilinear shifts (<span className="font-mono text-cyan-400">Δt × μ</span>) across epochs. Objects moving at this velocity add constructively while stationary stars streak.
              </p>

              {/* Quick Motion Presets */}
              <div className="space-y-1.5">
                <span className="text-[11px] text-neutral-400 font-medium">Quick Velocity Presets:</span>
                <div className="flex flex-wrap gap-1.5">
                  <button
                    onClick={() => onChangePm(0, 0)}
                    className={`px-2 py-1 rounded border text-[11px] transition ${
                      pmRa === 0 && pmDec === 0 ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/50 font-semibold' : 'bg-neutral-800 text-neutral-400 border-neutral-700'
                    }`}
                  >
                    Zero Motion
                  </button>
                  <button
                    onClick={() => onChangePm(-8.1, 0.6)}
                    className={`px-2 py-1 rounded border text-[11px] transition ${
                      pmRa === -8.1 && pmDec === 0.6 ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/50 font-semibold' : 'bg-neutral-800 text-neutral-400 border-neutral-700'
                    }`}
                  >
                    WISE 0855 (-8.1″/yr)
                  </button>
                  <button
                    onClick={() => onChangePm(-0.8, 10.36)}
                    className={`px-2 py-1 rounded border text-[11px] transition ${
                      pmRa === -0.8 && pmDec === 10.36 ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/50 font-semibold' : 'bg-neutral-800 text-neutral-400 border-neutral-700'
                    }`}
                  >
                    Barnard&apos;s (+10.4″/yr)
                  </button>
                </div>
              </div>

              {/* RA Motion Slider */}
              <div className="space-y-1">
                <div className="flex justify-between text-[11px]">
                  <span className="text-neutral-400">RA Motion (μ_α cos δ):</span>
                  <span className="font-mono text-cyan-400 font-medium">{pmRa > 0 ? `+${pmRa.toFixed(1)}` : pmRa.toFixed(1)} &quot;/yr</span>
                </div>
                <input
                  type="range"
                  min={-20}
                  max={20}
                  step={0.1}
                  value={pmRa}
                  onChange={(e) => onChangePm(parseFloat(e.target.value), pmDec)}
                  className="w-full h-1.5 bg-neutral-800 rounded appearance-none cursor-pointer"
                />
              </div>

              {/* Dec Motion Slider */}
              <div className="space-y-1">
                <div className="flex justify-between text-[11px]">
                  <span className="text-neutral-400">Dec Motion (μ_δ):</span>
                  <span className="font-mono text-cyan-400 font-medium">{pmDec > 0 ? `+${pmDec.toFixed(1)}` : pmDec.toFixed(1)} &quot;/yr</span>
                </div>
                <input
                  type="range"
                  min={-20}
                  max={20}
                  step={0.1}
                  value={pmDec}
                  onChange={(e) => onChangePm(pmRa, parseFloat(e.target.value))}
                  className="w-full h-1.5 bg-neutral-800 rounded appearance-none cursor-pointer"
                />
              </div>
            </div>
          </div>
        )}

        {/* ================= TAB 4: STORY & MISSION ================= */}
        {activeTab === 'story' && (
          <div className="space-y-3 text-xs leading-relaxed text-neutral-300">
            <div className="p-3 bg-neutral-950/60 rounded-xl border border-neutral-800/80 space-y-2">
              <span className="font-semibold text-cyan-300 text-sm block">NASA SPHEREx Mission</span>
              <p className="text-[11px] text-neutral-400 leading-relaxed">
                The Spectro-Photometer for the History of the Universe, Epoch of Reionization and Ices Explorer (SPHEREx) maps the entire sky in 102 infrared color bands every 6 months.
              </p>
              <div className="text-[10px] text-neutral-500 font-mono space-y-0.5 pt-1">
                <div>• Orbit: 700 km Sun-Synchronous Low Earth Orbit</div>
                <div>• Coverage: 0.75 to 5.0 microns across 6 detector arrays</div>
                <div>• Resolution: 6.2 arcseconds per pixel</div>
              </div>
            </div>

            <div className="p-3 bg-neutral-950/60 rounded-xl border border-neutral-800/80 space-y-2">
              <span className="font-semibold text-neutral-100 block">Planet X Search Technique</span>
              <p className="text-[11px] text-neutral-400 leading-relaxed">
                Hypothetical trans-Neptunian planets and nearby sub-stellar brown dwarfs reflect almost no visible sunlight, but emit detectable mid-infrared thermal glow. By blinking and stacking multi-epoch SPHEREx frames, their telltale motion stands out against stationary background stars.
              </p>
              <button
                onClick={onOpenInfrared101}
                className="w-full mt-1 py-1.5 bg-neutral-800 hover:bg-neutral-700 text-cyan-300 rounded font-medium text-xs transition flex items-center justify-center gap-1.5"
              >
                <BookOpen className="w-3.5 h-3.5" /> Open Full Science Dossier
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
