# SPHEREx Sky Viewer — Milestone 2.3.1: Live API Error Triage Report

**Date**: 2026-11-14
**Author**: Member 1 (Data, Processing, and Release)
**Status**: Resolved & Verified
**Milestone Scope**: Triage and eliminate backend `HTTP 502 Failed to query IRSA observation archive: 'str' object has no attribute 'get'` exception observed during frontend integration for arbitrary coordinates (`ra=0.0, dec=0.0`).

---

## 1. Executive Summary

During Milestone 2.3 frontend integration testing, querying arbitrary un-cached sky coordinates (`ra=0.0, dec=0.0`) yielded an unhandled backend exception:
```
HTTP 502 Bad Gateway
detail: "Failed to query IRSA observation archive: 'str' object has no attribute 'get'"
```
Preset targets (e.g., WISE 0855) worked seamlessly because their candidate metadata was pre-populated in `targets_tap_cache.json` as normalized Python dictionaries. However, any un-cached coordinate cone query triggered a live TAP query against IRSA, exposing an unexpected IVOA VOTable JSON envelope format.

The root cause was pinpointed, a robust VOTable JSON parser and defensive type guards were implemented in `backend/app/services/selector.py`, and comprehensive unit/integration tests were added. All 61 backend tests pass, frontend lint passes with 0 errors, and the frontend builds cleanly with 0 errors.

---

## 2. Root Cause Analysis

### 2.1 The Vulnerability Chain

1. **Trigger Condition**:
   When `ra=0.0, dec=0.0` is queried, `get_target_name_if_preset(0.0, 0.0)` returns `None`, and no local cache file exists in `backend/cache/tap/`.
2. **IRSA TAP Behavior**:
   `query_irsa_tap_for_target` executes an ADQL cone query to `https://irsa.ipac.caltech.edu/TAP/sync` with `FORMAT=json`.
3. **Response Envelope**:
   Unlike standard REST APIs or TAP endpoints returning flat tabular JSON `{"data": [...], "metadata": [...]}`, IRSA returns an IVOA VOTable structure wrapped in JSON:
   ```json
   {
     "VOTABLE": {
       "RESOURCE_ARRAY": [
         {
           "TABLE": {
             "FIELD_ARRAY": [
               {"<xmlattr>": {"name": "obs_id"}},
               {"<xmlattr>": {"name": "energy_bandpassname"}},
               ...
             ],
             "DATA": {
               "TABLEDATA": [
                 ["2025W25_1B_0085_1", "SPHEREx-D1", ...],
                 ...
               ]
             }
           }
         }
       ]
     }
   }
   ```
4. **The Crash**:
   The previous fallback in `query_irsa_tap_for_target` did not recognize `"VOTABLE"` and fell through to:
   ```python
   else:
       records = data  # assigns the top-level dict {"VOTABLE": {...}}
   ```
   When `select_observations_for_target` subsequently executed:
   ```python
   matching_records = [
       r for r in records
       if r.get("energy_bandpassname") == band
   ]
   ```
   Iterating over a Python `dict` yields its string keys (`r = 'VOTABLE'`).
   Evaluating `'VOTABLE'.get(...)` raised:
   ```
   AttributeError: 'str' object has no attribute 'get'
   ```
   In `backend/app/routers/frames.py`, this was caught and re-raised as HTTP 502 Bad Gateway.

---

## 3. Implementation Details & Fix

### 3.1 Parser Implementation (`backend/app/services/selector.py`)

Added `parse_tap_json_response(data: Any) -> List[Dict[str, Any]]`:
- **Pre-parsed Row Lists**: Passthrough for internal cached data or test fixtures, filtering out non-dict elements.
- **Standard TAP JSON**: Extracts column names from `metadata` and maps them to row tuples in `data`.
- **IVOA VOTable JSON**:
  - Traverses `VOTABLE -> RESOURCE_ARRAY -> TABLE`.
  - Extracts column names from `FIELD_ARRAY[i]["<xmlattr>"]["name"]` (falling back to `FIELD_ARRAY[i]["name"]` or positional indexes).
  - Pairs column names with cell values in `DATA.TABLEDATA`.
- **Defensive Fallback**: Returns `[]` with a clear warning log for malformed or unrecognized structures without crashing.

### 3.2 In-depth Defensive Guards

1. **Applied across all cache tiers**:
   - `parse_tap_json_response` is called when reading `backend/cache/tap/`, when reading `targets_tap_cache.json`, and on live HTTP 200 responses.
2. **Type Guard in Observation Selection**:
   In `select_observations_for_target`:
   ```python
   matching_records = [
       r for r in records
       if isinstance(r, dict) and r.get("energy_bandpassname") == band
   ]
   ```
   Ensures that even if arbitrary non-dict elements are passed in `cached_records`, they are safely ignored.

---

## 4. Verification Evidence

### 4.1 Backend Test Suite (Pytest)

Ran full backend test suite:
```
============================= test session starts =============================
platform win32 -- Python 3.13.3, pytest-9.0.2, pluggy-1.6.0
rootdir: D:\Projects\sphereX
collected 61 items

backend/tests/test_api_schema.py::test_spherex_api_response_schema PASSED [  1%]
backend/tests/test_api_schema.py::test_json_no_nan_or_infinity_tokens PASSED [  3%]
backend/tests/test_endpoints.py::test_get_health_endpoint PASSED         [  4%]
backend/tests/test_endpoints.py::test_get_frames_invalid_band PASSED     [  6%]
backend/tests/test_endpoints.py::test_get_frames_invalid_coordinates PASSED [  8%]
backend/tests/test_endpoints.py::test_get_frames_target_not_found PASSED [  9%]
backend/tests/test_endpoints.py::test_get_frames_deterministic_synthetic_flow PASSED [ 11%]
backend/tests/test_endpoints.py::test_offline_real_cutout_smoke_test PASSED [ 13%]
backend/tests/test_endpoints.py::test_get_frames_cache_aware_real_multi_epoch_return PASSED [ 14%]
backend/tests/test_endpoints.py::test_get_frames_offline_resilience PASSED [ 16%]
backend/tests/test_endpoints.py::test_get_frames_votable_tap_response_end_to_end PASSED [ 18%]
...
backend/tests/test_selector.py::test_parse_tap_json_response_votable_format PASSED [ 95%]
backend/tests/test_selector.py::test_parse_tap_json_response_standard_format PASSED [ 96%]
backend/tests/test_selector.py::test_parse_tap_json_response_list_and_malformed_inputs PASSED [ 98%]
backend/tests/test_selector.py::test_selector_ignores_non_dict_records_without_crashing PASSED [100%]

============================= 61 passed in 1.14s ==============================
```

### 4.2 Reproduction Verification for `ra=0.0, dec=0.0`

Executed live cone query for `(0.0, 0.0)`:
```
--- Testing query_irsa_tap_for_target(0.0, 0.0) ---
Type of records: <class 'list'>
Records length: 223
First 2 records: [
  {'obs_id': '2025W25_1B_0085_1', 'obs_collection': 'spherex_dr1', 'energy_bandpassname': 'SPHEREx-D4', ...},
  {'obs_id': '2025W25_1B_0085_1', 'obs_collection': 'spherex_dr1', 'energy_bandpassname': 'SPHEREx-D1', ...}
]
```
Executed `select_observations_for_target(0.0, 0.0, band='SPHEREx-D1', max_frames=3)`:
- Selected 3 valid, distinct observations:
  - `2025W25_1B_0085_1` (MJD 60842.377974)
  - `2025W25_1B_0085_2` (MJD 60842.379466)
  - `2025W25_1B_0085_3` (MJD 60842.380958)
- Zero exceptions, strict chronological ordering maintained.

### 4.3 Frontend Lint & Build Integrity

- **Lint (`npm run lint`)**: 0 errors (2 pre-existing warnings in `AladinSkyPicker.tsx` and `App.tsx`).
- **Build (`npm run build`)**: Built in 570ms with zero errors.

---

## 5. Required Observations

### Observation A: Temporal Coverage Reality
During the live integration tests in Milestone 2.3, the cache-aware selector returned three distinct observations for WISE 0855 in band `SPHEREx-D6`:
1. `2025W19_1B_0116_1` (MJD ~60799.988)
2. `2025W19_1B_0116_2` (MJD ~60799.990)
3. `2025W19_1B_0138_1` (MJD ~60800.122)

**Critical Scientific Finding**:
All three observations were taken on **May 5, 2025 within ~3.2 hours of each other** (short-term scan cadence).
- *Scientific Assessment*: While this validates multi-exposure retrieval, WCS alignment, and reprojection fidelity, **3.2 hours is insufficient to visually reveal proper motion** for WISE 0855 (~8 arcsec/yr, requiring multiple months for a multi-pixel displacement).
- *Recommendation*: For motion-detection demonstration, candidate selection should be expanded in Milestone 2.4 / 3 to enforce epoch-spaced selection across survey passes (e.g., May 2025 vs. November/December 2025). We record this factual temporal coverage accurately without redesigning the selector in this triage milestone.

### Observation B: Working Tree State
- `git status --short`:
  ```
   M package-lock.json
   M src/App.tsx
   M src/services/apiClient.ts
   M src/types/spherex.ts
   M src/utils/urlState.ts
   M vite.config.ts
  ?? backend/
  ?? docs/
  ```
- **Integrity Statement**:
  - Member 2's UI player components (`FrameCanvas.tsx`, `PlayerControls.tsx`, `MetadataPanel.tsx`) remain 100% untouched.
  - Zero commits, pushes, branch creations, or Git history modifications were made.
  - No new external packages were installed.
  - All backend code and tests remain in untracked `backend/`, and documentation reports in untracked `docs/`.

---

## 6. Conclusion & Recommended Next Step

Milestone 2.3.1 successfully resolved the live TAP query failure, hardened IRSA response parsing against arbitrary VOTable JSON payloads, and proved end-to-end resilience.

**Recommended Next Milestone**:
**Milestone 2.4** (Performance Optimization, Latency Profiling, and Epoch Spacing) to establish epoch-spaced observation selection for moving target verification, followed by the single-command demo.
