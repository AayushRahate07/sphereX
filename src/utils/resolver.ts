// Target Coordinate & Name Resolver
// Supports decimal coordinates, sexagesimal strings, local catalog lookup, and CDS Sesame.

import { TEST_TARGETS } from '../types/spherex';

export interface ResolvedTarget {
  ra: number;
  dec: number;
  name: string;
}

const COMMON_ASTRONOMICAL_TARGETS: Record<string, { ra: number; dec: number; name: string }> = {
  'wise 0855': { ra: 133.795129, dec: -7.245147, name: 'WISE 0855−0714' },
  'wise0855': { ra: 133.795129, dec: -7.245147, name: 'WISE 0855−0714' },
  "barnard's star": { ra: 269.452075, dec: 4.693364, name: "Barnard's Star" },
  'barnard': { ra: 269.452075, dec: 4.693364, name: "Barnard's Star" },
  'barnards star': { ra: 269.452075, dec: 4.693364, name: "Barnard's Star" },
  'epsilon indi b': { ra: 330.8402, dec: -56.7865, name: 'Epsilon Indi B' },
  'eps indi b': { ra: 330.8402, dec: -56.7865, name: 'Epsilon Indi B' },
  'rw aurigae': { ra: 77.1082, dec: 30.4014, name: 'RW Aurigae' },
  'rw aur': { ra: 77.1082, dec: 30.4014, name: 'RW Aurigae' },
  'r draconis': { ra: 247.5544, dec: 66.7029, name: 'R Draconis' },
  'r dra': { ra: 247.5544, dec: 66.7029, name: 'R Draconis' },
  'trappist-1': { ra: 346.622, dec: -5.041, name: 'TRAPPIST-1' },
  'proxima centauri': { ra: 217.4289, dec: -62.679, name: 'Proxima Centauri' },
  'sirius': { ra: 101.287, dec: -16.716, name: 'Sirius' },
  'vega': { ra: 279.2347, dec: 38.7837, name: 'Vega' },
  'betelgeuse': { ra: 88.7929, dec: 7.407, name: 'Betelgeuse' },
  'm31': { ra: 10.6847, dec: 41.2687, name: 'Andromeda Galaxy (M31)' },
  'andromeda': { ra: 10.6847, dec: 41.2687, name: 'Andromeda Galaxy (M31)' },
  'm42': { ra: 83.822, dec: -5.391, name: 'Orion Nebula (M42)' },
  'crab nebula': { ra: 83.633, dec: 22.014, name: 'Crab Nebula (M1)' },
};

export async function resolveTargetQuery(query: string): Promise<ResolvedTarget | null> {
  const trimmed = query.trim();
  if (!trimmed) return null;

  const lower = trimmed.toLowerCase();

  // 1. Direct dictionary match
  if (COMMON_ASTRONOMICAL_TARGETS[lower]) {
    return COMMON_ASTRONOMICAL_TARGETS[lower];
  }

  // 2. Test Targets match
  const testMatch = TEST_TARGETS.find(
    (t) => t.name.toLowerCase() === lower || t.name.toLowerCase().includes(lower)
  );
  if (testMatch) {
    return { ra: testMatch.ra, dec: testMatch.dec, name: testMatch.name };
  }

  // 3. Decimal coordinates (e.g. "133.795, -7.245" or "133.795 -7.245")
  const decimalMatch = trimmed.match(/^([-+]?\d*\.?\d+)[,\s]+([-+]?\d*\.?\d+)$/);
  if (decimalMatch) {
    const ra = parseFloat(decimalMatch[1]);
    const dec = parseFloat(decimalMatch[2]);
    if (!isNaN(ra) && !isNaN(dec) && ra >= 0 && ra <= 360 && dec >= -90 && dec <= 90) {
      return { ra: +ra.toFixed(6), dec: +dec.toFixed(6), name: `RA ${ra.toFixed(4)}°, Dec ${dec.toFixed(4)}°` };
    }
  }

  // 4. Sexagesimal coordinates (e.g. "08h55m10.8s -07d14m42.5s" or "08:55:10.8 -07:14:42.5")
  const sexaMatch = trimmed.match(
    /^(\d{1,2})[h:\s]+(\d{1,2})[m:\s]+(\d{1,2}(?:\.\d+)?)[s,\s]+([-+]?\d{1,2})[d:\s]+(\d{1,2})[m:\s]+(\d{1,2}(?:\.\d+)?)/i
  );
  if (sexaMatch) {
    const rh = parseFloat(sexaMatch[1]);
    const rm = parseFloat(sexaMatch[2]);
    const rs = parseFloat(sexaMatch[3]);
    const dSign = sexaMatch[4].startsWith('-') ? -1 : 1;
    const dd = Math.abs(parseFloat(sexaMatch[4]));
    const dm = parseFloat(sexaMatch[5]);
    const ds = parseFloat(sexaMatch[6]);

    const raDeg = (rh + rm / 60 + rs / 3600) * 15;
    const decDeg = dSign * (dd + dm / 60 + ds / 3600);
    return {
      ra: +raDeg.toFixed(6),
      dec: +decDeg.toFixed(6),
      name: `Sexagesimal: ${trimmed}`,
    };
  }

  // 5. Query CDS Sesame service with timeout
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 3500);
    const url = `https://cdsweb.u-strasbg.fr/cgi-bin/nph-sesame/-oI/A?${encodeURIComponent(trimmed)}`;
    const res = await fetch(url, { signal: controller.signal });
    clearTimeout(timeout);

    if (res.ok) {
      const text = await res.text();
      const jMatch = text.match(/%J\s+([\d.]+)\s+([+-]?[\d.]+)/);
      if (jMatch) {
        return {
          ra: parseFloat(jMatch[1]),
          dec: parseFloat(jMatch[2]),
          name: trimmed,
        };
      }
    }
  } catch {
    // Network or CORS error ignored
  }

  return null;
}
