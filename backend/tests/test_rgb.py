"""Unit and integration tests for the /api/rgb False-Colour Composite endpoint."""

import io
from pathlib import Path
from unittest.mock import patch
from astropy.io import fits
from fastapi.testclient import TestClient
import numpy as np
import pytest

from backend.app.main import app
from backend.app.services.selector import SelectedObservation

client = TestClient(app)


def test_get_rgb_composite_invalid_band():
    """GET /api/rgb with unsupported band must return HTTP 400."""
    response = client.get("/api/rgb?ra=133.795&dec=-7.245&red_band=INVALID_BAND")
    assert response.status_code == 400
    assert "Unsupported bandpass" in response.json()["detail"]


def test_get_rgb_composite_target_not_found():
    """GET /api/rgb for empty target coordinates must return HTTP 404."""
    with patch("backend.app.routers.rgb.select_observations_for_target") as mock_select:
        from backend.app.services.selector import TargetNotFoundError
        mock_select.side_effect = TargetNotFoundError("No SPHEREx observation found")
        response = client.get("/api/rgb?ra=10.0&dec=10.0")
        assert response.status_code == 404
        assert "No SPHEREx observation found" in response.json()["detail"]


def test_get_rgb_composite_deterministic_flow(
    tmp_path: Path,
    synthetic_fits_epoch1: fits.HDUList,
    synthetic_fits_epoch2: fits.HDUList,
):
    """End-to-end integration test of /api/rgb using synthetic FITS fixtures."""
    f_red = tmp_path / "red.fits"
    f_green = tmp_path / "green.fits"
    f_blue = tmp_path / "blue.fits"

    synthetic_fits_epoch1.writeto(f_red)
    synthetic_fits_epoch2.writeto(f_green)
    synthetic_fits_epoch1.writeto(f_blue)

    def mock_select(ra, dec, band, release, max_frames, size_deg):
        return [
            SelectedObservation(
                obs_id=f"OBS_{band}",
                band=band,
                mjd=60800.0 + (1.0 if band == "SPHEREx-D6" else 2.0),
                exptime=113.6,
                access_url=f"mock_url_{band}",
                s_ra=ra,
                s_dec=dec,
            )
        ]

    mock_retrieved = {
        "OBS_SPHEREx-D6": f_red,
        "OBS_SPHEREx-D2": f_green,
        "OBS_SPHEREx-D1": f_blue,
    }

    with patch("backend.app.routers.rgb.select_observations_for_target", side_effect=mock_select):
        with patch("backend.app.routers.rgb.batch_retrieve_cutouts", return_value=mock_retrieved):
            response = client.get(
                "/api/rgb?ra=133.795129&dec=-7.245147&size=0.05&red_band=SPHEREx-D6&green_band=SPHEREx-D2&blue_band=SPHEREx-D1"
            )
            assert response.status_code == 200
            data = response.json()

            # Target & release
            assert data["target"]["ra"] == pytest.approx(133.795129)
            assert data["target"]["dec"] == pytest.approx(-7.245147)
            assert data["target"]["name"] == "WISE 0855"
            assert data["dataRelease"] == "DR1"
            assert data["fovDegrees"] == pytest.approx(0.05)
            assert data["isSampleData"] is False

            # Dimensions & WCS
            assert data["width"] == 29
            assert data["height"] == 29
            wcs = data["wcs"]
            assert len(wcs["crval"]) == 2
            assert len(wcs["crpix"]) == 2
            assert wcs["ctype"] == ["RA---TAN", "DEC--TAN"]

            # Channels
            assert "red" in data["channels"]
            assert "green" in data["channels"]
            assert "blue" in data["channels"]

            for ch_key, expected_band in [("red", "SPHEREx-D6"), ("green", "SPHEREx-D2"), ("blue", "SPHEREx-D1")]:
                ch = data["channels"][ch_key]
                assert ch["band"] == expected_band
                assert len(ch["flux"]) == 29 * 29
                assert len(ch["flags"]) == 29 * 29
                assert not any(np.isnan(ch["flux"]))
                assert not any(np.isinf(ch["flux"]))
                assert set(ch["flags"]).issubset({0, 1})
                assert ch["minFlux"] <= ch["maxFlux"]
                assert ch["p1Flux"] <= ch["p99Flux"]
                assert ch["wavelengthMicrons"] > 0

            # Scientific notice
            assert "False-color infrared composite" in data["scientificNotice"]
            assert "Red = SPHEREx-D6" in data["scientificNotice"]


def test_get_rgb_composite_real_cache_smoke_test():
    """Smoke test of /api/rgb using real cached observations for WISE 0855."""
    from backend.app.config import FITS_CACHE_DIR

    required_bands = ["D6", "D2", "D1"]
    has_all_bands = all(
        any(f"-{b}_" in f.name for f in FITS_CACHE_DIR.glob("*.fits"))
        for b in required_bands
    )
    if not has_all_bands:
        pytest.skip("Not all required bands (D6, D2, D1) are present in local FITS cache.")

    response = client.get(
        "/api/rgb?ra=133.795129&dec=-7.245147&size=0.05&red_band=SPHEREx-D6&green_band=SPHEREx-D2&blue_band=SPHEREx-D1"
    )
    assert response.status_code == 200
    data = response.json()

    assert data["target"]["name"] == "WISE 0855"
    assert data["width"] == 29
    assert data["height"] == 29
    assert len(data["channels"]) == 3
    for ch_name in ("red", "green", "blue"):
        ch = data["channels"][ch_name]
        assert len(ch["flux"]) == 841
        assert len(ch["flags"]) == 841
        assert ch["minFlux"] <= ch["maxFlux"]


def test_get_rgb_composite_fov_dimensions(
    tmp_path: Path,
    synthetic_fits_epoch1: fits.HDUList,
    synthetic_fits_epoch2: fits.HDUList,
):
    """Verify that default and explicit FOV sizes construct correctly dimensioned RGB composites."""
    f_red = tmp_path / "red.fits"
    f_green = tmp_path / "green.fits"
    f_blue = tmp_path / "blue.fits"

    synthetic_fits_epoch1.writeto(f_red)
    synthetic_fits_epoch2.writeto(f_green)
    synthetic_fits_epoch1.writeto(f_blue)

    mock_retrieved = {
        "OBS_SPHEREx-D6": f_red,
        "OBS_SPHEREx-D2": f_green,
        "OBS_SPHEREx-D1": f_blue,
    }

    def mock_select(ra, dec, band, release, max_frames, size_deg):
        return [
            SelectedObservation(
                obs_id=f"OBS_{band}",
                band=band,
                mjd=60800.0,
                exptime=113.6,
                access_url=f"mock_url_{band}",
                s_ra=ra,
                s_dec=dec,
            )
        ]

    with patch("backend.app.routers.rgb.select_observations_for_target", side_effect=mock_select), \
         patch("backend.app.routers.rgb.batch_retrieve_cutouts", return_value=mock_retrieved):

        # 1. Default (no size specified) -> 0.25 deg -> 146x146
        resp_def = client.get("/api/rgb?ra=133.795129&dec=-7.245147")
        assert resp_def.status_code == 200
        d_def = resp_def.json()
        assert d_def["fovDegrees"] == pytest.approx(0.25)
        assert d_def["width"] == 146
        assert d_def["height"] == 146
        assert len(d_def["channels"]["red"]["flux"]) == 146 * 146

        # 2. Validation bounds
        resp_too_small = client.get("/api/rgb?ra=133.795129&dec=-7.245147&size=0.005")
        assert resp_too_small.status_code == 422
        resp_too_large = client.get("/api/rgb?ra=133.795129&dec=-7.245147&size=0.60")
        assert resp_too_large.status_code == 422

