import React from 'react';
import { ExternalLink } from 'lucide-react';

export const Footer: React.FC = () => {
  return (
    <footer className="border-t border-neutral-800/80 bg-neutral-950 py-6 px-4 mt-auto">
      <div className="max-w-7xl mx-auto space-y-4">
        {/* Required IRSA Acknowledgement (Section 13) */}
        <div className="bg-neutral-900/60 border border-neutral-800 rounded-lg p-3 text-xs text-neutral-400 leading-relaxed font-sans">
          <strong className="text-neutral-300 block mb-1">IRSA Acknowledgment:</strong>
          &ldquo;This publication makes use of data products from the Spectro-Photometer for the History of the Universe, Epoch of Reionization and Ices Explorer (SPHEREx), which is a joint project of the Jet Propulsion Laboratory and the California Institute of Technology, and is funded by the National Aeronautics and Space Administration.&rdquo;
        </div>

        {/* Resources & Team Role Information */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-neutral-500">
          <div>
            SPHEREx Sky Viewer — NASA Space Apps Challenge 2026: <em>Planet X and SPHEREx</em>
          </div>
          <div className="flex items-center gap-4">
            <a
              href="https://irsa.ipac.caltech.edu/Missions/spherex.html"
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1 hover:text-neutral-300 transition"
            >
              IRSA SPHEREx <ExternalLink className="w-3 h-3" />
            </a>
            <a
              href="https://caltech-ipac.github.io/irsa-tutorials/spherex"
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1 hover:text-neutral-300 transition"
            >
              Tutorials <ExternalLink className="w-3 h-3" />
            </a>
            <a
              href="https://byw.tools/wiseview"
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1 hover:text-neutral-300 transition"
            >
              WiseView <ExternalLink className="w-3 h-3" />
            </a>
          </div>
        </div>
      </div>
    </footer>
  );
};
