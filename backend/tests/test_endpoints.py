"""Integration tests for FastAPI endpoints: /api/health and /api/frames."""

import io
from pathlib import Path
from unittest.mock import MagicMock, patch
from astropy.io import fits
from fastapi.testclient import TestClient
import numpy as np
import pytest

from backend.app.main import app
from backend.app.services.selector import SelectedObservation

client = TestClient(app)


def test_get_health_endpoint():
    """GET /api/health must return HTTP 200 with service metadata and cache stats."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.1.0"
    assert "timestampUtc" in data
    assert "SPHEREx-D1" in data["supportedBands"]
    assert "cache" in data
    assert "cachedFitsFiles" in data["cache"]


def test_get_frames_invalid_band():
    """GET /api/frames with unsupported band must return HTTP 400."""
    response = client.get("/api/frames?ra=133.795&dec=-7.245&band=INVALID")
    assert response.status_code == 400
    assert "Unsupported bandpass" in response.json()["detail"]


def test_get_frames_invalid_coordinates():
    """GET /api/frames with out-of-range coordinates must return HTTP 422 or 400."""
    response = client.get("/api/frames?ra=400.0&dec=-7.245&band=SPHEREx-D1")
    assert response.status_code == 422  # FastAPI query validation bounds


def test_get_frames_target_not_found():
    """GET /api/frames for empty target area must return HTTP 404."""
    with patch("backend.app.routers.frames.select_observations_for_target") as mock_select:
        from backend.app.services.selector import TargetNotFoundError
        mock_select.side_effect = TargetNotFoundError("No observations found")
        response = client.get("/api/frames?ra=10.0&dec=10.0&band=SPHEREx-D1")
        assert response.status_code == 404
        assert "No observations found" in response.json()["detail"]


def test_get_frames_deterministic_synthetic_flow(
    tmp_path: Path,
    synthetic_fits_epoch1: fits.HDUList,
    synthetic_fits_epoch2: fits.HDUList,
):
    """End-to-end integration test of /api/frames using deterministic synthetic fixtures."""
    # Write synthetic FITS cutouts to temporary disk cache
    f1_path = tmp_path / "epoch1.fits"
    f2_path = tmp_path / "epoch2.fits"
    synthetic_fits_epoch1.writeto(f1_path)
    synthetic_fits_epoch2.writeto(f2_path)

    obs1 = SelectedObservation(
        obs_id="SYNTH_EPOCH1",
        band="SPHEREx-D6",
        mjd=60800.1,
        exptime=113.6,
        access_url="mock_url_1",
        s_ra=133.795,
        s_dec=-7.245,
    )
    obs2 = SelectedObservation(
        obs_id="SYNTH_EPOCH2",
        band="SPHEREx-D6",
        mjd=60845.2,
        exptime=113.6,
        access_url="mock_url_2",
        s_ra=133.805,
        s_dec=-7.240,
    )

    with patch("backend.app.routers.frames.select_observations_for_target", return_value=[obs1, obs2]):
        with patch("backend.app.routers.frames.batch_retrieve_cutouts", return_value={"SYNTH_EPOCH1": f1_path, "SYNTH_EPOCH2": f2_path}):
            response = client.get("/api/frames?ra=133.795129&dec=-7.245147&band=SPHEREx-D6&size=0.05")
            assert response.status_code == 200
            data = response.json()

            # Target & release
            assert data["target"]["ra"] == pytest.approx(133.795129)
            assert data["target"]["dec"] == pytest.approx(-7.245147)
            assert data["target"]["name"] == "WISE 0855"  # Preset match
            assert data["band"] == "SPHEREx-D6"
            assert data["dataRelease"] == "DR1"
            assert data["fovDegrees"] == pytest.approx(0.05)
            assert data["frameCount"] == 2
            assert len(data["frames"]) == 2

            # Common WCS
            wcs = data["wcs"]
            assert len(wcs["crval"]) == 2
            assert len(wcs["crpix"]) == 2
            assert wcs["ctype"] == ["RA---TAN", "DEC--TAN"]

            # Frames validation
            for idx, frame in enumerate(data["frames"]):
                assert frame["index"] == idx
                assert frame["width"] == 29
                assert frame["height"] == 29
                assert frame["band"] == "SPHEREx-D6"
                assert len(frame["flux"]) == 29 * 29
                assert len(frame["flags"]) == 29 * 29
                assert not any(np.isnan(frame["flux"]))
                # Flags must be strictly 0 or 1
                assert set(frame["flags"]).issubset({0, 1})
                assert frame["minFlux"] <= frame["maxFlux"]

            # Markers
            assert data["markers"] is not None
            assert len(data["markers"]) >= 1
            assert data["markers"][0]["id"] == "target_nominal"


def test_offline_real_cutout_smoke_test(tmp_path: Path):
    """Smoke test using the real downloaded Level 2 cutout if present in cache or scratch."""
    from backend.app.config import FITS_CACHE_DIR, SCRATCH_DIR
    real_cutout = FITS_CACHE_DIR / "spherex_dr1_2025W46_1A_0076_3_SPHEREx-D6_133.7604_-7.2423_0.0500.fits"
    obs_id = "2025W46_1A_0076_3"
    if not real_cutout.exists():
        real_cutout = SCRATCH_DIR / "benchmark_2025W46_1A_0075_4.fits"
        obs_id = "2025W46_1A_0075_4"
    if not real_cutout.exists():
        pytest.skip("Pre-cached real cutout not found in cache or scratch directory.")

    obs = SelectedObservation(
        obs_id=obs_id,
        band="SPHEREx-D6",
        mjd=60989.301533,
        exptime=118.18,
        access_url="mock_access",
        s_ra=133.058,
        s_dec=-8.739,
    )

    with patch("backend.app.routers.frames.select_observations_for_target", return_value=[obs]):
        with patch("backend.app.routers.frames.batch_retrieve_cutouts", return_value={obs_id: real_cutout}):
            response = client.get("/api/frames?ra=133.795129&dec=-7.245147&band=SPHEREx-D6&size=0.05")
            assert response.status_code == 200
            data = response.json()
            assert data["frameCount"] == 1
            f0 = data["frames"][0]
            assert f0["width"] == 29
            assert f0["height"] == 29
            assert len(f0["flux"]) == 841
            assert len(f0["flags"]) == 841
            # Invalid flags should account for boundary/corner pixels (< 25% of grid)
            invalid_count = sum(f0["flags"])
            assert 0 < invalid_count < 250, f"Unexpected invalid flag count: {invalid_count}"


def test_get_frames_cache_aware_real_multi_epoch_return():
    """Verify GET /api/frames successfully returns all 3 cached real observations for WISE 0855."""
    from backend.app.config import FITS_CACHE_DIR
    required_files = [
        "spherex_dr1_2025W19_1B_0116_1_SPHEREx-D6_0.0500.fits",
        "spherex_dr1_2025W46_1A_0075_4_SPHEREx-D6_0.0500.fits",
        "spherex_dr1_2025W50_2A_0254_1_SPHEREx-D6_0.0500.fits",
    ]
    if not all((FITS_CACHE_DIR / fname).exists() for fname in required_files):
        pytest.skip("Not all 3 cached real FITS cutouts are present in FITS_CACHE_DIR.")

    # Request 3 frames for WISE 0855 in band SPHEREx-D6
    response = client.get("/api/frames?ra=133.795129&dec=-7.245147&band=SPHEREx-D6&size=0.05&max_frames=3")
    assert response.status_code == 200
    data = response.json()

    assert data["frameCount"] == 3
    assert len(data["frames"]) == 3

    # Verify all 3 frames are distinct real cached observations
    obs_ids = [f["obsId"] for f in data["frames"]]
    assert len(set(obs_ids)) == 3
    for oid in obs_ids:
        expected_path = FITS_CACHE_DIR / f"spherex_dr1_{oid}_SPHEREx-D6_0.0500.fits"
        assert expected_path.exists(), f"Returned observation {oid} was not found in cache"

    # Verify strict chronological ordering by MJD
    mjds = [f["mjd"] for f in data["frames"]]
    assert mjds[0] < mjds[1] < mjds[2]

    # Verify sequential zero-based indices
    for idx, f in enumerate(data["frames"]):
        assert f["index"] == idx
        assert f["width"] == 29
        assert f["height"] == 29
        assert len(f["flux"]) == 841
        assert len(f["flags"]) == 841
        assert not any(np.isnan(f["flux"]))


def test_get_frames_offline_resilience():
    """Verify that when real cached cutouts exist, /api/frames succeeds even if the network is completely offline."""
    from backend.app.config import FITS_CACHE_DIR
    required_files = [
        "spherex_dr1_2025W19_1B_0116_1_SPHEREx-D6_0.0500.fits",
        "spherex_dr1_2025W46_1A_0075_4_SPHEREx-D6_0.0500.fits",
        "spherex_dr1_2025W50_2A_0254_1_SPHEREx-D6_0.0500.fits",
    ]
    if not all((FITS_CACHE_DIR / fname).exists() for fname in required_files):
        pytest.skip("Not all 3 cached real FITS cutouts are present in FITS_CACHE_DIR.")

    # Any live network request will fail immediately
    with patch("requests.get", side_effect=Exception("Network is offline")):
        with patch("requests.post", side_effect=Exception("Network is offline")):
            response = client.get("/api/frames?ra=133.795129&dec=-7.245147&band=SPHEREx-D6&size=0.05&max_frames=3")
            assert response.status_code == 200
            data = response.json()
            assert data["frameCount"] == 3
            assert len(data["frames"]) == 3
            assert data["frames"][0]["obsId"] == "2025W19_1B_0116_1"


def test_get_frames_votable_tap_response_end_to_end(tmp_path: Path, synthetic_fits_epoch1: fits.HDUList):
    """Verify that VOTable TAP response is properly parsed during /api/frames request without 502 error."""
    f1_path = tmp_path / "epoch1.fits"
    synthetic_fits_epoch1.writeto(f1_path)

    votable_payload = {
        "VOTABLE": {
            "RESOURCE_ARRAY": [
                {
                    "TABLE": {
                        "FIELD_ARRAY": [
                            {"<xmlattr>": {"name": "obs_id"}},
                            {"<xmlattr>": {"name": "energy_bandpassname"}},
                            {"<xmlattr>": {"name": "t_min"}},
                            {"<xmlattr>": {"name": "t_exptime"}},
                            {"<xmlattr>": {"name": "s_ra"}},
                            {"<xmlattr>": {"name": "s_dec"}},
                            {"<xmlattr>": {"name": "access_url"}},
                        ],
                        "DATA": {
                            "TABLEDATA": [
                                ["SYNTH_EPOCH1", "SPHEREx-D1", 60800.1, 113.6, 0.0, 0.0, "https://mock.irsa/cutout"],
                            ]
                        },
                    }
                }
            ]
        }
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = votable_payload

    with patch("backend.app.services.selector.TAP_CACHE_DIR", tmp_path / "tap_cache"), \
         patch("backend.app.services.selector.SCRATCH_DIR", tmp_path / "scratch"), \
         patch("requests.post", return_value=mock_resp), \
         patch("backend.app.routers.frames.batch_retrieve_cutouts", return_value={"SYNTH_EPOCH1": f1_path}):
        response = client.get("/api/frames?ra=0.0&dec=0.0&band=SPHEREx-D1&max_frames=1")
        assert response.status_code == 200
        data = response.json()
        assert data["frameCount"] == 1
        assert data["fovDegrees"] == pytest.approx(0.25)
        assert data["frames"][0]["width"] == 146
        assert data["frames"][0]["height"] == 146
        assert len(data["frames"][0]["flux"]) == 146 * 146


def test_get_frames_fov_parameter_validation():
    """Verify that field-of-view parameter 'size' enforces strict bounds [0.01, 0.50]."""
    # Below lower bound (size < 0.01)
    resp_small = client.get("/api/frames?ra=133.795&dec=-7.245&band=SPHEREx-D6&size=0.005")
    assert resp_small.status_code == 422

    # Above upper bound (size > 0.50)
    resp_large = client.get("/api/frames?ra=133.795&dec=-7.245&band=SPHEREx-D6&size=0.60")
    assert resp_large.status_code == 422


def test_get_frames_fov_dimensions_handling(tmp_path: Path, synthetic_fits_epoch1: fits.HDUList):
    """Verify that requesting different valid field-of-view sizes creates matching WCS grids."""
    f1_path = tmp_path / "epoch1.fits"
    synthetic_fits_epoch1.writeto(f1_path)

    obs1 = SelectedObservation(
        obs_id="SYNTH_FOV_1",
        band="SPHEREx-D6",
        mjd=60800.1,
        exptime=113.6,
        access_url="mock_url",
        s_ra=133.795,
        s_dec=-7.245,
    )

    with patch("backend.app.routers.frames.select_observations_for_target", return_value=[obs1]), \
         patch("backend.app.routers.frames.batch_retrieve_cutouts", return_value={"SYNTH_FOV_1": f1_path}):

        # 1. Explicit 0.05 deg -> 29x29
        resp_005 = client.get("/api/frames?ra=133.795129&dec=-7.245147&band=SPHEREx-D6&size=0.05&max_frames=1")
        assert resp_005.status_code == 200
        d_005 = resp_005.json()
        assert d_005["fovDegrees"] == pytest.approx(0.05)
        assert d_005["frames"][0]["width"] == 29
        assert d_005["frames"][0]["height"] == 29
        assert len(d_005["frames"][0]["flux"]) == 841

        # 2. Default (no size parameter) -> 0.25 deg -> 146x146
        resp_default = client.get("/api/frames?ra=133.795129&dec=-7.245147&band=SPHEREx-D6&max_frames=1")
        assert resp_default.status_code == 200
        d_default = resp_default.json()
        assert d_default["fovDegrees"] == pytest.approx(0.25)
        assert d_default["frames"][0]["width"] == 146
        assert d_default["frames"][0]["height"] == 146
        assert len(d_default["frames"][0]["flux"]) == 146 * 146

        # 3. Explicit 0.50 deg -> 292x292
        resp_050 = client.get("/api/frames?ra=133.795129&dec=-7.245147&band=SPHEREx-D6&size=0.50&max_frames=1")
        assert resp_050.status_code == 200
        d_050 = resp_050.json()
        assert d_050["fovDegrees"] == pytest.approx(0.50)
        assert d_050["frames"][0]["width"] == 292
        assert d_050["frames"][0]["height"] == 292
        assert len(d_050["frames"][0]["flux"]) == 292 * 292

