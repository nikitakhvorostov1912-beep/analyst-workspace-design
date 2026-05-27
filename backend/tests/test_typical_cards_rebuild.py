"""Тесты для scripts/typical_cards_rebuild.py (M-K2.5.10.5).

Используем respx для мока LLM HTTP вызовов + in-memory SQLite.
"""

from __future__ import annotations

import json
from pathlib import Path

import aiosqlite
import httpx
import pytest
import pytest_asyncio
import respx

from app.knowledge.graph_storage import EdgeKind, NodeKind, insert_edge, insert_node
from app.knowledge.typical.card_models import TypicalObjectCard
from app.knowledge.typical.card_storage import (
    get_card_by_qname,
    upsert_card,
)
from app.knowledge.typical.openai_compat_llm_caller import OpenAICompatLLMCaller
from app.storage.migrations import apply_migrations
from scripts.typical_cards_rebuild import (
    RebuildStats,
    load_checkpoint,
    rebuild_channel,
    save_checkpoint,
)


# ─── Fixtures ─────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def db_ready(tmp_path: Path):
    """In-memory БД с минимальным графом и mock-карточками для теста."""
    db = await aiosqlite.connect(":memory:")
    await db.execute("PRAGMA foreign_keys = ON")
    await apply_migrations(db)

    # Добавим 3 объекта в граф канала _test_
    for qname in ("Document.A", "Document.B", "Document.C"):
        await insert_node(
            db, channel_id="_test_",
            node_kind=NodeKind.METADATA_OBJECT.value,
            qualified_name=qname,
            source_path=None,
            attributes={"kind": "Document", "name": qname.split(".", 1)[1]},
        )

    # И сохраним 3 mock-карточки в БД
    for qname in ("Document.A", "Document.B", "Document.C"):
        card = TypicalObjectCard(
            object_qualified_name=qname,
            object_kind="Document",
            channel_id="_test_",
            summary=f"Stub {qname}",
        )
        await upsert_card(
            db, card=card, source_hash=f"h-{qname}",
            llm_model="mock-generator-v1", is_mock=True,
        )

    yield db
    await db.close()


def _mock_llm_response(qname: str = "Document.X") -> dict:
    """Стандартный LLM ответ для мока."""
    return {
        "model": "test-llm",
        "choices": [{
            "message": {
                "content": json.dumps({
                    "summary": f"Качественное описание {qname}.",
                    "purpose": "Бизнес-смысл объекта в учёте.",
                    "key_attributes": [{"name": "Контрагент", "role": "получатель"}],
                    "movements": [],
                    "posting_flow": ["шаг 1", "шаг 2"],
                    "typical_scenarios": ["сценарий 1"],
                    "preconditions": [],
                    "related_objects": [],
                    "its_links": [],
                }),
            },
        }],
        "usage": {"prompt_tokens": 200, "completion_tokens": 100},
    }


# ─── Checkpoint roundtrip ─────────────────────────────────────────────


def test_save_load_checkpoint_roundtrip(tmp_path: Path):
    stats = RebuildStats(channel_id="_test_", total_in_channel=10, processed=3, succeeded=3)
    save_checkpoint(
        tmp_path,
        "_test_",
        processed_qnames={"Document.A", "Document.B", "Document.C"},
        failed=[],
        stats=stats,
    )

    loaded = load_checkpoint(tmp_path, "_test_")
    assert loaded == {"Document.A", "Document.B", "Document.C"}


def test_load_checkpoint_returns_empty_if_no_file(tmp_path: Path):
    loaded = load_checkpoint(tmp_path, "_nonexistent_")
    assert loaded == set()


def test_load_checkpoint_handles_corrupt_file(tmp_path: Path):
    (tmp_path / "rebuild-_test_.json").write_text("not valid json {{{")
    loaded = load_checkpoint(tmp_path, "_test_")
    assert loaded == set()


# ─── Dry-run ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_dry_run_does_not_call_llm_or_write(db_ready, tmp_path: Path):
    """Dry-run считает carts но не вызывает LLM и не пишет в БД."""
    llm = OpenAICompatLLMCaller(
        endpoint="http://no-call.local/v1",  # этот endpoint не будет вызван
        model="x", api_key="sk-x",
    )
    stats = await rebuild_channel(
        db=db_ready,
        channel_id="_test_",
        llm=llm,
        checkpoint_dir=tmp_path,
        dry_run=True,
    )

    assert stats.total_in_channel == 3  # 3 mock карточки
    assert stats.processed == 0  # Ничего не обработано
    assert llm.telemetry.total_calls == 0  # LLM не вызывался

    # БД не изменилась — карточки всё ещё mock
    rec = await get_card_by_qname(
        db_ready, channel_id="_test_", object_qualified_name="Document.A",
    )
    assert rec.is_mock is True


# ─── Happy path: rebuild ──────────────────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_rebuild_happy_path_3_cards(db_ready, tmp_path: Path):
    """3 mock-карточки → real LLM call → upsert с is_mock=False."""
    respx.post("https://api.test.local/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=_mock_llm_response()),
    )

    llm = OpenAICompatLLMCaller(
        endpoint="https://api.test.local/v1",
        model="test-llm",
        api_key="sk-test",
    )

    stats = await rebuild_channel(
        db=db_ready,
        channel_id="_test_",
        llm=llm,
        checkpoint_dir=tmp_path,
        rate_limit_rps=100.0,  # быстро для теста
        skip_validation=True,
    )

    assert stats.processed == 3
    assert stats.succeeded == 3
    assert stats.failed == 0
    assert llm.telemetry.total_calls == 3
    assert llm.telemetry.total_success == 3

    # Все карточки теперь is_mock=False с real content
    for qname in ("Document.A", "Document.B", "Document.C"):
        rec = await get_card_by_qname(
            db_ready, channel_id="_test_", object_qualified_name=qname,
        )
        assert rec.is_mock is False
        # Mock возвращает один JSON на все вызовы (test fixture), достаточно проверить
        # что summary содержит "Качественное описание" (real content, не stub).
        assert "Качественное описание" in rec.card.summary
        assert rec.llm_model == "test-llm"
        # object_qualified_name сохраняется правильный (а не из mock response)
        assert rec.object_qualified_name == qname


# ─── Resume ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_rebuild_skips_already_processed(db_ready, tmp_path: Path):
    """Resume — если qname в checkpoint, skip."""
    # Заранее положим Document.A в checkpoint
    save_checkpoint(
        tmp_path, "_test_",
        processed_qnames={"Document.A"},
        failed=[],
        stats=RebuildStats(channel_id="_test_"),
    )

    respx.post("https://api.test.local/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=_mock_llm_response()),
    )
    llm = OpenAICompatLLMCaller(
        endpoint="https://api.test.local/v1", model="test", api_key="sk-test",
    )

    stats = await rebuild_channel(
        db=db_ready, channel_id="_test_", llm=llm,
        checkpoint_dir=tmp_path,
        rate_limit_rps=100.0,
        skip_validation=True,
        resume=True,
    )

    # Document.A skipped, Document.B и Document.C обработаны
    assert stats.processed == 2
    assert stats.succeeded == 2
    assert stats.skipped_already_real == 1
    assert llm.telemetry.total_calls == 2


# ─── Limit ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_rebuild_respects_limit(db_ready, tmp_path: Path):
    """--limit ограничивает количество."""
    respx.post("https://api.test.local/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=_mock_llm_response()),
    )
    llm = OpenAICompatLLMCaller(
        endpoint="https://api.test.local/v1", model="test", api_key="sk-test",
    )

    stats = await rebuild_channel(
        db=db_ready, channel_id="_test_", llm=llm,
        checkpoint_dir=tmp_path,
        limit=2,
        rate_limit_rps=100.0,
        skip_validation=True,
    )

    assert stats.total_in_channel == 2  # лимит применён
    assert stats.processed == 2
    assert llm.telemetry.total_calls == 2


# ─── only_mock filter ─────────────────────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_rebuild_only_mock_skips_real_cards(db_ready, tmp_path: Path):
    """Если карточка уже is_mock=False — skip когда only_mock=True."""
    # Document.A уже real LLM
    card = TypicalObjectCard(
        object_qualified_name="Document.A",
        object_kind="Document",
        channel_id="_test_",
        summary="Уже real",
    )
    await upsert_card(
        db_ready, card=card, source_hash="h",
        llm_model="deepseek-chat", is_mock=False,
    )

    respx.post("https://api.test.local/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=_mock_llm_response()),
    )
    llm = OpenAICompatLLMCaller(
        endpoint="https://api.test.local/v1", model="test", api_key="sk-test",
    )

    stats = await rebuild_channel(
        db=db_ready, channel_id="_test_", llm=llm,
        checkpoint_dir=tmp_path,
        only_mock=True,
        rate_limit_rps=100.0,
        skip_validation=True,
    )

    # Только Document.B и Document.C — 2 mock + Document.A skip (уже real)
    assert stats.total_in_channel == 2
    assert stats.processed == 2


# ─── Critical auth error stops immediately ────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_401_auth_error_stops_rebuild(db_ready, tmp_path: Path):
    """401 → LLMAuthError → прекращаем rebuild сразу, не дёргаем dalee."""
    route = respx.post("https://api.test.local/v1/chat/completions").mock(
        return_value=httpx.Response(401, json={"error": "Invalid key"}),
    )
    llm = OpenAICompatLLMCaller(
        endpoint="https://api.test.local/v1", model="test", api_key="sk-bad",
        max_retries=1,
    )

    from app.knowledge.typical.openai_compat_llm_caller import LLMAuthError  # noqa: PLC0415

    with pytest.raises(LLMAuthError):
        await rebuild_channel(
            db=db_ready, channel_id="_test_", llm=llm,
            checkpoint_dir=tmp_path,
            rate_limit_rps=100.0,
            skip_validation=True,
        )

    # Только 1 call (первая карточка) — потом raise
    assert route.call_count == 1

    # Checkpoint всё равно сохранён (для resume)
    cp_path = tmp_path / "rebuild-_test_.json"
    assert cp_path.exists()


# ─── Validation integration ───────────────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_rebuild_with_validation_writes_validation_result(db_ready, tmp_path: Path):
    """С skip_validation=False — validation_status сохраняется в БД."""
    respx.post("https://api.test.local/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=_mock_llm_response()),
    )
    llm = OpenAICompatLLMCaller(
        endpoint="https://api.test.local/v1", model="test", api_key="sk-test",
    )

    stats = await rebuild_channel(
        db=db_ready, channel_id="_test_", llm=llm,
        checkpoint_dir=tmp_path,
        rate_limit_rps=100.0,
        skip_validation=False,  # validate включена
    )

    # Validation должна выполниться для всех карточек
    assert stats.processed == 3
    total_validated = (stats.validation_valid + stats.validation_issues
                       + stats.validation_not_in_graph)
    assert total_validated == 3

    # validation_status сохранён в БД
    rec = await get_card_by_qname(
        db_ready, channel_id="_test_", object_qualified_name="Document.A",
    )
    assert rec.validation_status is not None
