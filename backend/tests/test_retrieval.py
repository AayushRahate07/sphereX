"""Unit tests for FITS Retrieval, Caching, and Transient Retry Handling."""

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
import requests

from backend.app.services.retrieval import (
    RetrievalError,
    fetch_or_cache_fits_cutout,
    find_cached_obs_ids,
    get_cached_fits_path,
    is_cutout_cached,
    resolve_cutout_url_from_datalink,
    retrieve_cutouts_adaptive,
)
from backend.app.services.selector import SelectedObservation


def test_cache_hit_bypasses_network(tmp_path: Path):
    """If FITS file already exists on disk in cache, return immediately without network call."""
    obs = SelectedObservation(
        obs_id="OBS_CACHED_001",
        band="SPHEREx-D1",
        mjd=60800.0,
        exptime=113.6,
        access_url="https://irsa.ipac.caltech.edu/mock_datalink",
        s_ra=100.0,
        s_dec=20.0,
    )

    with patch("backend.app.services.retrieval.FITS_CACHE_DIR", tmp_path):
        cache_file = tmp_path / "spherex_dr1_OBS_CACHED_001_SPHEREx-D1_0.0500.fits"
        # Write dummy valid bytes (> 10000 bytes)
        cache_file.write_bytes(b"FITS_DUMMY_CONTENT" * 1000)

        with patch("requests.get") as mock_get:
            result_path = fetch_or_cache_fits_cutout(obs, ra=100.0, dec=20.0, size_deg=0.05)
            assert result_path == cache_file
            # Network request must NOT have been called
            mock_get.assert_not_called()


def test_transient_503_retry_success(tmp_path: Path):
    """If IRSA IBE returns transient 503 on attempt 1 but 200 on attempt 2, retrieval succeeds."""
    obs = SelectedObservation(
        obs_id="OBS_RETRY_001",
        band="SPHEREx-D1",
        mjd=60800.0,
        exptime=113.6,
        access_url="https://irsa.ipac.caltech.edu/mock_datalink",
        s_ra=100.0,
        s_dec=20.0,
    )

    # Mock DataLink response
    mock_datalink_resp = MagicMock()
    mock_datalink_resp.status_code = 200
    mock_datalink_resp.content = b"""<?xml version="1.0"?>
    <VOTABLE version="1.3">
      <RESOURCE>
        <TABLE>
          <FIELD name="col_1" datatype="char" arraysize="*"/>
          <FIELD name="col_4" datatype="char" arraysize="*"/>
          <DATA><TABLEDATA>
            <TR><TD>https://irsa.ipac.caltech.edu/ibe/data/test.fits</TD><TD>#this</TD></TR>
          </TABLEDATA></DATA>
        </TABLE>
      </RESOURCE>
    </VOTABLE>"""

    # Mock cutout 503 first, then 200 with valid FITS payload
    mock_cutout_503 = MagicMock()
    mock_cutout_503.status_code = 503
    mock_cutout_503.text = "Server busy"

    mock_cutout_200 = MagicMock()
    mock_cutout_200.status_code = 200
    mock_cutout_200.content = b"SIMPLE  =                    T" + b"X" * 15000

    with patch("backend.app.services.retrieval.FITS_CACHE_DIR", tmp_path):
        with patch("backend.app.services.retrieval.time.sleep") as mock_sleep:
            with patch("requests.get", side_effect=[mock_datalink_resp, mock_cutout_503, mock_cutout_200]) as mock_get:
                result_path = fetch_or_cache_fits_cutout(obs, ra=100.0, dec=20.0, size_deg=0.05)
                assert result_path.exists()
                assert result_path.stat().st_size > 10000
                assert mock_get.call_count == 3
                mock_sleep.assert_called_once()


def test_bounded_failure_after_max_retries(tmp_path: Path):
    """If IRSA IBE consistently fails across all retries, raise RetrievalError."""
    obs = SelectedObservation(
        obs_id="OBS_FAIL_001",
        band="SPHEREx-D1",
        mjd=60800.0,
        exptime=113.6,
        access_url="https://irsa.ipac.caltech.edu/mock_datalink",
        s_ra=100.0,
        s_dec=20.0,
    )

    mock_datalink_resp = MagicMock()
    mock_datalink_resp.status_code = 200
    mock_datalink_resp.content = b"""<?xml version="1.0"?>
    <VOTABLE version="1.3">
      <RESOURCE>
        <TABLE>
          <FIELD name="col_1" datatype="char" arraysize="*"/>
          <FIELD name="col_4" datatype="char" arraysize="*"/>
          <DATA><TABLEDATA>
            <TR><TD>https://irsa.ipac.caltech.edu/ibe/data/test.fits</TD><TD>#this</TD></TR>
          </TABLEDATA></DATA>
        </TABLE>
      </RESOURCE>
    </VOTABLE>"""

    mock_cutout_503 = MagicMock()
    mock_cutout_503.status_code = 503
    mock_cutout_503.text = "Server busy"

    with patch("backend.app.services.retrieval.FITS_CACHE_DIR", tmp_path):
        with patch("backend.app.services.retrieval.time.sleep"):
            with patch("requests.get", side_effect=[mock_datalink_resp, mock_cutout_503, mock_cutout_503, mock_cutout_503]):
                with pytest.raises(RetrievalError, match="Failed to retrieve FITS cutout"):
                    fetch_or_cache_fits_cutout(obs, ra=100.0, dec=20.0, size_deg=0.05, max_retries=3)


def test_is_cutout_cached_and_find_cached_obs_ids(tmp_path: Path):
    """Verify is_cutout_cached and find_cached_obs_ids correctly identify cached files."""
    with patch("backend.app.services.retrieval.FITS_CACHE_DIR", tmp_path):
        f1 = tmp_path / "spherex_dr1_OBS_A_SPHEREx-D1_0.0500.fits"
        f1.write_bytes(b"VALID_FITS_BYTES" * 1000)

        assert is_cutout_cached("OBS_A", "SPHEREx-D1", 0.05) is True
        assert is_cutout_cached("OBS_B", "SPHEREx-D1", 0.05) is False

        cached_set = find_cached_obs_ids(["OBS_A", "OBS_B", "OBS_C"], "SPHEREx-D1", 0.05)
        assert cached_set == {"OBS_A"}


def test_retrieve_cutouts_adaptive_uses_cached_without_network(tmp_path: Path):
    """Adaptive retrieval should return cached observations without making network requests."""
    with patch("backend.app.services.retrieval.FITS_CACHE_DIR", tmp_path):
        # Create two valid cached FITS files
        f1 = tmp_path / "spherex_dr1_OBS_CACHED_1_SPHEREx-D6_0.0500.fits"
        f2 = tmp_path / "spherex_dr1_OBS_CACHED_2_SPHEREx-D6_0.0500.fits"
        f1.write_bytes(b"FITS_CONTENT_1" * 1000)
        f2.write_bytes(b"FITS_CONTENT_2" * 1000)

        candidates = [
            SelectedObservation("OBS_UNCACHED", "SPHEREx-D6", 60800.0, 113.6, "url0", 133.795, -7.245),
            SelectedObservation("OBS_CACHED_1", "SPHEREx-D6", 60810.0, 113.6, "url1", 133.795, -7.245),
            SelectedObservation("OBS_CACHED_2", "SPHEREx-D6", 60820.0, 113.6, "url2", 133.795, -7.245),
        ]

        with patch("requests.get") as mock_get:
            obs_list, paths = retrieve_cutouts_adaptive(
                candidates=candidates,
                ra=133.795,
                dec=-7.245,
                target_count=2,
                size_deg=0.05,
            )
            # Both cached observations returned
            assert len(obs_list) == 2
            assert [o.obs_id for o in obs_list] == ["OBS_CACHED_1", "OBS_CACHED_2"]
            assert paths["OBS_CACHED_1"] == f1
            assert paths["OBS_CACHED_2"] == f2
            # Zero network calls performed
            mock_get.assert_not_called()


def test_retrieve_cutouts_adaptive_skips_failed_download_and_continues(tmp_path: Path):
    """If an uncached download fails, continue to next candidate to satisfy target count."""
    with patch("backend.app.services.retrieval.FITS_CACHE_DIR", tmp_path):
        # Pre-cache OBS_2
        f2 = tmp_path / "spherex_dr1_OBS_2_SPHEREx-D6_0.0500.fits"
        f2.write_bytes(b"FITS_CONTENT_2" * 1000)

        candidates = [
            SelectedObservation("OBS_1", "SPHEREx-D6", 60800.0, 113.6, "url1", 133.795, -7.245),
            SelectedObservation("OBS_2", "SPHEREx-D6", 60810.0, 113.6, "url2", 133.795, -7.245),
            SelectedObservation("OBS_3", "SPHEREx-D6", 60820.0, 113.6, "url3", 133.795, -7.245),
        ]

        # Mock: OBS_1 fails download, OBS_3 succeeds download
        f3_path = tmp_path / "spherex_dr1_OBS_3_SPHEREx-D6_0.0500.fits"

        def mock_fetch(observation, ra, dec, size_deg, release):
            if observation.obs_id == "OBS_1":
                raise RetrievalError("503 Server Busy on OBS_1")
            elif observation.obs_id == "OBS_3":
                f3_path.write_bytes(b"FITS_CONTENT_3" * 1000)
                return f3_path
            raise RuntimeError("Unexpected obs_id")

        with patch("backend.app.services.retrieval.fetch_or_cache_fits_cutout", side_effect=mock_fetch):
            obs_list, paths = retrieve_cutouts_adaptive(
                candidates=candidates,
                ra=133.795,
                dec=-7.245,
                target_count=2,
                size_deg=0.05,
            )
            # OBS_2 (cached) and OBS_3 (downloaded) returned
            assert len(obs_list) == 2
            assert [o.obs_id for o in obs_list] == ["OBS_2", "OBS_3"]
            assert paths["OBS_2"] == f2
            assert paths["OBS_3"] == f3_path
            assert obs_list[0].mjd < obs_list[1].mjd


def test_retrieve_cutouts_adaptive_bounded_failure_stops_after_max_attempts(tmp_path: Path):
    """When all downloads fail, adaptive retrieval must stop after max_download_attempts."""
    with patch("backend.app.services.retrieval.FITS_CACHE_DIR", tmp_path):
        candidates = [
            SelectedObservation(f"OBS_{i}", "SPHEREx-D6", 60800.0 + i, 113.6, f"url{i}", 133.795, -7.245)
            for i in range(10)
        ]

        attempt_count = 0

        def failing_fetch(observation, ra, dec, size_deg, release):
            nonlocal attempt_count
            attempt_count += 1
            raise RetrievalError("Simulated download failure")

        with patch("backend.app.services.retrieval.fetch_or_cache_fits_cutout", side_effect=failing_fetch):
            obs_list, paths = retrieve_cutouts_adaptive(
                candidates=candidates,
                ra=133.795,
                dec=-7.245,
                target_count=5,
                size_deg=0.05,
                max_download_attempts=3,
            )
            assert len(obs_list) == 0
            assert len(paths) == 0
            # Must have stopped exactly after 3 attempts, NOT tried all 10
            assert attempt_count == 3
