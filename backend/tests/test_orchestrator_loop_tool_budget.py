"""W1.3 (2026-05-22): per-turn tool-call бюджет.

Проверяем что loop останавливается с ErrorEvent `tool_call_budget_exceeded`
после N tool calls (settings.max_tool_calls_per_turn), даже если LLM
продолжает запрашивать tool calls. Это защита от runaway parallel tools
(LLM зажигает 100+ MCP-запросов на одну базу 1С → DoS клиентской БД + рост
стоимости токенов).
"""

import aiosqlite
import pytest

from app.models import ChatRequest

from .fixtures.mcp_responses import (
    FakeMCPClient,
    make_stop_chunk,
    make_text_chunk,
    make_tool_call_chunk,
    make_tool_calls_finish_chunk,
    stub_llm_stream,
)
from .test_orchestrator_loop import collect_sse, mem_db, make_request  # reuse


# ----- настройки: monkeypatch get_settings -----


@pytest.fixture
def small_budget(monkeypatch):
    """Force max_tool_calls_per_turn=2 чтобы тест был быстрым."""
    import app.orchestrator.loop as loop_module
    from app.config import Settings

    def _tight_settings():
        return Settings(
            iteration_budget=10,
            max_tool_calls_per_turn=2,
            compression_enabled=False,
            learning_enabled=False,
            memory_enabled=False,
            seed_on_startup=False,
        )

    monkeypatch.setattr(loop_module, "get_settings", _tight_settings)
    return 2


# ----- helpers -----


def _llm_emits_n_tool_calls(n: int):
    """Возвращает async-generator производящий n tool_calls в одной итерации.

    После первого turn LLM «продолжает» запрашивать ещё tool_calls (повторяет
    тот же ответ), но budget gate должен сработать на (n_per_turn + 1)-м
    вызове.
    """

    def _stream(*_args, **_kwargs):
        chunks = []
        # Один LLM-response с N tool_calls (parallel)
        for i in range(n):
            chunks.append(make_tool_call_chunk(
                index=i,
                call_id=f"t{i}",
                name="get_metadata",
                arguments='{"object_type": "Catalog"}',
            ))
        chunks.append(make_tool_calls_finish_chunk())
        return stub_llm_stream(*chunks)

    return _stream


# ----- тест -----


@pytest.mark.asyncio
async def test_loop_emits_budget_exceeded_when_too_many_tool_calls(
    mem_db, monkeypatch, small_budget,
):
    """LLM зажигает 3 параллельных tool_calls. Budget=2. Loop должен:
    - выполнить первые 2 tool_calls (status, tool_call, tool_result)
    - на 3-м эмитировать ErrorEvent с code='tool_call_budget_exceeded'
    - не делать 3-й tool_call в MCP.
    """
    import app.orchestrator.loop as loop_module

    class FakeLLM:
        def __init__(self, *a, **kw):
            pass

        def stream_chat_completion(self, *a, **kw):
            # 3 tool_calls — на 3-м budget=2 должен сработать
            return _llm_emits_n_tool_calls(3)()

        async def aclose(self):
            pass

    monkeypatch.setattr(loop_module, "LLMClient", FakeLLM)
    monkeypatch.setattr(loop_module, "MCPClient",
                        lambda *a, **kw: FakeMCPClient("http://fake"))

    request = make_request("Покажи всё что есть в базе")
    events = await collect_sse(loop_module.run_chat_loop(
        mem_db, request, "api-key", "http://llm", "model"
    ))

    # Должен быть error event с правильным кодом
    error_events = [e for e in events if e["event"] == "error"]
    assert len(error_events) >= 1, "Должен быть emitted error event"
    err = error_events[0]
    assert err["data"]["code"] == "tool_call_budget_exceeded", (
        f"Expected code='tool_call_budget_exceeded', got {err['data']}"
    )
    # Сообщение упоминает лимит
    assert "Слишком много" in err["data"]["message"]

    # Tool calls в SSE: должны быть РОВНО 2 (budget=2), не 3
    tool_call_events = [e for e in events if e["event"] == "tool_call"]
    assert len(tool_call_events) == 2, (
        f"Expected 2 tool_call events (budget=2), got {len(tool_call_events)}"
    )


@pytest.mark.asyncio
async def test_loop_within_budget_completes_normally(mem_db, monkeypatch, small_budget):
    """LLM зажигает ровно 2 tool_calls (= budget). После всё ок — `done`."""
    import app.orchestrator.loop as loop_module

    class FakeLLM:
        first_call = True

        def __init__(self, *a, **kw):
            pass

        def stream_chat_completion(self, *a, **kw):
            if FakeLLM.first_call:
                FakeLLM.first_call = False
                return _llm_emits_n_tool_calls(2)()
            # Второй round — финальный текст
            return stub_llm_stream(
                make_text_chunk("Готово", finish_reason="stop"),
            )

        async def aclose(self):
            pass

    monkeypatch.setattr(loop_module, "LLMClient", FakeLLM)
    monkeypatch.setattr(loop_module, "MCPClient",
                        lambda *a, **kw: FakeMCPClient("http://fake"))

    request = make_request("В пределах бюджета")
    events = await collect_sse(loop_module.run_chat_loop(
        mem_db, request, "api-key", "http://llm", "model"
    ))

    error_events = [e for e in events if e["event"] == "error"]
    budget_errors = [e for e in error_events
                     if e["data"].get("code") == "tool_call_budget_exceeded"]
    assert len(budget_errors) == 0, "Не должно быть budget-exceeded"

    tool_call_events = [e for e in events if e["event"] == "tool_call"]
    assert len(tool_call_events) == 2

    # done event должен прийти
    done_events = [e for e in events if e["event"] == "done"]
    assert len(done_events) >= 1
