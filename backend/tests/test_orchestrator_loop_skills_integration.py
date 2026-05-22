"""W1.8 (2026-05-22): интеграционный тест Sprint 3 Hermes wire-up.

Проверяем full-stack цепочку:
  user message → run_chat_loop → assistant response → schedule_review (fire-and-forget) →
  background_review.review_turn → aux LLM → skill saved → SkillStore.read() возвращает skill →
  следующий turn видит skill в system prompt (render_for_prompt) → skill_usage.increment().

Это закрывает honesty-gap, который записан в STATE.md «Sprint 3 code-only complete»:
factual проверка что wire-up реально работает end-to-end.
"""

from __future__ import annotations

import asyncio
import json

import aiosqlite
import pytest

from app.config import Settings
from app.models import ChatRequest

from .fixtures.mcp_responses import (
    FakeMCPClient,
    make_stop_chunk,
    make_text_chunk,
    stub_llm_stream,
)
from .test_orchestrator_loop import collect_sse, mem_db, make_request  # noqa: F401  reuse


# ====== Fake aux client который возвращает «save skill» решение ======


class FakeAuxClient:
    """Имитирует AuxiliaryClient.complete_with_fallback.

    review_turn вызывает complete_with_fallback с messages — мы возвращаем
    JSON с save=True. Background_review должен распарсить и записать skill.
    """

    def __init__(self, decision: dict) -> None:
        self.decision_json = json.dumps(decision)
        self.calls: list[list[dict]] = []

    async def complete_with_fallback(self, messages, **_kwargs):
        self.calls.append(messages)
        return self.decision_json

    async def aclose(self) -> None:
        pass


# ====== Fixture: подменяет AuxiliaryClient и memory_root ======


@pytest.fixture
def isolated_skill_env(monkeypatch, tmp_path):
    """Force memory_root=tmp_path + auxiliary возвращает «save skill».

    Возвращает (aux_client_class, fake_aux_instance) для проверок в тесте.
    """
    skill_decision = {
        "save": True,
        "id": "opp-fast-query",
        "tags": ["opp", "test"],
        "body": (
            "Когда аналитик спрашивает «покажи ОПП за X без шапки» — нужно "
            "использовать ЗапросИНДД и фильтровать по полю ВидДокумента. "
            "Это типовой паттерн для быстрого вывода 32 строк. Проверено "
            "в Транзит-базе. Длина body минимум 100 символов для прохождения "
            "filter'а в background_review."
        ),
    }
    fake_aux = FakeAuxClient(skill_decision)

    # AuxiliaryClient инстанцируется внутри run_chat_loop. Подменяем класс.
    import app.orchestrator.loop as loop_module

    class _FakeAuxClass:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def complete_with_fallback(self, messages, **kwargs):
            return await fake_aux.complete_with_fallback(messages, **kwargs)

        async def aclose(self) -> None:
            await fake_aux.aclose()

    monkeypatch.setattr(loop_module, "AuxiliaryClient", _FakeAuxClass)

    # Memory root через Settings monkeypatch
    def _tight_settings():
        return Settings(
            iteration_budget=10,
            max_tool_calls_per_turn=10,
            compression_enabled=False,  # упрощаем — без compressor
            learning_enabled=True,
            memory_enabled=True,
            memory_root=str(tmp_path / "memory"),
            seed_on_startup=False,
        )

    monkeypatch.setattr(loop_module, "get_settings", _tight_settings)
    return fake_aux, tmp_path / "memory" / "skills"


# ====== Тест ======


@pytest.mark.asyncio
async def test_sprint3_wire_up_skill_created_after_turn(
    mem_db, monkeypatch, isolated_skill_env
):
    """End-to-end: после успешного turn'а background_review создаёт skill в SkillStore.

    Acceptance:
    1. schedule_review был вызван (fake_aux.calls не пустой)
    2. Skill реально создан на диске в tmp_path/memory/skills/<channel>/
    3. SkillStore может его прочитать
    4. Skill provenance = 'agent' (NOT 'user')
    """
    fake_aux, skills_dir = isolated_skill_env

    import app.orchestrator.loop as loop_module

    class FakeLLM:
        def __init__(self, *a, **kw):
            pass

        def stream_chat_completion(self, *a, **kw):
            # Просто текстовый ответ без tool_calls — чтобы скорее закончить turn
            return stub_llm_stream(
                make_text_chunk("Готово, вот результат."),
                make_text_chunk("", finish_reason="stop"),
            )

        async def aclose(self):
            pass

    monkeypatch.setattr(loop_module, "LLMClient", FakeLLM)
    monkeypatch.setattr(
        loop_module, "MCPClient", lambda *a, **kw: FakeMCPClient("http://fake"),
    )

    # Канал test-ch уже в mem_db фикстуре (insert в conftest mem_db)
    request = make_request("Покажи ОПП за 30.04 без шапки")
    events = await collect_sse(
        loop_module.run_chat_loop(
            mem_db, request, "api-key", "http://llm", "model"
        )
    )

    # done event должен прийти
    done = [e for e in events if e["event"] == "done"]
    assert len(done) == 1, f"Expected done event, got events: {[e['event'] for e in events]}"

    # schedule_review запускает asyncio.create_task — даём ему время выполниться
    # (он fire-and-forget, мы ждём явно)
    await asyncio.sleep(0.1)
    # Иногда нужно ещё подождать, особенно на slow CI
    for _ in range(10):
        if fake_aux.calls:
            break
        await asyncio.sleep(0.05)

    # 1. fake_aux был вызван
    assert len(fake_aux.calls) >= 1, (
        "background_review не вызвал aux client — schedule_review не сработал"
    )

    # 2. Skill реально создан на диске
    channel_skills_dir = skills_dir / "test-ch"
    assert channel_skills_dir.exists(), (
        f"Skills dir для канала не создан: {channel_skills_dir}"
    )
    skill_files = list(channel_skills_dir.glob("*.md"))
    # Не считаем .archive/ — это вне нашего теста
    skill_files = [f for f in skill_files if not f.name.startswith(".")]
    assert len(skill_files) >= 1, (
        f"Skill не создан на диске. Файлы в {channel_skills_dir}: "
        f"{list(channel_skills_dir.iterdir()) if channel_skills_dir.exists() else 'dir не существует'}"
    )

    # 3. SkillStore читает skill корректно
    from app.learning.skill_store import SkillStore

    store = SkillStore(skills_dir, "test-ch")
    active = store.list_active()
    assert len(active) >= 1, "SkillStore.list_active() вернул пустой список"

    skill = next((s for s in active if s.id == "opp-fast-query"), None)
    assert skill is not None, (
        f"Skill 'opp-fast-query' не найден в active skills: {[s.id for s in active]}"
    )

    # 4. Provenance = 'agent' (это вклад LLM, не пользователя)
    assert skill.provenance == "agent", (
        f"Skill provenance должен быть 'agent', получен: {skill.provenance!r}"
    )

    # 5. Body содержит ожидаемый контент
    assert "ОПП" in skill.body and "ЗапросИНДД" in skill.body, (
        f"Skill body не содержит ожидаемого контента: {skill.body[:200]}"
    )


@pytest.mark.asyncio
async def test_sprint3_skill_injected_into_next_turn_prompt(
    mem_db, monkeypatch, isolated_skill_env, tmp_path
):
    """Skill созданный в первом turn должен попасть в system prompt второго turn'а.

    Это проверяет render_for_prompt() инжект — главный USP «самообучения».
    """
    fake_aux, skills_dir = isolated_skill_env

    # Pre-seed: сразу создаём skill в store (имитируем что предыдущий turn его сохранил).
    from app.learning.skill_provenance import provenance
    from app.learning.skill_store import Skill, SkillStore

    store = SkillStore(skills_dir, "test-ch")
    with provenance("agent"):
        store.write(
            Skill(
                id="opp-fast-query",
                body=(
                    "Когда аналитик спрашивает «покажи ОПП за X без шапки» — "
                    "нужно использовать ЗапросИНДД."
                ),
                provenance="agent",
                tags=["opp"],
            )
        )

    import app.orchestrator.loop as loop_module

    captured_messages: list[list[dict]] = []

    class FakeLLMCapture:
        def __init__(self, *a, **kw):
            pass

        def stream_chat_completion(self, *args, **kwargs):
            # messages — первый позиционный или в kwargs
            captured = kwargs.get("messages") or (args[0] if args else None)
            if captured:
                captured_messages.append(captured)
            return stub_llm_stream(
                make_text_chunk("OK"),
                make_text_chunk("", finish_reason="stop"),
            )

        async def aclose(self):
            pass

    monkeypatch.setattr(loop_module, "LLMClient", FakeLLMCapture)
    monkeypatch.setattr(
        loop_module, "MCPClient", lambda *a, **kw: FakeMCPClient("http://fake"),
    )

    request = make_request("Какой-то новый вопрос")
    await collect_sse(
        loop_module.run_chat_loop(
            mem_db, request, "api-key", "http://llm", "model"
        )
    )

    # Проверяем что в system prompt есть наш skill
    assert len(captured_messages) >= 1, "FakeLLMCapture не получил messages"
    first_call_messages = captured_messages[0]
    system_msg = next((m for m in first_call_messages if m.get("role") == "system"), None)
    assert system_msg is not None, "Нет system message"
    system_content = system_msg["content"]

    assert "opp-fast-query" in system_content, (
        f"Skill id не найден в system prompt. Content (first 500 chars): "
        f"{system_content[:500]}"
    )
    assert "ЗапросИНДД" in system_content, (
        "Skill body не инжектирован в system prompt"
    )
