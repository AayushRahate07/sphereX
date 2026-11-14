"""Unit tests for JSON Serialization and Frontend Contract Schema Conformance."""

import json
from backend.app.models.spherex import (
    CatalogMarker,
    SpherexApiResponse,
    SpherexFrame,
    TargetInfo,
    WcsInfo,
)


def test_spherex_api_response_schema():
    """Verify that SpherexApiResponse serializes to exact expected JSON structure."""
    target = TargetInfo(ra=133.795129, dec=-7.245147, name="WISE 0855")
    wcs = WcsInfo(
        crval=(133.795129, -7.245147),
        crpix=(15.0, 15.0),
        cdelt=(-0.001712, 0.001712),
        ctype=("RA---TAN", "DEC--TAN"),
    )
    frame = SpherexFrame(
        index=0,
        mjd=60800.5,
        dateUtc="2025-05-05T12:00:00.000",
        wavelengthMicrons=4.70,
        band="SPHEREx-D6",
        width=3,
        height=3,
        flux=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9],
        flags=[0, 0, 0, 0, 1, 0, 0, 0, 0],
        minFlux=0.1,
        maxFlux=0.9,
        obsId="SYNTH_OBS_001",
    )
    markers = [CatalogMarker(id="m1", ra=133.795, dec=-7.245, label="Target Center")]

    response = SpherexApiResponse(
        target=target,
        fovDegrees=0.05,
        band="SPHEREx-D6",
        dataRelease="DR1",
        wcs=wcs,
        frameCount=1,
        frames=[frame],
        markers=markers,
        isSampleData=False,
    )

    # 1. Standard compliant JSON serialization (allow_nan=False ensures strict RFC 8259)
    json_str = response.model_dump_json()
    data = json.loads(json_str)

    # 2. Strict checks matching src/types/spherex.ts
    assert data["target"]["ra"] == pytest.approx(133.795129)
    assert data["target"]["dec"] == pytest.approx(-7.245147)
    assert data["target"]["name"] == "WISE 0855"
    assert data["fovDegrees"] == pytest.approx(0.05)
    assert data["band"] == "SPHEREx-D6"
    assert data["dataRelease"] == "DR1"
    assert data["frameCount"] == 1
    assert data["isSampleData"] is False

    # WcsInfo
    assert len(data["wcs"]["crval"]) == 2
    assert len(data["wcs"]["crpix"]) == 2
    assert len(data["wcs"]["cdelt"]) == 2
    assert data["wcs"]["ctype"] == ["RA---TAN", "DEC--TAN"]

    # SpherexFrame
    f0 = data["frames"][0]
    assert f0["index"] == 0
    assert f0["mjd"] == pytest.approx(60800.5)
    assert f0["dateUtc"] == "2025-05-05T12:00:00.000"
    assert f0["wavelengthMicrons"] == pytest.approx(4.70)
    assert f0["band"] == "SPHEREx-D6"
    assert f0["width"] == 3
    assert f0["height"] == 3
    assert len(f0["flux"]) == 3 * 3
    assert len(f0["flags"]) == 3 * 3
    assert f0["minFlux"] == pytest.approx(0.1)
    assert f0["maxFlux"] == pytest.approx(0.9)


def test_json_no_nan_or_infinity_tokens():
    """Ensure standard JSON serialization never emits non-standard NaN or Infinity tokens."""
    frame = SpherexFrame(
        index=0,
        mjd=60800.5,
        dateUtc="2025-05-05T12:00:00.000",
        wavelengthMicrons=4.70,
        band="SPHEREx-D6",
        width=2,
        height=2,
        flux=[0.0, 1.0, 2.0, 3.0],
        flags=[0, 0, 1, 0],
        minFlux=0.0,
        maxFlux=3.0,
    )
    response = SpherexApiResponse(
        target=TargetInfo(ra=10.0, dec=20.0),
        fovDegrees=0.05,
        band="SPHEREx-D6",
        dataRelease="DR1",
        wcs=WcsInfo(crval=(10.0, 20.0), crpix=(1.5, 1.5), cdelt=(-0.0017, 0.0017), ctype=("RA---TAN", "DEC--TAN")),
        frameCount=1,
        frames=[frame],
    )
    json_str = response.model_dump_json()
    assert "NaN" not in json_str
    assert "Infinity" not in json_str
    assert "-Infinity" not in json_str


import pytest
