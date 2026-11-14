"""Unit tests for SPHEREx Level 2 Quality Flags Policy and Mask Conversion."""

import numpy as np
import pytest

from backend.app.processing.flags import (
    FLAG_COLD,
    FLAG_DICHROIC,
    FLAG_FULLSAMPLE,
    FLAG_HOT,
    FLAG_NONFUNC,
    FLAG_NONLINEAR,
    FLAG_OUTLIER,
    FLAG_OVERFLOW,
    FLAG_PERSIST,
    FLAG_SOURCE,
    FLAG_SUR_ERROR,
    FLAG_TRANSIENT,
    INVALIDATING_MASK,
    create_binary_quality_mask,
)


def test_clean_pixel_returns_zero():
    """Unflagged pixel (0) must yield a clean mask value of 0."""
    raw = np.array([0], dtype=np.int32)
    mask = create_binary_quality_mask(raw)
    assert mask[0] == 0
    assert mask.dtype == np.uint8


def test_source_pixel_remains_valid():
    """CRITICAL TEST: Bit 21 (SOURCE = 2097152) indicates a catalog reference star and MUST NOT be masked."""
    raw = np.array([FLAG_SOURCE], dtype=np.int32)
    mask = create_binary_quality_mask(raw)
    assert mask[0] == 0, "FLAG_SOURCE (bit 21) was erroneously masked as invalid!"


def test_fullsample_pixel_remains_valid():
    """Bit 12 (FULLSAMPLE = 4096) indicates complete sample history and MUST NOT be masked."""
    raw = np.array([FLAG_FULLSAMPLE], dtype=np.int32)
    mask = create_binary_quality_mask(raw)
    assert mask[0] == 0


def test_source_plus_fullsample_remains_valid():
    """A pixel coinciding with a catalog star and full ramp history is clean (0)."""
    raw = np.array([FLAG_SOURCE | FLAG_FULLSAMPLE], dtype=np.int32)
    mask = create_binary_quality_mask(raw)
    assert mask[0] == 0


def test_cautionary_flags_remain_valid():
    """Cautionary flags (PERSIST, OUTLIER) should not be invalidated by default."""
    raw = np.array([FLAG_PERSIST, FLAG_OUTLIER, FLAG_PERSIST | FLAG_OUTLIER], dtype=np.int32)
    mask = create_binary_quality_mask(raw)
    assert np.all(mask == 0)


@pytest.mark.parametrize(
    "fatal_flag",
    [
        FLAG_TRANSIENT,
        FLAG_OVERFLOW,
        FLAG_SUR_ERROR,
        FLAG_NONFUNC,
        FLAG_DICHROIC,
        FLAG_HOT,
        FLAG_COLD,
        FLAG_NONLINEAR,
    ],
)
def test_fatal_flags_are_invalidated(fatal_flag: int):
    """Each individual fatal condition must yield an invalid mask value of 1."""
    raw = np.array([fatal_flag], dtype=np.int32)
    mask = create_binary_quality_mask(raw)
    assert mask[0] == 1, f"Fatal flag {fatal_flag} was not masked as invalid!"


def test_source_coinciding_with_transient_is_invalidated():
    """If a catalog star also suffered a cosmic ray strike (TRANSIENT), the pixel must be masked (1)."""
    raw = np.array([FLAG_SOURCE | FLAG_TRANSIENT], dtype=np.int32)
    mask = create_binary_quality_mask(raw)
    assert mask[0] == 1


def test_prevent_uint8_direct_cast_overflow():
    """Direct uint8 casting of 2097152 would equal 0 (2097152 % 256 == 0).

    Our converter must safely evaluate 32-bit values and output uint8 containing only {0, 1}.
    """
    raw_flags = np.array(
        [
            0,                      # clean -> 0
            FLAG_SOURCE,            # 2097152 -> 0
            FLAG_TRANSIENT,         # 1 -> 1
            FLAG_NONFUNC,           # 64 -> 1
            FLAG_SOURCE | FLAG_NONFUNC,  # 2097216 -> 1
        ],
        dtype=np.int32,
    )
    mask = create_binary_quality_mask(raw_flags)
    expected = np.array([0, 0, 1, 1, 1], dtype=np.uint8)
    np.testing.assert_array_equal(mask, expected)
    assert set(np.unique(mask)).issubset({0, 1})
