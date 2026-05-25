"""Tests for app.knowledge.storage (M-K1.4)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.knowledge.fingerprint import compute_fingerprint
from app.knowledge.storage import (
    KnowledgeStorage,
    KnowledgeStorageError,
    _reset_cache_for_tests,
    get_storage,
)


@pytest.fixture(autouse=True)
def _clear_cache():
    """Каждый тест начинает с чистого module-level cache."""
    _reset_cache_for_tests()
    yield
    _reset_cache_for_tests()


def _make_fp():
    return compute_fingerprint(
        configuration_name="УТ",
        configuration_version="11.5",
        platform_version="8.3.27.1989",
    )


# ---------------------------------------------------------------------------
# Basic creation
# ---------------------------------------------------------------------------


def test_storage_construction_no_io(tmp_path: Path) -> None:
    """Конструктор НЕ создаёт каталоги — только конфигурирует."""
    fp = _make_fp()
    storage = KnowledgeStorage(fp, analyst_home=tmp_path)
    assert not storage.root.exists()
    assert storage.fingerprint is fp


def test_storage_root_layout(tmp_path: Path) -> None:
    """Path: $ANALYST_HOME/knowledge/<slug>."""
    fp = _make_fp()
    storage = KnowledgeStorage(fp, analyst_home=tmp_path)
    assert storage.root == (tmp_path / "knowledge" / fp.slug).resolve()


def test_storage_initialize_creates_all_subdirs(tmp_path: Path) -> None:
    fp = _make_fp()
    storage = KnowledgeStorage(fp, analyst_home=tmp_path)
    storage.initialize()
    assert storage.exists()
    for name in ("metadata", "embeddings", "graph", "cache", "logs"):
        assert (storage.root / name).is_dir()


def test_storage_initialize_idempotent(tmp_path: Path) -> None:
    """Повторный initialize не падает и не дублирует."""
    fp = _make_fp()
    storage = KnowledgeStorage(fp, analyst_home=tmp_path)
    storage.initialize()
    storage.initialize()  # должно работать
    assert storage.exists()


def test_storage_ensure_subdir_creates_lazy(tmp_path: Path) -> None:
    fp = _make_fp()
    storage = KnowledgeStorage(fp, analyst_home=tmp_path)
    # без initialize, только нужный subdir
    embeddings_path = storage.ensure_subdir("embeddings")
    assert embeddings_path.exists()
    assert (storage.root / "metadata").exists() is False


# ---------------------------------------------------------------------------
# Path traversal protection
# ---------------------------------------------------------------------------


def test_storage_subdir_path_traversal_blocked(tmp_path: Path) -> None:
    """Литеральная попытка пройти через '..' блокируется."""
    fp = _make_fp()
    storage = KnowledgeStorage(fp, analyst_home=tmp_path)
    # subdir() не может принять '..' как KnowledgeSubdir Literal, но type
    # check работает только в IDE — runtime защита всё равно нужна
    with pytest.raises(KnowledgeStorageError, match="traversal"):
        storage.subdir("../../../etc")  # type: ignore[arg-type]


def test_storage_subdir_absolute_blocked(tmp_path: Path) -> None:
    fp = _make_fp()
    storage = KnowledgeStorage(fp, analyst_home=tmp_path)
    with pytest.raises(KnowledgeStorageError, match="traversal"):
        storage.subdir("/etc/passwd")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Module-level cache (get_storage)
# ---------------------------------------------------------------------------


def test_get_storage_returns_same_instance(tmp_path: Path) -> None:
    """Один fingerprint slug → один cached KnowledgeStorage."""
    fp = _make_fp()
    s1 = get_storage(fp, analyst_home=tmp_path)
    s2 = get_storage(fp, analyst_home=tmp_path)
    assert s1 is s2


def test_get_storage_different_fingerprints_different_instances(tmp_path: Path) -> None:
    fp1 = compute_fingerprint(
        configuration_name="УТ",
        configuration_version="11.5",
        platform_version="8.3",
    )
    fp2 = compute_fingerprint(
        configuration_name="ERP",
        configuration_version="2.5",
        platform_version="8.3",
    )
    s1 = get_storage(fp1, analyst_home=tmp_path)
    s2 = get_storage(fp2, analyst_home=tmp_path)
    assert s1 is not s2
    assert s1.root != s2.root


# ---------------------------------------------------------------------------
# ANALYST_HOME env var
# ---------------------------------------------------------------------------


def test_storage_uses_analyst_home_env(tmp_path: Path, monkeypatch) -> None:
    custom = tmp_path / "custom_home"
    monkeypatch.setenv("ANALYST_HOME", str(custom))
    fp = _make_fp()
    # Без явного analyst_home — должен взять из env
    storage = KnowledgeStorage(fp)
    storage.initialize()
    assert custom in storage.root.parents
    assert storage.exists()


def test_storage_repr(tmp_path: Path) -> None:
    fp = _make_fp()
    storage = KnowledgeStorage(fp, analyst_home=tmp_path)
    s = repr(storage)
    assert "KnowledgeStorage" in s
    assert fp.slug in s
