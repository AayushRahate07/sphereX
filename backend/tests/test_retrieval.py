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
    get_fits_cache_path,
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


def test_resolve_datalink_uncropped_science_product():
    """When size_deg is None, resolve_cutout_url_from_datalink preserves the genuine full science product."""
    mock_datalink_resp = MagicMock()
    mock_datalink_resp.status_code = 200
    mock_datalink_resp.content = b"""<?xml version="1.0"?>
    <VOTABLE version="1.3">
      <RESOURCE>
        <TABLE>
          <FIELD name="col_1" datatype="char" arraysize="*"/>
          <FIELD name="col_4" datatype="char" arraysize="*"/>
          <FIELD name="col_12" datatype="char" arraysize="*"/>
          <DATA><TABLEDATA>
            <TR><TD>https://irsa.ipac.caltech.edu/ibe/data/spherex/dr1/full_level2.fits</TD><TD>#this</TD><TD></TD></TR>
            <TR><TD></TD><TD>#cutout</TD><TD>spherex/dr1/full_level2.fits</TD></TR>
          </TABLEDATA></DATA>
        </TABLE>
      </RESOURCE>
    </VOTABLE>"""

    with patch("requests.get", return_value=mock_datalink_resp):
        # 1. Uncropped product: size_deg=None returns exact science_url without query parameters
        url_full = resolve_cutout_url_from_datalink(
            "https://irsa.ipac.caltech.edu/mock_datalink_full",
            ra=133.795,
            dec=-7.245,
            size_deg=None,
        )
        assert url_full == "https://irsa.ipac.caltech.edu/ibe/data/spherex/dr1/full_level2.fits"
        assert "?" not in url_full

        # 2. Cutout request: size_deg=0.05 targets cutout service with center and size
        url_cutout = resolve_cutout_url_from_datalink(
            "https://irsa.ipac.caltech.edu/mock_datalink_cutout",
            ra=133.795,
            dec=-7.245,
            size_deg=0.05,
        )
        assert url_cutout.startswith("https://irsa.ipac.caltech.edu/ibe/data/spherex/dr1/full_level2.fits?")
        assert "center=133.795000,-7.245000d" in url_cutout
        assert "size=0.05" in url_cutout


def test_get_cached_fits_path_recognizes_full_fits(tmp_path: Path):
    """get_cached_fits_path returns cached full detector FITS when available."""
    full_fits_file = tmp_path / "spherex_dr1_OBS_FULL_001_SPHEREx-D1.fits"
    full_fits_file.write_bytes(b"FULL_FITS_BYTES" * 1000)

    with patch("backend.app.services.retrieval.FITS_CACHE_DIR", tmp_path):
        # Asking for a cutout when full file is cached returns full file
        found = get_cached_fits_path("OBS_FULL_001", "SPHEREx-D1", size_deg=0.05)
        assert found == full_fits_file


def test_cache_separation_across_different_fov_sizes(tmp_path: Path):
    """Verify that cached cutouts of different FOVs maintain distinct paths and do not collide."""
    obs_id = "OBS_SEP_001"
    band = "SPHEREx-D6"
    release = "DR1"
    ra, dec = 133.7951, -7.2451

    # 1. Deterministic path generation
    path_005 = get_fits_cache_path(obs_id, band, size_deg=0.05, release=release, center_ra=ra, center_dec=dec)
    path_025 = get_fits_cache_path(obs_id, band, size_deg=0.25, release=release, center_ra=ra, center_dec=dec)
    path_050 = get_fits_cache_path(obs_id, band, size_deg=0.50, release=release, center_ra=ra, center_dec=dec)

    assert path_005.name == "spherex_dr1_OBS_SEP_001_SPHEREx-D6_133.7951_-7.2451_0.0500.fits"
    assert path_025.name == "spherex_dr1_OBS_SEP_001_SPHEREx-D6_133.7951_-7.2451_0.2500.fits"
    assert path_050.name == "spherex_dr1_OBS_SEP_001_SPHEREx-D6_133.7951_-7.2451_0.5000.fits"

    assert path_005 != path_025
    assert path_025 != path_050

    with patch("backend.app.services.retrieval.FITS_CACHE_DIR", tmp_path):
        # 2. Write only the 0.0500.fits file
        cache_005 = tmp_path / path_005.name
        cache_005.write_bytes(b"DUMMY_FITS_BYTES_005" * 1000)

        # 0.05 cutout is cached
        assert is_cutout_cached(obs_id, band, size_deg=0.05, release=release, center_ra=ra, center_dec=dec) is True

        # 0.25 cutout must NOT be reported as cached; must trigger genuine fetch
        assert is_cutout_cached(obs_id, band, size_deg=0.25, release=release, center_ra=ra, center_dec=dec) is False
        assert is_cutout_cached(obs_id, band, size_deg=0.50, release=release, center_ra=ra, center_dec=dec) is False

        # find_cached_obs_ids must not return obs_id for 0.25
        coords_map = {obs_id: (ra, dec)}
        cached_set_025 = find_cached_obs_ids([obs_id], band, size_deg=0.25, release=release, coords_per_obs=coords_map)
        assert obs_id not in cached_set_025

        cached_set_005 = find_cached_obs_ids([obs_id], band, size_deg=0.05, release=release, coords_per_obs=coords_map)
        assert obs_id in cached_set_005

        # 3. Write 0.25 file and verify independent presence
        cache_025 = tmp_path / path_025.name
        cache_025.write_bytes(b"DUMMY_FITS_BYTES_025" * 1000)

        assert is_cutout_cached(obs_id, band, size_deg=0.25, release=release, center_ra=ra, center_dec=dec) is True
        # Original 0.05 file is unmodified
        assert cache_005.read_bytes() == b"DUMMY_FITS_BYTES_005" * 1000


def test_datalink_transient_502_retry_success():
    """Verify that resolve_cutout_url_from_datalink retries on transient 502/503 from IRSA proxy and succeeds."""
    mock_502 = MagicMock()
    mock_502.status_code = 502
    mock_502.text = "Proxy Error"

    mock_200 = MagicMock()
    mock_200.status_code = 200
    mock_200.content = b"""<?xml version="1.0"?>
    <VOTABLE version="1.3">
      <RESOURCE>
        <TABLE>
          <FIELD name="col_1" datatype="char" arraysize="*"/>
          <FIELD name="col_4" datatype="char" arraysize="*"/>
          <DATA><TABLEDATA>
            <TR><TD>https://irsa.ipac.caltech.edu/ibe/data/spherex/dr1/cutout.fits</TD><TD>#cutout</TD></TR>
          </TABLEDATA></DATA>
        </TABLE>
      </RESOURCE>
    </VOTABLE>"""

    with patch("requests.get", side_effect=[mock_502, mock_200]), patch("time.sleep"):
        url = resolve_cutout_url_from_datalink(
            "https://irsa.ipac.caltech.edu/test_retry_datalink",
            ra=133.795,
            dec=-7.245,
            size_deg=0.25,
        )
        assert "center=133.795000,-7.245000d" in url
        assert "size=0.25" in url


def test_fov_cache_incompatible_cutout_rejection(tmp_path: Path):
    """A 29x29 cutout must be rejected when a 0.50 deg FOV (~292 px) is requested."""
    import numpy as np
    from astropy.io import fits
    from backend.app.config import DEFAULT_PLATE_SCALE_DEG
    from backend.app.services.retrieval import _is_fits_compatible_with_fov

    # Create real 29x29 FITS file
    fits_29 = tmp_path / "spherex_dr1_OBS_TEST_SPHEREx-D6_0.5000.fits"
    hdr = fits.Header()
    hdr["SIMPLE"] = True
    hdr["BITPIX"] = -32
    hdr["NAXIS"] = 2
    hdr["NAXIS1"] = 29
    hdr["NAXIS2"] = 29
    hdr["CRPIX1"] = 15.0
    hdr["CRPIX2"] = 15.0
    hdr["CRVAL1"] = 100.0
    hdr["CRVAL2"] = 20.0
    hdr["CDELT1"] = -DEFAULT_PLATE_SCALE_DEG
    hdr["CDELT2"] = DEFAULT_PLATE_SCALE_DEG
    hdr["CTYPE1"] = "RA---TAN"
    hdr["CTYPE2"] = "DEC--TAN"
    primary = fits.PrimaryHDU()
    img = fits.ImageHDU(data=np.zeros((29, 29), dtype=np.float32), header=hdr, name="IMAGE")
    hdul = fits.HDUList([primary, img])
    hdul.writeto(fits_29)
    with open(fits_29, "ab") as f:
        f.write(b"\x00" * 15000)

    # Compatible for 0.05 deg
    assert _is_fits_compatible_with_fov(fits_29, size_deg=0.05) is True
    # Incompatible for 0.50 deg (29 << 160 min required)
    assert _is_fits_compatible_with_fov(fits_29, size_deg=0.50) is False

    # Edge-truncated genuine cutout (294x213) is accepted for 0.50 deg
    hdr_edge = fits.Header()
    hdr_edge["SIMPLE"] = True
    hdr_edge["BITPIX"] = -32
    hdr_edge["NAXIS"] = 2
    hdr_edge["NAXIS1"] = 294
    hdr_edge["NAXIS2"] = 213
    img_edge = fits.ImageHDU(data=np.zeros((213, 294), dtype=np.float32), header=hdr_edge, name="IMAGE")
    fits_edge = tmp_path / "spherex_dr1_OBS_EDGE_SPHEREx-D6_0.5000.fits"
    fits.HDUList([fits.PrimaryHDU(), img_edge]).writeto(fits_edge)
    with open(fits_edge, "ab") as f:
        f.write(b"\x00" * 15000)
    assert _is_fits_compatible_with_fov(fits_edge, size_deg=0.50) is True

    with patch("backend.app.services.retrieval.FITS_CACHE_DIR", tmp_path):
        assert get_cached_fits_path("OBS_TEST", "SPHEREx-D6", size_deg=0.50) is None


def test_batch_retrieve_cutouts_concurrency_scaling():
    """Verify batch_retrieve_cutouts caps workers to 2 for FOV >= 0.40 deg to respect IRSA IBE."""
    from backend.app.services.retrieval import batch_retrieve_cutouts

    with patch("backend.app.services.retrieval.ThreadPoolExecutor") as mock_tpe:
        # 0.50 deg FOV with max_workers=4 requested should be clamped to 2
        batch_retrieve_cutouts(
            observations=[],
            ra=100.0,
            dec=20.0,
            size_deg=0.50,
            max_workers=4,
        )
        mock_tpe.assert_called_once_with(max_workers=2)

    with patch("backend.app.services.retrieval.ThreadPoolExecutor") as mock_tpe:
        # 0.25 deg FOV keeps 4 workers
        batch_retrieve_cutouts(
            observations=[],
            ra=100.0,
            dec=20.0,
            size_deg=0.25,
            max_workers=4,
        )
        mock_tpe.assert_called_once_with(max_workers=4)


def test_fetch_or_cache_fits_cutout_adapts_timeout_for_large_fov(tmp_path: Path):
    """When size_deg > 0.25, timeout must be at least 60 seconds for heavy IRSA cutouts."""
    obs = SelectedObservation("OBS_TIMEOUT", "SPHEREx-D6", 60800.0, 113.6, "https://mock.irsa/dl", 100.0, 20.0)

    mock_datalink_resp = MagicMock()
    mock_datalink_resp.status_code = 200
    mock_datalink_resp.content = b"""<?xml version="1.0"?>
    <VOTABLE version="1.3">
      <RESOURCE><TABLE>
        <FIELD name="col_1" datatype="char" arraysize="*"/>
        <FIELD name="col_4" datatype="char" arraysize="*"/>
        <DATA><TABLEDATA><TR><TD>https://mock.irsa/ibe/cutout.fits</TD><TD>#this</TD></TR></TABLEDATA></DATA>
      </TABLE></RESOURCE>
    </VOTABLE>"""

    mock_cutout_resp = MagicMock()
    mock_cutout_resp.status_code = 200
    mock_cutout_resp.content = b"SIMPLE  =                    T" + b"X" * 15000

    with patch("backend.app.services.retrieval.FITS_CACHE_DIR", tmp_path):
        with patch("requests.get", side_effect=[mock_datalink_resp, mock_cutout_resp]) as mock_get:
            fetch_or_cache_fits_cutout(obs, 100.0, 20.0, size_deg=0.50, timeout=35)
            # Second call (cutout download) must have effective timeout >= 60
            assert mock_get.call_count == 2
            cutout_call = mock_get.call_args_list[1]
            assert cutout_call.kwargs.get("timeout") >= 60




