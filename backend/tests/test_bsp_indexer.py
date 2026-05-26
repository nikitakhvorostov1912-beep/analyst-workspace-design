"""Тесты для bsp_indexer.py + bsp_search.py (M-K2.8).

Покрытие:
- BSP_CHANNEL_ID константа
- index_bsp_corpus: happy / idempotent skip / force_reindex / batch
- count_bsp_methods / count_bsp_modules / count_bsp_by_version
- error handling: missing root → skip + continue
- search_bsp: happy, ordering, version_filter, k validation, empty index
- BSPSearchHit.to_dict / to_citation / object_path / full_name
"""

from __future__ import annotations

from pathlib import Path

import aiosqlite
import pytest
import pytest_asyncio

from app.knowledge.bsp_indexer import (
    BSP_CHANNEL_ID,
    BSPIndexProgress,
    count_bsp_by_version,
    count_bsp_methods,
    count_bsp_modules,
    index_bsp_corpus,
)
from app.knowledge.bsp_search import (
    BSPSearchError,
    BSPSearchHit,
    search_bsp,
)
from app.knowledge.embeddings import MockEmbeddingClient
from app.knowledge.vector_store import count_embeddings
from app.storage.migrations import apply_migrations


TEST_DIM = 4


def _make_ssl_root(tmp_path: Path, name: str, modules: dict[str, str]) -> Path:
    """Создаёт tmp_path/<name>/src/cf/CommonModules/* с указанными bsl-файлами."""
    root = tmp_path / name
    base = root / "src" / "cf" / "CommonModules"
    for module_name, body in modules.items():
        target = base / module_name / "Ext" / "Module.bsl"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
    return root


def _module_bsl(method_name: str, body: str = "Возврат Истина;") -> str:
    return (
        "#Область ПрограммныйИнтерфейс\n"
        f"// Doc для {method_name}\n"
        f"Функция {method_name}() Экспорт\n"
        f"    {body}\n"
        "КонецФункции\n"
        "#КонецОбласти\n"
    )


@pytest_asyncio.fixture
async def db_ready():
    conn = await aiosqlite.connect(":memory:")
    try:
        await apply_migrations(conn)
        yield conn
    finally:
        await conn.close()


@pytest_asyncio.fixture
async def embed_client():
    return MockEmbeddingClient(dim=TEST_DIM)


# ---------- Константы ----------


def test_bsp_channel_id_reserved():
    assert BSP_CHANNEL_ID == "_bsp"
    assert BSP_CHANNEL_ID.startswith("_")


# ---------- index_bsp_corpus ----------


@pytest.mark.asyncio
async def test_index_one_root(db_ready, embed_client, tmp_path: Path):
    ssl_root = _make_ssl_root(tmp_path, "ssl_3_2", {
        "ДлительныеОперации": _module_bsl("ВыполнитьФункцию"),
        "БезопасноеХранилище": _module_bsl("ПрочитатьДанные"),
    })

    progress = await index_bsp_corpus(db_ready, embed_client, [ssl_root])
    assert isinstance(progress, BSPIndexProgress)
    assert progress.is_success
    assert progress.roots_total == 1
    assert progress.methods_total == 2
    assert progress.methods_embedded == 2
    assert progress.methods_skipped == 0

    assert await count_embeddings(db_ready, BSP_CHANNEL_ID) == 2
    assert await count_bsp_methods(db_ready) == 2
    assert await count_bsp_modules(db_ready) == 2


@pytest.mark.asyncio
async def test_index_two_roots(db_ready, embed_client, tmp_path: Path):
    """Две версии БСП (3.1 + 3.2) индексируются параллельно с разными version."""
    r31 = _make_ssl_root(tmp_path, "ssl_3_1", {
        "Модуль": _module_bsl("МетодВ31"),
    })
    r32 = _make_ssl_root(tmp_path, "ssl_3_2", {
        "Модуль": _module_bsl("МетодВ32"),
    })

    progress = await index_bsp_corpus(db_ready, embed_client, [r31, r32])
    assert progress.is_success
    assert progress.roots_total == 2
    assert progress.methods_total == 2

    by_version = await count_bsp_by_version(db_ready)
    assert by_version == {"3.1": 1, "3.2": 1}


@pytest.mark.asyncio
async def test_index_idempotent_second_run_skips(db_ready, embed_client, tmp_path: Path):
    ssl_root = _make_ssl_root(tmp_path, "ssl_3_2", {
        "M": _module_bsl("X"),
    })

    p1 = await index_bsp_corpus(db_ready, embed_client, [ssl_root])
    assert p1.methods_embedded == 1
    assert p1.methods_skipped == 0

    p2 = await index_bsp_corpus(db_ready, embed_client, [ssl_root])
    assert p2.methods_embedded == 0
    assert p2.methods_skipped == 1


@pytest.mark.asyncio
async def test_index_picks_up_modified_method(db_ready, embed_client, tmp_path: Path):
    ssl_root = _make_ssl_root(tmp_path, "ssl_3_2", {
        "M": _module_bsl("X", body="Возврат 1;"),
    })
    await index_bsp_corpus(db_ready, embed_client, [ssl_root])

    # Меняем body метода
    target = ssl_root / "src" / "cf" / "CommonModules" / "M" / "Ext" / "Module.bsl"
    target.write_text(_module_bsl("X", body="Возврат 2;"), encoding="utf-8")

    p = await index_bsp_corpus(db_ready, embed_client, [ssl_root])
    assert p.methods_embedded == 1
    assert p.methods_skipped == 0


@pytest.mark.asyncio
async def test_index_force_reindex(db_ready, embed_client, tmp_path: Path):
    ssl_root = _make_ssl_root(tmp_path, "ssl_3_2", {"M": _module_bsl("X")})
    await index_bsp_corpus(db_ready, embed_client, [ssl_root])

    p = await index_bsp_corpus(db_ready, embed_client, [ssl_root], force_reindex=True)
    assert p.methods_embedded == 1
    assert p.methods_skipped == 0


@pytest.mark.asyncio
async def test_index_missing_root_continues(db_ready, embed_client, tmp_path: Path):
    """Один root отсутствует → loader fails → продолжаем с остальными."""
    good = _make_ssl_root(tmp_path, "ssl_3_2", {"M": _module_bsl("X")})
    bad = tmp_path / "does-not-exist"

    progress = await index_bsp_corpus(db_ready, embed_client, [bad, good])
    assert progress.is_success
    assert progress.roots_total == 1
    assert progress.methods_embedded == 1


@pytest.mark.asyncio
async def test_index_batch_flush(db_ready, embed_client, tmp_path: Path):
    """batch_size=2 → multiple flushes для 5 методов."""
    modules = {}
    for i in range(5):
        modules[f"M{i}"] = _module_bsl(f"Метод{i}")
    ssl_root = _make_ssl_root(tmp_path, "ssl_3_2", modules)

    progress = await index_bsp_corpus(
        db_ready, embed_client, [ssl_root], batch_size=2,
    )
    assert progress.methods_embedded == 5
    assert await count_embeddings(db_ready, BSP_CHANNEL_ID) == 5


@pytest.mark.asyncio
async def test_index_empty_roots(db_ready, embed_client):
    progress = await index_bsp_corpus(db_ready, embed_client, [])
    assert progress.is_success
    assert progress.roots_total == 0
    assert progress.methods_total == 0


# ---------- search_bsp ----------


@pytest_asyncio.fixture
async def db_with_bsp(tmp_path: Path):
    """In-memory DB с заэмбедженным мини-корпусом БСП."""
    conn = await aiosqlite.connect(":memory:")
    await apply_migrations(conn)
    client = MockEmbeddingClient(dim=TEST_DIM)
    ssl_root = _make_ssl_root(tmp_path, "ssl_3_2", {
        "ДлительныеОперации": _module_bsl("ВыполнитьФункцию"),
        "БезопасноеХранилище": _module_bsl("ПрочитатьДанные"),
        "ЦифроваяПодпись": _module_bsl("ПодписатьДанные"),
    })
    await index_bsp_corpus(conn, client, [ssl_root])
    yield conn, client
    await conn.close()


@pytest.mark.asyncio
async def test_search_returns_hits(db_with_bsp):
    db, client = db_with_bsp
    hits = await search_bsp(db, client, "что-то", k=3)
    assert len(hits) == 3
    assert all(isinstance(h, BSPSearchHit) for h in hits)
    modules = {h.module_name for h in hits}
    assert modules == {"ДлительныеОперации", "БезопасноеХранилище", "ЦифроваяПодпись"}


@pytest.mark.asyncio
async def test_search_ordered_by_distance(db_with_bsp):
    db, client = db_with_bsp
    hits = await search_bsp(db, client, "что-то", k=3)
    distances = [h.distance for h in hits]
    assert distances == sorted(distances)


@pytest.mark.asyncio
async def test_search_exact_match(db_with_bsp):
    """Query равен контенту чанка → distance 0."""
    db, client = db_with_bsp
    cursor = await db.execute(
        "SELECT content FROM bsp_chunks WHERE module_name = 'ДлительныеОперации'"
    )
    row = await cursor.fetchone()
    content = row[0]
    hits = await search_bsp(db, client, content, k=3)
    assert hits[0].module_name == "ДлительныеОперации"


@pytest.mark.asyncio
async def test_search_respects_k(db_with_bsp):
    db, client = db_with_bsp
    hits = await search_bsp(db, client, "что-то", k=1)
    assert len(hits) == 1


@pytest.mark.asyncio
async def test_search_empty_query_raises(db_with_bsp):
    db, client = db_with_bsp
    with pytest.raises(BSPSearchError, match="пустой"):
        await search_bsp(db, client, "")


@pytest.mark.asyncio
async def test_search_invalid_k_raises(db_with_bsp):
    db, client = db_with_bsp
    with pytest.raises(BSPSearchError, match="k должен"):
        await search_bsp(db, client, "q", k=0)


@pytest.mark.asyncio
async def test_search_version_filter(db_ready, tmp_path: Path):
    """version_filter='3.1' возвращает только 3.1-методы."""
    client = MockEmbeddingClient(dim=TEST_DIM)
    r31 = _make_ssl_root(tmp_path, "ssl_3_1", {"M": _module_bsl("МетодВ31")})
    r32 = _make_ssl_root(tmp_path, "ssl_3_2", {"M": _module_bsl("МетодВ32")})
    await index_bsp_corpus(db_ready, client, [r31, r32])

    hits_31 = await search_bsp(db_ready, client, "any", k=5, version_filter="3.1")
    versions = {h.version for h in hits_31}
    assert versions == {"3.1"}

    hits_32 = await search_bsp(db_ready, client, "any", k=5, version_filter="3.2")
    versions = {h.version for h in hits_32}
    assert versions == {"3.2"}


@pytest.mark.asyncio
async def test_search_empty_index():
    conn = await aiosqlite.connect(":memory:")
    try:
        await apply_migrations(conn)
        client = MockEmbeddingClient(dim=TEST_DIM)
        from app.knowledge.vector_store import init_vector_store
        await init_vector_store(conn, dim=TEST_DIM)

        hits = await search_bsp(conn, client, "any")
        assert hits == []
    finally:
        await conn.close()


# ---------- BSPSearchHit serialization ----------


def test_hit_object_path():
    hit = BSPSearchHit(
        module_name="ДлительныеОперации", method_name="ВыполнитьФункцию",
        method_kind="Функция", signature="sig", doc_comment="doc",
        content="content", version="3.2", source_path="src/path",
        distance=0.1,
    )
    assert hit.object_path == "bsp:3.2:ДлительныеОперации.ВыполнитьФункцию"
    assert hit.full_name == "ДлительныеОперации.ВыполнитьФункцию"


def test_hit_to_dict():
    hit = BSPSearchHit(
        module_name="M", method_name="N", method_kind="Процедура",
        signature="Процедура N() Экспорт", doc_comment="doc",
        content="full", version="3.2", source_path="x",
        distance=0.05,
    )
    d = hit.to_dict()
    assert d["module_name"] == "M"
    assert d["method_kind"] == "Процедура"
    assert d["version"] == "3.2"
    assert d["distance"] == 0.05


def test_hit_to_citation():
    hit = BSPSearchHit(
        module_name="ДлительныеОперации", method_name="ВыполнитьФункцию",
        method_kind="Функция", signature="sig", doc_comment="doc",
        content="content", version="3.2", source_path="x", distance=0.1,
    )
    cite = hit.to_citation()
    assert "ДлительныеОперации.ВыполнитьФункцию" in cite
    assert "3.2" in cite
    assert "Функция" in cite
