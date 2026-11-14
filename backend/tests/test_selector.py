"""Unit tests for Observation Selection, Validation, and Duplicate Handling."""

from typing import Any, Dict, List
import pytest

from backend.app.services.selector import (
    SelectedObservation,
    SelectionError,
    TargetNotFoundError,
    get_target_name_if_preset,
    parse_tap_json_response,
    select_epoch_spaced_observations,
    select_observations_for_target,
)


def test_preset_target_name_resolution():
    """Verify known challenge target coordinates resolve to canonical names."""
    assert get_target_name_if_preset(133.795129, -7.245147) == "WISE 0855"
    assert get_target_name_if_preset(269.452075, 4.693364) == "Barnard's Star"
    assert get_target_name_if_preset(330.8402, -56.7865) == "Epsilon Indi B"
    assert get_target_name_if_preset(0.0, 0.0) is None


def test_invalid_band_raises_selection_error(mock_tap_candidates: List[Dict[str, Any]]):
    """Unsupported bandpass must raise SelectionError."""
    with pytest.raises(SelectionError, match="Unsupported bandpass"):
        select_observations_for_target(
            ra=133.795,
            dec=-7.245,
            band="INVALID-BAND",
            cached_records=mock_tap_candidates,
        )


@pytest.mark.parametrize("bad_ra, bad_dec", [(-5.0, 0.0), (365.0, 0.0), (100.0, 95.0), (100.0, -95.0)])
def test_out_of_range_coordinates_raises_selection_error(bad_ra: float, bad_dec: float):
    """Invalid sky coordinates must raise SelectionError."""
    with pytest.raises(SelectionError, match="Coordinates out of range"):
        select_observations_for_target(ra=bad_ra, dec=bad_dec, band="SPHEREx-D1")


def test_target_not_found_raises_error(mock_tap_candidates: List[Dict[str, Any]]):
    """Selecting a band with zero observations must raise TargetNotFoundError."""
    # Mock records only have D6 and D1, requesting D2 will fail
    with pytest.raises(TargetNotFoundError, match="No observations found"):
        select_observations_for_target(
            ra=133.795,
            dec=-7.245,
            band="SPHEREx-D2",
            cached_records=mock_tap_candidates,
        )


def test_chronological_sorting(mock_tap_candidates: List[Dict[str, Any]]):
    """Selected observations must be sorted in strictly ascending MJD order."""
    # Create unordered records
    unordered = [
        {"obs_id": "LATER", "energy_bandpassname": "SPHEREx-D6", "t_min": 60900.0, "access_url": "url2"},
        {"obs_id": "EARLIER", "energy_bandpassname": "SPHEREx-D6", "t_min": 60800.0, "access_url": "url1"},
    ]
    results = select_observations_for_target(
        ra=133.795,
        dec=-7.245,
        band="SPHEREx-D6",
        cached_records=unordered,
    )
    assert len(results) == 2
    assert results[0].obs_id == "EARLIER"
    assert results[1].obs_id == "LATER"
    assert results[0].mjd < results[1].mjd


def test_duplicate_handling_preserves_distinct_exposures():
    """Preserve distinct multi-epoch exposures while removing exact identical duplicate rows."""
    candidates = [
        {"obs_id": "OBS_1", "energy_bandpassname": "SPHEREx-D6", "t_min": 60800.1, "access_url": "url1"},
        {"obs_id": "OBS_2", "energy_bandpassname": "SPHEREx-D6", "t_min": 60800.5, "access_url": "url2"},
        {"obs_id": "OBS_1", "energy_bandpassname": "SPHEREx-D6", "t_min": 60800.1, "access_url": "url1"},  # Exact dup
    ]
    results = select_observations_for_target(
        ra=133.795,
        dec=-7.245,
        band="SPHEREx-D6",
        cached_records=candidates,
    )
    # Distinct exposures OBS_1 and OBS_2 must both be present
    assert len(results) == 2
    assert [r.obs_id for r in results] == ["OBS_1", "OBS_2"]


def test_max_frames_cap():
    """Max frames cap must be respected."""
    many_records = [
        {"obs_id": f"OBS_{i}", "energy_bandpassname": "SPHEREx-D1", "t_min": 60800.0 + i, "access_url": f"url_{i}"}
        for i in range(25)
    ]
    results = select_observations_for_target(
        ra=100.0,
        dec=0.0,
        band="SPHEREx-D1",
        max_frames=5,
        cached_records=many_records,
    )
    assert len(results) == 5
    assert results[-1].obs_id == "OBS_4"


def test_cache_aware_selection_prioritizes_cached_observations():
    """When suitable cached observations exist, they must be prioritized over uncached ones."""
    records = [
        {"obs_id": f"OBS_{i}", "energy_bandpassname": "SPHEREx-D1", "t_min": 60800.0 + i, "access_url": f"url_{i}"}
        for i in range(10)
    ]
    # OBS_2 and OBS_7 are cached
    results = select_observations_for_target(
        ra=100.0,
        dec=0.0,
        band="SPHEREx-D1",
        max_frames=2,
        cached_records=records,
        cached_obs_ids={"OBS_2", "OBS_7"},
    )
    assert len(results) == 2
    assert [r.obs_id for r in results] == ["OBS_2", "OBS_7"]
    # Chronological ordering strictly preserved
    assert results[0].mjd < results[1].mjd


def test_cache_aware_selection_fills_shortfall_with_earliest_uncached():
    """If cached count is less than max_frames, fill shortfall with earliest uncached observations."""
    records = [
        {"obs_id": f"OBS_{i}", "energy_bandpassname": "SPHEREx-D1", "t_min": 60800.0 + i, "access_url": f"url_{i}"}
        for i in range(10)
    ]
    # Only OBS_5 is cached; requesting 3 frames
    results = select_observations_for_target(
        ra=100.0,
        dec=0.0,
        band="SPHEREx-D1",
        max_frames=3,
        cached_records=records,
        cached_obs_ids={"OBS_5"},
    )
    assert len(results) == 3
    # OBS_5 must be included, along with earliest uncached OBS_0 and OBS_1
    obs_ids = [r.obs_id for r in results]
    assert obs_ids == ["OBS_0", "OBS_1", "OBS_5"]
    assert results[0].mjd < results[1].mjd < results[2].mjd


def test_cache_aware_selection_with_empty_cache_returns_earliest_chronological():
    """When cache is empty, selection behaves as standard earliest-first chronological retrieval."""
    records = [
        {"obs_id": f"OBS_{i}", "energy_bandpassname": "SPHEREx-D1", "t_min": 60800.0 + i, "access_url": f"url_{i}"}
        for i in range(10)
    ]
    results = select_observations_for_target(
        ra=100.0,
        dec=0.0,
        band="SPHEREx-D1",
        max_frames=3,
        cached_records=records,
        cached_obs_ids=set(),
    )
    assert [r.obs_id for r in results] == ["OBS_0", "OBS_1", "OBS_2"]


def test_cache_aware_selection_all_candidates_when_max_frames_none():
    """When max_frames is None, return all distinct candidate observations sorted by MJD."""
    records = [
        {"obs_id": f"OBS_{i}", "energy_bandpassname": "SPHEREx-D1", "t_min": 60850.0 - i, "access_url": f"url_{i}"}
        for i in range(8)
    ]
    results = select_observations_for_target(
        ra=100.0,
        dec=0.0,
        band="SPHEREx-D1",
        max_frames=None,
        cached_records=records,
    )
    assert len(results) == 8
    # Must be sorted in ascending chronological order
    mjds = [r.mjd for r in results]
    assert mjds == sorted(mjds)


def test_parse_tap_json_response_votable_format():
    """Verify parsing of real IRSA VOTable JSON response envelope."""
    votable_payload = {
        "VOTABLE": {
            "RESOURCE_ARRAY": [
                {
                    "TABLE": {
                        "FIELD_ARRAY": [
                            {"<xmlattr>": {"name": "obs_id"}},
                            {"<xmlattr>": {"name": "energy_bandpassname"}},
                            {"<xmlattr>": {"name": "t_min"}},
                            {"<xmlattr>": {"name": "access_url"}},
                        ],
                        "DATA": {
                            "TABLEDATA": [
                                ["OBS_VOT_1", "SPHEREx-D1", 60800.1, "https://irsa.ipac.caltech.edu/cutout1"],
                                ["OBS_VOT_2", "SPHEREx-D6", 60800.5, "https://irsa.ipac.caltech.edu/cutout2"],
                            ]
                        },
                    }
                }
            ]
        }
    }
    records = parse_tap_json_response(votable_payload)
    assert len(records) == 2
    assert records[0] == {
        "obs_id": "OBS_VOT_1",
        "energy_bandpassname": "SPHEREx-D1",
        "t_min": 60800.1,
        "access_url": "https://irsa.ipac.caltech.edu/cutout1",
    }
    assert records[1]["obs_id"] == "OBS_VOT_2"
    assert records[1]["energy_bandpassname"] == "SPHEREx-D6"


def test_parse_tap_json_response_standard_format():
    """Verify parsing of standard TAP JSON format (data and metadata)."""
    standard_payload = {
        "metadata": [{"name": "obs_id"}, {"name": "energy_bandpassname"}, {"name": "t_min"}],
        "data": [
            ["OBS_STD_1", "SPHEREx-D1", 60810.0],
            ["OBS_STD_2", "SPHEREx-D2", 60811.0],
        ],
    }
    records = parse_tap_json_response(standard_payload)
    assert len(records) == 2
    assert records[0] == {"obs_id": "OBS_STD_1", "energy_bandpassname": "SPHEREx-D1", "t_min": 60810.0}
    assert records[1] == {"obs_id": "OBS_STD_2", "energy_bandpassname": "SPHEREx-D2", "t_min": 60811.0}


def test_parse_tap_json_response_list_and_malformed_inputs():
    """Verify graceful handling of list of dicts, non-dict records, and invalid structures."""
    # Pre-parsed list of dicts with stray non-dict
    records = parse_tap_json_response([{"obs_id": "OBS_1"}, "invalid_str", None, {"obs_id": "OBS_2"}])
    assert records == [{"obs_id": "OBS_1"}, {"obs_id": "OBS_2"}]

    # Malformed / unexpected types
    assert parse_tap_json_response("not_json") == []
    assert parse_tap_json_response(12345) == []
    assert parse_tap_json_response({}) == []
    assert parse_tap_json_response({"unknown_key": "unknown_value"}) == []


def test_selector_ignores_non_dict_records_without_crashing():
    """select_observations_for_target must safely ignore stray non-dict elements without raising AttributeError."""
    mixed_records = [
        "VOTABLE",  # The exact string that caused the original bug
        {"obs_id": "OBS_VALID", "energy_bandpassname": "SPHEREx-D1", "t_min": 60800.0, "access_url": "url"},
        42,
    ]
    results = select_observations_for_target(
        ra=100.0,
        dec=0.0,
        band="SPHEREx-D1",
        cached_records=mixed_records,  # type: ignore[arg-type]
    )
    assert len(results) == 1
    assert results[0].obs_id == "OBS_VALID"


def test_select_epoch_spaced_observations_spacing():
    """Verify deterministic epoch-spacing spreads frames evenly across available timeline."""
    obs_list = [
        SelectedObservation(
            obs_id=f"OBS_{i}",
            band="SPHEREx-D6",
            mjd=60800.0 + i * 10.0,
            exptime=113.6,
            access_url=f"url_{i}",
            s_ra=100.0,
            s_dec=0.0,
        )
        for i in range(10)  # OBS_0 to OBS_9 (MJD 60800.0 to 60890.0)
    ]

    # Spacing 3 frames across 10 candidates -> indices 0, 4, 9
    spaced_3 = select_epoch_spaced_observations(obs_list, 3)
    assert len(spaced_3) == 3
    assert [o.obs_id for o in spaced_3] == ["OBS_0", "OBS_4", "OBS_9"]
    assert spaced_3[0].mjd < spaced_3[1].mjd < spaced_3[2].mjd

    # Spacing 5 frames across 10 candidates -> indices 0, 2, 4, 7, 9
    spaced_5 = select_epoch_spaced_observations(obs_list, 5)
    assert len(spaced_5) == 5
    assert [o.obs_id for o in spaced_5] == ["OBS_0", "OBS_2", "OBS_4", "OBS_7", "OBS_9"]

    # Boundary cases: count = 1
    spaced_1 = select_epoch_spaced_observations(obs_list, 1)
    assert len(spaced_1) == 1
    assert spaced_1[0].obs_id == "OBS_0"

    # Count exceeds candidate count: returns all candidates unchanged
    spaced_all = select_epoch_spaced_observations(obs_list, 15)
    assert len(spaced_all) == 10
    assert [o.obs_id for o in spaced_all] == [f"OBS_{i}" for i in range(10)]


def test_cache_aware_selection_spaces_across_cached_observations():
    """When cached observations exceed max_frames, selection spaces across the cached baseline."""
    candidates = [
        {"obs_id": f"OBS_{i}", "energy_bandpassname": "SPHEREx-D6", "t_min": 60800.0 + i * 10.0, "access_url": f"url_{i}"}
        for i in range(10)
    ]
    # Say OBS_1, OBS_4, OBS_8 are cached (spanning MJD 60810, 60840, 60880)
    results = select_observations_for_target(
        ra=100.0,
        dec=0.0,
        band="SPHEREx-D6",
        max_frames=2,
        cached_records=candidates,
        cached_obs_ids={"OBS_1", "OBS_4", "OBS_8"},
    )
    # Spacing 2 frames across [OBS_1, OBS_4, OBS_8] -> indices 0 and 2 -> OBS_1 and OBS_8
    assert len(results) == 2
    assert [r.obs_id for r in results] == ["OBS_1", "OBS_8"]
    assert results[0].mjd < results[1].mjd
