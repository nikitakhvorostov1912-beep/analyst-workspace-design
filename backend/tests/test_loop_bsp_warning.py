"""Интеграционный тест: phantom guardrail (G2) эмитит bsp_warning в run_chat_loop.

Драйвит реальный run_chat_loop через FakeLLM (как test_orchestrator_loop_confirm),
проверяет что при выдуманном методе БСП в ответе эмитится bsp_warning и при этом
ответ НЕ блокируется (done всё равно приходит).
"""

from __future__ import annotations

import json

import aiosqlite
import pytest

from app.models import ChatRequest

from .fixtures.mcp_responses import (
    FakeMCPClient,
    make_stop_chunk,
    make_text_chunk,
    stub_llm_stream,
)


@pytest.fixture
async def mem_db():
    from app.storage.migrations import apply_migrations

    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    await apply_migrations(conn)
    await conn.execute(
        "INSERT INTO mcp_connections (id, name, endpoint) VALUES (?, ?, ?)",
        ("test-ch", "Тест", "http://fake-mcp/mcp"),
    )
    # Сидим один реальный метод БСП → модуль ОбщегоНазначения известен корпусу
    await conn.execute(
        "INSERT INTO bsp_chunks(object_path,module_name,method_name,method_kind,signature,"
        "doc_comment,content,version,source_path,char_count,chunk_hash) "
        "VALUES('bsp:3.2:ОбщегоНазначения.ЗначениеРеквизитаОбъекта','ОбщегоНазначения',"
        "'ЗначениеРеквизитаОбъекта','Функция','sig','doc','c','3.2','x',10,'h')"
    )
    await conn.commit()
    yield conn
    await conn.close()


async def _collect_sse(gen) -> list[dict]:
    events: list[dict] = []
    async for raw in gen:
        event_name = ""
        data_str = ""
        for line in raw.strip().split("\n"):
            if line.startswith("event: "):
                event_name = line[7:]
            elif line.startswith("data: "):
                data_str = line[6:]
        if event_name and data_str:
            events.append({"event": event_name, "data": json.loads(data_str)})
    return events


def _fake_llm_returning(text: str):
    class FakeLLM:
        def __init__(self, *a, **kw):
            pass

        def stream_chat_completion(self, *a, **kw):
            return stub_llm_stream(make_text_chunk(text), make_stop_chunk())

        async def aclose(self):
            pass

    return FakeLLM


async def _run(loop_module, mem_db) -> list[dict]:
    return await _collect_sse(
        loop_module.run_chat_loop(
            mem_db, ChatRequest(message="как?", channel_id="test-ch"),
            "api-key", "http://llm", "model",
        )
    )


@pytest.mark.asyncio
async def test_phantom_answer_emits_bsp_warning(mem_db, monkeypatch):
    import app.orchestrator.loop as loop_module

    monkeypatch.setattr(
        loop_module, "LLMClient",
        _fake_llm_returning("Вызови ОбщегоНазначения.ВыдуманныйМетодХ(Ссылка) для результата."),
    )
    monkeypatch.setattr(loop_module, "MCPClient", lambda *a, **kw: FakeMCPClient("http://fake"))

    events = await _run(loop_module, mem_db)

    warnings = [e for e in events if e["event"] == "bsp_warning"]
    assert len(warnings) == 1, f"ожидался bsp_warning, events={[e['event'] for e in events]}"
    assert "ОбщегоНазначения.ВыдуманныйМетодХ" in warnings[0]["data"]["phantom"]
    # G2 не блокирует — done всё равно эмитится
    assert any(e["event"] == "done" for e in events)


@pytest.mark.asyncio
async def test_real_method_answer_no_bsp_warning(mem_db, monkeypatch):
    import app.orchestrator.loop as loop_module

    monkeypatch.setattr(
        loop_module, "LLMClient",
        _fake_llm_returning("Используй ОбщегоНазначения.ЗначениеРеквизитаОбъекта(Ссылка)."),
    )
    monkeypatch.setattr(loop_module, "MCPClient", lambda *a, **kw: FakeMCPClient("http://fake"))

    events = await _run(loop_module, mem_db)

    assert not any(e["event"] == "bsp_warning" for e in events)
    assert any(e["event"] == "done" for e in events)
