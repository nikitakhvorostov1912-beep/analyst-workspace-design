"""Tests for app.knowledge.fingerprint (M-K1.5)."""

from __future__ import annotations

import pytest

from app.knowledge.fingerprint import (
    compute_fingerprint,
    fingerprint_from_string,
)


# ---------------------------------------------------------------------------
# compute_fingerprint — happy path
# ---------------------------------------------------------------------------


def test_compute_fingerprint_basic() -> None:
    fp = compute_fingerprint(
        configuration_name="УправлениеТорговлей",
        configuration_version="11.5.18.123",
        platform_version="8.3.27.1989",
    )
    assert len(fp.slug) == 12
    assert len(fp.full_hash) == 64
    assert all(c in "0123456789abcdef" for c in fp.slug)
    assert fp.source_fields["platform_major_minor"] == "8.3"
    assert fp.source_fields["configuration_name"] == "управлениеторговлей"


def test_compute_fingerprint_deterministic() -> None:
    """Same inputs → same output."""
    fp1 = compute_fingerprint(
        configuration_name="УправлениеТорговлей",
        configuration_version="11.5.18.123",
        platform_version="8.3.27.1989",
    )
    fp2 = compute_fingerprint(
        configuration_name="УправлениеТорговлей",
        configuration_version="11.5.18.123",
        platform_version="8.3.27.1989",
    )
    assert fp1.slug == fp2.slug
    assert fp1.full_hash == fp2.full_hash


def test_compute_fingerprint_normalizes_casing_whitespace() -> None:
    """Lowercase + trim — нечувствительность к написанию."""
    fp1 = compute_fingerprint(
        configuration_name="УТ",
        configuration_version="11.5.18",
        platform_version="8.3.27.1989",
    )
    fp2 = compute_fingerprint(
        configuration_name="  ут  ",
        configuration_version=" 11.5.18 ",
        platform_version="8.3.27.1989",
    )
    assert fp1.slug == fp2.slug


def test_compute_fingerprint_platform_patch_ignored() -> None:
    """8.3.27.1989 → 8.3 (только major.minor). Patch+build игнорируется
    чтобы platform updates не дропали knowledge."""
    fp1 = compute_fingerprint(
        configuration_name="УТ",
        configuration_version="11.5.18",
        platform_version="8.3.27.1989",
    )
    fp2 = compute_fingerprint(
        configuration_name="УТ",
        configuration_version="11.5.18",
        platform_version="8.3.28.2000",
    )
    assert fp1.slug == fp2.slug


def test_compute_fingerprint_85_differs_from_83() -> None:
    """8.5.x — отдельный fingerprint от 8.3.x (UI меняется)."""
    fp_83 = compute_fingerprint(
        configuration_name="УТ",
        configuration_version="11.5.18",
        platform_version="8.3.27.1989",
    )
    fp_85 = compute_fingerprint(
        configuration_name="УТ",
        configuration_version="11.5.18",
        platform_version="8.5.1.123",
    )
    assert fp_83.slug != fp_85.slug


def test_compute_fingerprint_extension_order_independent() -> None:
    """Tuple of UUIDs сортируется → порядок не важен."""
    uid_a = "11111111-1111-1111-1111-111111111111"
    uid_b = "22222222-2222-2222-2222-222222222222"

    fp1 = compute_fingerprint(
        configuration_name="УТ",
        configuration_version="11.5",
        platform_version="8.3",
        extension_uids=(uid_a, uid_b),
    )
    fp2 = compute_fingerprint(
        configuration_name="УТ",
        configuration_version="11.5",
        platform_version="8.3",
        extension_uids=(uid_b, uid_a),
    )
    assert fp1.slug == fp2.slug


def test_compute_fingerprint_with_extensions_differs_from_without() -> None:
    """Расширения меняют доступные объекты → fingerprint должен меняться."""
    fp_clean = compute_fingerprint(
        configuration_name="УТ",
        configuration_version="11.5",
        platform_version="8.3",
    )
    fp_ext = compute_fingerprint(
        configuration_name="УТ",
        configuration_version="11.5",
        platform_version="8.3",
        extension_uids=("aabbcc-1234",),
    )
    assert fp_clean.slug != fp_ext.slug


def test_compute_fingerprint_bsp_version_short() -> None:
    """3.1.10.123 → 3.1 (только major.minor)."""
    fp1 = compute_fingerprint(
        configuration_name="УТ",
        configuration_version="11.5",
        platform_version="8.3",
        bsp_version="3.1.10.123",
    )
    fp2 = compute_fingerprint(
        configuration_name="УТ",
        configuration_version="11.5",
        platform_version="8.3",
        bsp_version="3.1.11.456",
    )
    assert fp1.slug == fp2.slug


# ---------------------------------------------------------------------------
# compute_fingerprint — error cases
# ---------------------------------------------------------------------------


def test_compute_fingerprint_empty_configuration_name_raises() -> None:
    with pytest.raises(ValueError, match="configuration_name is required"):
        compute_fingerprint(
            configuration_name="",
            configuration_version="11.5",
            platform_version="8.3",
        )


def test_compute_fingerprint_invalid_platform_raises() -> None:
    with pytest.raises(ValueError, match="major.minor"):
        compute_fingerprint(
            configuration_name="УТ",
            configuration_version="11.5",
            platform_version="invalid",
        )


# ---------------------------------------------------------------------------
# fingerprint_from_string
# ---------------------------------------------------------------------------


def test_fingerprint_from_string_valid() -> None:
    """Восстановление только из slug — для load из БД."""
    fp = fingerprint_from_string("abc123def456")
    assert fp.slug == "abc123def456"
    assert fp.full_hash == ""  # unknown без source_fields
    assert fp.source_fields == {}


def test_fingerprint_from_string_normalizes_casing() -> None:
    fp = fingerprint_from_string("ABC123DEF456")
    assert fp.slug == "abc123def456"


def test_fingerprint_from_string_invalid_length_raises() -> None:
    with pytest.raises(ValueError, match="12 hex chars"):
        fingerprint_from_string("abc")
    with pytest.raises(ValueError, match="12 hex chars"):
        fingerprint_from_string("abc123def456ZZ")


def test_fingerprint_from_string_non_hex_raises() -> None:
    with pytest.raises(ValueError, match="hex"):
        fingerprint_from_string("abc123def4XY")
