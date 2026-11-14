// SPHEREx Sky Viewer - Type Definitions
// Strictly aligned with Build Plan (Section 7 API Contract)

export type SpherexBand =
  | 'SPHEREx-D1'
  | 'SPHEREx-D2'
  | 'SPHEREx-D3'
  | 'SPHEREx-D4'
  | 'SPHEREx-D5'
  | 'SPHEREx-D6';

// Configurable default band. Notice: Which detector shows WISE 0855 or other targets
// is an open check in Section 3, pending Member 1's verification.
export const DEFAULT_BAND: SpherexBand = 'SPHEREx-D1';

export interface BandInfo {
  id: SpherexBand;
  detectorNumber: number;
  wavelengthRange: [number, number]; // [min, max] in microns
  label: string;
}

export const SPHEREX_BANDS: Record<SpherexBand, BandInfo> = {
  'SPHEREx-D1': { id: 'SPHEREx-D1', detectorNumber: 1, wavelengthRange: [0.75, 1.1], label: 'D1 (0.75 - 1.1 µm)' },
  'SPHEREx-D2': { id: 'SPHEREx-D2', detectorNumber: 2, wavelengthRange: [1.1, 1.6], label: 'D2 (1.1 - 1.6 µm)' },
  'SPHEREx-D3': { id: 'SPHEREx-D3', detectorNumber: 3, wavelengthRange: [1.6, 2.4], label: 'D3 (1.6 - 2.4 µm)' },
  'SPHEREx-D4': { id: 'SPHEREx-D4', detectorNumber: 4, wavelengthRange: [2.4, 3.8], label: 'D4 (2.4 - 3.8 µm)' },
  'SPHEREx-D5': { id: 'SPHEREx-D5', detectorNumber: 5, wavelengthRange: [3.8, 4.4], label: 'D5 (3.8 - 4.4 µm)' },
  'SPHEREx-D6': { id: 'SPHEREx-D6', detectorNumber: 6, wavelengthRange: [4.4, 5.0], label: 'D6 (4.4 - 5.0 µm)' },
};

export interface WcsInfo {
  crval: [number, number]; // [RA_deg, Dec_deg]
  crpix: [number, number]; // [X_pix, Y_pix]
  cdelt: [number, number]; // [deg/pixel_x, deg/pixel_y]
  ctype: [string, string]; // ['RA---TAN', 'DEC--TAN']
}

export interface SpherexFrame {
  index: number;
  mjd: number; // Observation time
  dateUtc: string; // ISO date string
  wavelengthMicrons: number; // Central wavelength in microns
  band: SpherexBand;
  width: number;
  height: number;
  flux: Float32Array; // Real pixel values
  flags?: Uint8Array; // Bad pixel flags (0 = good)
  minFlux: number;
  maxFlux: number;
}

export interface CatalogMarker {
  id: string;
  ra: number;
  dec: number;
  label?: string;
}

// Section 7 API Response Contract
export interface SpherexApiResponse {
  target: {
    ra: number;
    dec: number;
    name?: string;
  };
  fovDegrees: number;
  band: SpherexBand;
  dataRelease: string;
  wcs: WcsInfo;
  frameCount: number;
  frames: SpherexFrame[];
  markers?: CatalogMarker[];
  isSampleData?: boolean;
}

export type StretchType = 'linear' | 'log';

// 5 Test Targets from Challenge
export interface TargetPreset {
  name: string;
  ra: number;
  dec: number;
  defaultFov: number;
}

export const TEST_TARGETS: TargetPreset[] = [
  { name: 'WISE 0855', ra: 133.795129, dec: -7.245147, defaultFov: 0.05 },
  { name: "Barnard's Star", ra: 269.452075, dec: 4.693364, defaultFov: 0.05 },
  { name: 'Epsilon Indi B', ra: 330.8402, dec: -56.7865, defaultFov: 0.05 },
  { name: 'RW Aurigae', ra: 77.1082, dec: 30.4014, defaultFov: 0.05 },
  { name: 'R Draconis', ra: 247.5544, dec: 66.7029, defaultFov: 0.05 },
];
