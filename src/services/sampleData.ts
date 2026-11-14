// DISABLED FOR SCIENTIFIC SUBMISSIONS: Fabricated synthetic astronomy
// must never be displayed in place of real SPHEREx observations.
// Member 1's FastAPI backend serves real Level 2 observations exclusively.

import type { SpherexApiResponse, SpherexBand } from '../types/spherex';

export function getSampleMovingDotData(
  _ra = 133.795129,
  _dec = -7.245147,
  _band: SpherexBand = 'SPHEREx-D1'
): SpherexApiResponse {
  throw new Error(
    'Fabricated sample data is disabled. The SPHEREx viewer exclusively displays real Level 2 observations from Member 1 API.'
  );
}
