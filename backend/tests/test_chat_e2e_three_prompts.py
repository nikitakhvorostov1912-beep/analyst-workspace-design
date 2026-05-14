"""3 «золотых» e2e сценария из ROADMAP acceptance criteria."""

import json

import pytest
from httpx import AsyncClient

from .fixtures.mcp_responses import (
    FakeMCPClient,
    make_stop_chunk,
    make_text_chunk,
    make_tool_call_chunk,
    make_tool_calls_finish_chunk,
    stub_llm_stream,
)


def _parse_sse_events(body: str) -> list[dict]:
    """Парсит SSE-поток в список {event, data}."""
    events = []
    current: dict = {}
    for line in body.splitlines():
        if line.startswith("event: "):
            current["event"] = line[len("event: "):]
        elif line.startswith("data: "):
            raw = line[len("data: "):]
            try:
                current["data"] = json.loads(raw)
            except json.JSONDecodeError:
                current["data"] = raw
        elif line == "" and current:
            events.append(current)
            current = {}
    if current:
        events.append(current)
    return events


def _patch_loop_for_test(monkeypatch, fake_llm_class, fake_mcp):
    """Патчит LLMClient и MCPClient в loop_module + lookup_mcp_endpoint."""
    import app.orchestrator.loop as loop_module
    import app.orchestrator.persistence as persistence_module

    monkeypatch.setattr(loop_module, "LLMClient", fake_llm_class)
    monkeypatch.setattr(loop_module, "MCPClient", lambda *a, **kw: fake_mcp)
    # Патчим lookup_mcp_endpoint чтобы всегда возвращал endpoint
    monkeypatch.setattr(
        persistence_module,
        "lookup_mcp_endpoint",
        lambda db, channel_id: "http://fake-mcp/mcp" if channel_id == "test-ch" else None,
    )


# --- E2E 1: «Расскажи про базу» → ObjectCard ---

@pytest.mark.asyncio
async def test_e2e_prompt_database_overview(client: AsyncClient, monkeypatch):
    """Prompt «Расскажи про базу» → get_metadata → ObjectCard."""
    import app.orchestrator.loop as loop_module

    metadata_result = {
        "content": [{"type": "text", "text": json.dumps({
            "header": {"name": "InfoBase5", "type": "Configuration", "path": ""},
            "attributes": [
                {"name": "Catalogs", "type": "Number", "value": 265},
                {"name": "Documents", "type": "Number", "value": 27},
                {"name": "Registers", "type": "Number", "value": 150},
            ],
            "tabular_sections": [],
            "forms": [],
            "templates": [],
        })}]
    }

    llm_call = [0]

    class FakeLLM:
        def __init__(self, *a, **kw): pass

        def stream_chat_completion(self, *a, **kw):
            llm_call[0] += 1
            if llm_call[0] == 1:
                return stub_llm_stream(
                    make_tool_call_chunk(0, "tc-meta", "get_metadata", "{}"),
                    make_tool_calls_finish_chunk(),
                )
            return stub_llm_stream(
                make_text_chunk("265 catalogs, 27 documents, 150 registers."),
                make_stop_chunk(),
            )

        async def aclose(self): pass

    fake_mcp = FakeMCPClient(tool_map={"get_metadata": metadata_result})

    async def fake_lookup(db, channel_id):
        return "http://fake-mcp/mcp" if channel_id == "test-ch" else None

    monkeypatch.setattr(loop_module, "LLMClient", FakeLLM)
    monkeypatch.setattr(loop_module, "MCPClient", lambda *a, **kw: fake_mcp)
    monkeypatch.setattr(loop_module, "lookup_mcp_endpoint", fake_lookup)

    response = await client.post(
        "/chat",
        json={"message": "Расскажи про базу", "channel_id": "test-ch"},
        headers={"X-LLM-API-Key": "test-key"},
    )

    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    event_names = [e["event"] for e in events]

    assert "tool_call" in event_names
    assert "tool_result" in event_names
    assert "done" in event_names
    assert "error" not in event_names

    # tool_call должен быть get_metadata
    tool_calls = [e for e in events if e["event"] == "tool_call"]
    assert tool_calls[0]["data"]["name"] == "get_metadata"

    # tool_result ok=True
    tool_results = [e for e in events if e["event"] == "tool_result"]
    assert tool_results[0]["data"]["ok"] is True

    # Проверяем персистенцию: 2 сообщения (user + assistant) в app.state.db
    db = client._transport.app.state.db  # noqa: SLF001
    rows = await db.execute_fetchall("SELECT role FROM messages ORDER BY created_at")
    roles = [r[0] for r in rows]
    assert "user" in roles
    assert "assistant" in roles

    # Assistant message содержит tool_calls
    assistant_rows = await db.execute_fetchall(
        "SELECT tool_calls FROM messages WHERE role = 'assistant'"
    )
    assert assistant_rows
    persisted_tools = json.loads(assistant_rows[0][0])
    assert any(t["name"] == "get_metadata" for t in persisted_tools)


# --- E2E 2: «Покажи документы ОПП за вчера» → TableCard ---

@pytest.mark.asyncio
async def test_e2e_prompt_documents_yesterday(client: AsyncClient, monkeypatch):
    """Prompt «Покажи документы ОПП за вчера» → execute_query → TableCard."""
    import app.orchestrator.loop as loop_module

    query_result = {
        "columns": [{"name": "Номер", "type": "String"}, {"name": "Дата", "type": "Date"}],
        "rows": [["OPP-001", "2026-05-13"]],
    }

    llm_call = [0]

    class FakeLLM:
        def __init__(self, *a, **kw): pass

        def stream_chat_completion(self, *a, **kw):
            llm_call[0] += 1
            if llm_call[0] == 1:
                return stub_llm_stream(
                    make_tool_call_chunk(
                        0, "tc-query", "execute_query",
                        json.dumps({"query": "SELECT Number, Date FROM OPP WHERE Date = &Yesterday"}),
                    ),
                    make_tool_calls_finish_chunk(),
                )
            return stub_llm_stream(
                make_text_chunk("Found 1 OPP document for yesterday."),
                make_stop_chunk(),
            )

        async def aclose(self): pass

    async def fake_lookup(db, channel_id):
        return "http://fake-mcp/mcp" if channel_id == "test-ch" else None

    fake_mcp = FakeMCPClient(tool_map={"execute_query": query_result})
    monkeypatch.setattr(loop_module, "LLMClient", FakeLLM)
    monkeypatch.setattr(loop_module, "MCPClient", lambda *a, **kw: fake_mcp)
    monkeypatch.setattr(loop_module, "lookup_mcp_endpoint", fake_lookup)

    response = await client.post(
        "/chat",
        json={"message": "Покажи документы ОПП за вчера", "channel_id": "test-ch"},
        headers={"X-LLM-API-Key": "test-key"},
    )

    assert response.status_code == 200
    events = _parse_sse_events(response.text)

    # Должна быть TableCard
    card_events = [e for e in events if e["event"] == "card"]
    assert card_events, f"Ожидался event:card, получено: {[e['event'] for e in events]}"
    assert card_events[0]["data"]["type"] == "table"
    assert card_events[0]["data"]["payload"]["rows"] == [["OPP-001", "2026-05-13"]]

    # Проверяем cards в app.state.db
    db = client._transport.app.state.db  # noqa: SLF001
    assistant_rows = await db.execute_fetchall(
        "SELECT cards FROM messages WHERE role = 'assistant'"
    )
    assert assistant_rows
    persisted_cards = json.loads(assistant_rows[0][0])
    assert any(c["type"] == "table" for c in persisted_cards)


# --- E2E 3: «Что в журнале сегодня» → LogCard ---

@pytest.mark.asyncio
async def test_e2e_prompt_event_log_today(client: AsyncClient, monkeypatch):
    """Prompt «Что в журнале сегодня» → get_event_log → LogCard."""
    import app.orchestrator.loop as loop_module

    log_result = {
        "entries": [
            {
                "time": "2026-05-14T09:30:00",
                "level": "Error",
                "user": "admin",
                "event": "_$Data$_.Update",
                "comment": "Record not found",
            }
        ]
    }

    llm_call = [0]

    class FakeLLM:
        def __init__(self, *a, **kw): pass

        def stream_chat_completion(self, *a, **kw):
            llm_call[0] += 1
            if llm_call[0] == 1:
                return stub_llm_stream(
                    make_tool_call_chunk(
                        0, "tc-log", "get_event_log",
                        json.dumps({"start_date": "2026-05-14"}),
                    ),
                    make_tool_calls_finish_chunk(),
                )
            return stub_llm_stream(
                make_text_chunk("1 error in event log today."),
                make_stop_chunk(),
            )

        async def aclose(self): pass

    async def fake_lookup(db, channel_id):
        return "http://fake-mcp/mcp" if channel_id == "test-ch" else None

    fake_mcp = FakeMCPClient(tool_map={"get_event_log": log_result})
    monkeypatch.setattr(loop_module, "LLMClient", FakeLLM)
    monkeypatch.setattr(loop_module, "MCPClient", lambda *a, **kw: fake_mcp)
    monkeypatch.setattr(loop_module, "lookup_mcp_endpoint", fake_lookup)

    response = await client.post(
        "/chat",
        json={"message": "Что в журнале сегодня", "channel_id": "test-ch"},
        headers={"X-LLM-API-Key": "test-key"},
    )

    assert response.status_code == 200
    events = _parse_sse_events(response.text)

    # Должна быть LogCard
    card_events = [e for e in events if e["event"] == "card"]
    assert card_events, f"Ожидался event:card, получено: {[e['event'] for e in events]}"
    assert card_events[0]["data"]["type"] == "log"
    assert len(card_events[0]["data"]["payload"]["entries"]) == 1
    assert card_events[0]["data"]["payload"]["entries"][0]["level"] == "Error"

    assert "done" in [e["event"] for e in events]
    assert "error" not in [e["event"] for e in events]
