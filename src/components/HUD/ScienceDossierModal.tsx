import React, { useState } from 'react';
import { X, BookOpen, Target, Sparkles, TrendingUp, Layers, ExternalLink } from 'lucide-react';
import { TEST_TARGETS } from '../../types/spherex';

interface ScienceDossierModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectTarget: (ra: number, dec: number, name: string) => void;
}

export const ScienceDossierModal: React.FC<ScienceDossierModalProps> = ({
  isOpen,
  onClose,
  onSelectTarget,
}) => {
  const [activeTab, setActiveTab] = useState<'targets' | 'spectra' | 'lightcurves' | 'stacking'>('targets');

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-6 max-w-4xl w-full max-h-[90vh] overflow-y-auto space-y-5 shadow-2xl text-xs text-neutral-300">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-neutral-800 pb-3">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-cyan-500/20 border border-cyan-500/40 flex items-center justify-center">
              <BookOpen className="w-4 h-4 text-cyan-400" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-neutral-100">
                NASA SPHEREx Science Dossier &amp; Validation Report
              </h2>
              <p className="text-[11px] text-neutral-500 font-mono">
                Member 3 Astrophysical Verification &bull; Multi-Detector Infrared Analysis
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded text-neutral-400 hover:text-neutral-100 hover:bg-neutral-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="flex items-center gap-2 border-b border-neutral-800/80 pb-2">
          <button
            onClick={() => setActiveTab('targets')}
            className={`px-3 py-1.5 rounded-md font-medium text-xs transition flex items-center gap-1.5 ${
              activeTab === 'targets'
                ? 'bg-cyan-500 text-neutral-950 font-semibold'
                : 'text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800'
            }`}
          >
            <Target className="w-3.5 h-3.5" /> 5 Challenge Targets
          </button>
          <button
            onClick={() => setActiveTab('spectra')}
            className={`px-3 py-1.5 rounded-md font-medium text-xs transition flex items-center gap-1.5 ${
              activeTab === 'spectra'
                ? 'bg-cyan-500 text-neutral-950 font-semibold'
                : 'text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800'
            }`}
          >
            <Sparkles className="w-3.5 h-3.5" /> Multi-Detector Spectra
          </button>
          <button
            onClick={() => setActiveTab('lightcurves')}
            className={`px-3 py-1.5 rounded-md font-medium text-xs transition flex items-center gap-1.5 ${
              activeTab === 'lightcurves'
                ? 'bg-cyan-500 text-neutral-950 font-semibold'
                : 'text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800'
            }`}
          >
            <TrendingUp className="w-3.5 h-3.5" /> Time-Domain Light Curves
          </button>
          <button
            onClick={() => setActiveTab('stacking')}
            className={`px-3 py-1.5 rounded-md font-medium text-xs transition flex items-center gap-1.5 ${
              activeTab === 'stacking'
                ? 'bg-cyan-500 text-neutral-950 font-semibold'
                : 'text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800'
            }`}
          >
            <Layers className="w-3.5 h-3.5" /> Co-addition &amp; SNR Boost
          </button>
        </div>

        {/* Tab 1: 5 Challenge Targets */}
        {activeTab === 'targets' && (
          <div className="space-y-4">
            <p className="text-neutral-400 text-xs">
              Scientific profiles and astrometric drift characteristics for the five test targets specified in
              the NASA Space Apps 2026 Challenge:
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {/* WISE 0855 */}
              <div className="bg-neutral-950 p-4 rounded-xl border border-neutral-800 space-y-2.5">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-cyan-300 text-sm">WISE 0855−0714</span>
                  <span className="text-[10px] bg-cyan-500/10 text-cyan-400 px-2 py-0.5 rounded border border-cyan-500/20 font-mono">
                    Y-Type Brown Dwarf
                  </span>
                </div>
                <div className="text-[11px] text-neutral-400 space-y-1 font-mono">
                  <div>T_eff: ~250 K (Coldest known sub-stellar object)</div>
                  <div>Proper Motion: 8.14″/yr (1.31 pix/yr at 6.2″/pix)</div>
                  <div>SPHEREx Detectors: D1–D6 (Peaks in D5 &amp; D6 at 4.4–5.0 µm)</div>
                </div>
                <p className="text-[11px] text-neutral-400 leading-relaxed">
                  Near-IR flux (&lt;2.5 µm) is completely suppressed by deep atmospheric H₂O and CH₄ absorption.
                  Emits prominently in the 4.5–4.9 µm thermal window.
                </p>
                <button
                  onClick={() => {
                    const t = TEST_TARGETS[0];
                    onSelectTarget(t.ra, t.dec, t.name);
                    onClose();
                  }}
                  className="w-full mt-2 py-1.5 bg-neutral-800 hover:bg-cyan-500 hover:text-neutral-950 font-medium rounded text-xs transition flex items-center justify-center gap-1.5"
                >
                  <ExternalLink className="w-3.5 h-3.5" /> Load in Sky Viewer
                </button>
              </div>

              {/* Barnard's Star */}
              <div className="bg-neutral-950 p-4 rounded-xl border border-neutral-800 space-y-2.5">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-cyan-300 text-sm">Barnard's Star (GJ 699)</span>
                  <span className="text-[10px] bg-amber-500/10 text-amber-400 px-2 py-0.5 rounded border border-amber-500/20 font-mono">
                    M4V Red Dwarf
                  </span>
                </div>
                <div className="text-[11px] text-neutral-400 space-y-1 font-mono">
                  <div>Distance: 1.83 pc (Second closest star system)</div>
                  <div>Proper Motion: 10.37″/yr (1.67 pix/yr — Fastest in sky!)</div>
                  <div>SPHEREx Detectors: D1–D6 (High SNR detection across all bands)</div>
                </div>
                <p className="text-[11px] text-neutral-400 leading-relaxed">
                  Fastest apparent motion of any known star. Displays prominent TiO and VO absorption in near-IR with
                  a spectral peak around 1.1–1.5 µm (Band 2).
                </p>
                <button
                  onClick={() => {
                    const t = TEST_TARGETS[1];
                    onSelectTarget(t.ra, t.dec, t.name);
                    onClose();
                  }}
                  className="w-full mt-2 py-1.5 bg-neutral-800 hover:bg-cyan-500 hover:text-neutral-950 font-medium rounded text-xs transition flex items-center justify-center gap-1.5"
                >
                  <ExternalLink className="w-3.5 h-3.5" /> Load in Sky Viewer
                </button>
              </div>

              {/* Epsilon Indi B */}
              <div className="bg-neutral-950 p-4 rounded-xl border border-neutral-800 space-y-2.5">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-cyan-300 text-sm">Epsilon Indi B</span>
                  <span className="text-[10px] bg-purple-500/10 text-purple-400 px-2 py-0.5 rounded border border-purple-500/20 font-mono">
                    T-Dwarf Binary (T1 + T6)
                  </span>
                </div>
                <div className="text-[11px] text-neutral-400 space-y-1 font-mono">
                  <div>Distance: ~3.64 pc</div>
                  <div>Proper Motion: 4.70″/yr (0.76 pix/yr)</div>
                  <div>Features: Strong 3.3 µm CH₄ fundamental band suppression</div>
                </div>
                <p className="text-[11px] text-neutral-400 leading-relaxed">
                  Benchmark brown dwarf binary demonstrating the transition between early and late T spectral types.
                  Shows pronounced methane and water molecular absorption.
                </p>
                <button
                  onClick={() => {
                    const t = TEST_TARGETS[2];
                    onSelectTarget(t.ra, t.dec, t.name);
                    onClose();
                  }}
                  className="w-full mt-2 py-1.5 bg-neutral-800 hover:bg-cyan-500 hover:text-neutral-950 font-medium rounded text-xs transition flex items-center justify-center gap-1.5"
                >
                  <ExternalLink className="w-3.5 h-3.5" /> Load in Sky Viewer
                </button>
              </div>

              {/* RW Aurigae */}
              <div className="bg-neutral-950 p-4 rounded-xl border border-neutral-800 space-y-2.5">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-cyan-300 text-sm">RW Aurigae</span>
                  <span className="text-[10px] bg-rose-500/10 text-rose-400 px-2 py-0.5 rounded border border-rose-500/20 font-mono">
                    Classical T Tauri YSO
                  </span>
                </div>
                <div className="text-[11px] text-neutral-400 space-y-1 font-mono">
                  <div>Type: Young Protostellar Binary System</div>
                  <div>Variability: Accretion flaring &amp; circumstellar dust occultation</div>
                  <div>Detector: SPHEREx Band 2 (1.1–1.6 µm)</div>
                </div>
                <p className="text-[11px] text-neutral-400 leading-relaxed">
                  Young stellar object undergoing erratic multi-magnitude dimming events caused by tidal disruption
                  and occultation by circumstellar dust streams.
                </p>
                <button
                  onClick={() => {
                    const t = TEST_TARGETS[3];
                    onSelectTarget(t.ra, t.dec, t.name);
                    onClose();
                  }}
                  className="w-full mt-2 py-1.5 bg-neutral-800 hover:bg-cyan-500 hover:text-neutral-950 font-medium rounded text-xs transition flex items-center justify-center gap-1.5"
                >
                  <ExternalLink className="w-3.5 h-3.5" /> Load in Sky Viewer
                </button>
              </div>

              {/* R Draconis */}
              <div className="bg-neutral-950 p-4 rounded-xl border border-neutral-800 space-y-2.5 md:col-span-2">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-cyan-300 text-sm">R Draconis</span>
                  <span className="text-[10px] bg-emerald-500/10 text-emerald-400 px-2 py-0.5 rounded border border-emerald-500/20 font-mono">
                    Mira Long-Period Variable Giant
                  </span>
                </div>
                <div className="text-[11px] text-neutral-400 space-y-1 font-mono">
                  <div>Period: ~245.6 days</div>
                  <div>Magnitude Range: V ~ 6.7 to 13.2 (Strong Infrared Emitter)</div>
                  <div>Detector: SPHEREx Band 1 (0.75–1.1 µm)</div>
                </div>
                <p className="text-[11px] text-neutral-400 leading-relaxed">
                  Pulsating Asymptotic Giant Branch (AGB) star undergoing radial stellar pulsations. Bright infrared flux
                  requires saturation masking checks during peak pulsation phases.
                </p>
                <button
                  onClick={() => {
                    const t = TEST_TARGETS[4];
                    onSelectTarget(t.ra, t.dec, t.name);
                    onClose();
                  }}
                  className="w-full mt-2 py-1.5 bg-neutral-800 hover:bg-cyan-500 hover:text-neutral-950 font-medium rounded text-xs transition flex items-center justify-center gap-1.5"
                >
                  <ExternalLink className="w-3.5 h-3.5" /> Load in Sky Viewer
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: Multi-Detector Spectra */}
        {activeTab === 'spectra' && (
          <div className="space-y-4">
            <p className="text-neutral-400 text-xs">
              Continuous multi-detector spectra extracted across SPHEREx Bands 1 through 6 (0.75–5.00 µm) using Member 3's
              photometric aperture synthesis:
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="bg-neutral-950 p-3 rounded-xl border border-neutral-800 space-y-2">
                <div className="font-semibold text-cyan-300 text-xs flex items-center justify-between">
                  <span>Barnard's Star (M4V Red Dwarf)</span>
                  <span className="text-[10px] text-neutral-500 font-mono">All 6 Bands</span>
                </div>
                <img
                  src="/science/barnards_star_spectrum.png"
                  alt="Barnard's Star SPHEREx Spectrum"
                  className="w-full rounded-lg border border-neutral-800 bg-neutral-900"
                />
                <p className="text-[11px] text-neutral-400 leading-relaxed">
                  Displays Rayleigh-Jeans tail in mid-IR with molecular absorption bands (TiO, VO, FeH) in near-IR.
                </p>
              </div>

              <div className="bg-neutral-950 p-3 rounded-xl border border-neutral-800 space-y-2">
                <div className="font-semibold text-cyan-300 text-xs flex items-center justify-between">
                  <span>WISE 0855 (Sub-stellar Brown Dwarf)</span>
                  <span className="text-[10px] text-neutral-500 font-mono">Bands 5 &amp; 6</span>
                </div>
                <img
                  src="/science/wise_0855_spectrum.png"
                  alt="WISE 0855 SPHEREx Spectrum"
                  className="w-full rounded-lg border border-neutral-800 bg-neutral-900"
                />
                <p className="text-[11px] text-neutral-400 leading-relaxed">
                  Exhibits deep H₂O and CH₄ suppression below 2.5 µm and strong 4.5–4.9 µm atmospheric window emission.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Tab 3: Light Curves */}
        {activeTab === 'lightcurves' && (
          <div className="space-y-4">
            <p className="text-neutral-400 text-xs">
              Time-domain photometric light curves demonstrating variable star and accretion physics across SPHEREx survey epochs:
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="bg-neutral-950 p-3 rounded-xl border border-neutral-800 space-y-2">
                <div className="font-semibold text-cyan-300 text-xs flex items-center justify-between">
                  <span>RW Aurigae Light Curve (Band 2)</span>
                  <span className="text-[10px] text-neutral-500 font-mono">YSO Variability</span>
                </div>
                <img
                  src="/science/rw_aur_light_curve.png"
                  alt="RW Aurigae SPHEREx Light Curve"
                  className="w-full rounded-lg border border-neutral-800 bg-neutral-900"
                />
                <p className="text-[11px] text-neutral-400 leading-relaxed">
                  Reveals accretion variability and circumstellar dust occultation across observation baselines.
                </p>
              </div>

              <div className="bg-neutral-950 p-3 rounded-xl border border-neutral-800 space-y-2">
                <div className="font-semibold text-cyan-300 text-xs flex items-center justify-between">
                  <span>R Draconis Light Curve (Band 1)</span>
                  <span className="text-[10px] text-neutral-500 font-mono">Mira Pulsation</span>
                </div>
                <img
                  src="/science/r_dra_light_curve.png"
                  alt="R Draconis SPHEREx Light Curve"
                  className="w-full rounded-lg border border-neutral-800 bg-neutral-900"
                />
                <p className="text-[11px] text-neutral-400 leading-relaxed">
                  Captures large-amplitude stellar pulsations of an Asymptotic Giant Branch (AGB) pulsating red giant.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Tab 4: Stacking & Co-addition */}
        {activeTab === 'stacking' && (
          <div className="space-y-4">
            <p className="text-neutral-400 text-xs">
              Frame stacking engine validation demonstrating theoretical SNR improvement and outlier rejection:
            </p>

            <div className="bg-neutral-950 p-4 rounded-xl border border-neutral-800 space-y-3">
              <div className="font-semibold text-cyan-300 text-xs flex items-center justify-between">
                <span>Signal-to-Noise Ratio (SNR) Boost &amp; Outlier Rejection Demonstration</span>
                <span className="text-[10px] font-mono text-cyan-400">SNR ∝ √N</span>
              </div>
              <img
                src="/science/stacking_demonstration.png"
                alt="Stacking and SNR Demonstration"
                className="w-full rounded-lg border border-neutral-800 bg-neutral-900"
              />
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2 text-[11px] font-mono">
                <div className="bg-neutral-900 p-2.5 rounded border border-neutral-800 space-y-1">
                  <div className="text-cyan-400 font-semibold">1. Single Epoch:</div>
                  <div className="text-neutral-400">Dominated by zodiacal noise and background variance.</div>
                </div>
                <div className="bg-neutral-900 p-2.5 rounded border border-neutral-800 space-y-1">
                  <div className="text-cyan-400 font-semibold">2. Median Co-add:</div>
                  <div className="text-neutral-400">Rejects cosmic rays, hot pixels, and transient glitches.</div>
                </div>
                <div className="bg-neutral-900 p-2.5 rounded border border-neutral-800 space-y-1">
                  <div className="text-cyan-400 font-semibold">3. Shift-and-Stack:</div>
                  <div className="text-neutral-400">Aligns high-PM bodies to discover faint moving objects.</div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="pt-3 border-t border-neutral-800 flex items-center justify-between text-neutral-500 text-[11px] font-mono">
          <span>NASA Space Apps 2026 &bull; Team Planet X &amp; SPHEREx</span>
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-lg bg-neutral-800 hover:bg-neutral-700 text-neutral-200 text-xs font-medium transition"
          >
            Close Dossier
          </button>
        </div>
      </div>
    </div>
  );
};
