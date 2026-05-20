"""Tests for background_review (Sprint 3 — Hermes A5)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.learning.background_review import (
    ReviewDecision,
    _format_turn,
    _parse_decision,
    review_turn,
)
from app.learning.skill_store import SkillStore


class _FakeAuxOk:
    """Aux client, который всегда сохраняет skill."""

    def __init__(self, response: str) -> None:
        self._response = response
        self.calls: list[list[dict]] = []

    async def complete_with_fallback(self, messages, **_kwargs):
        self.calls.append(messages)
        return self._response


class _FakeAuxNone:
    async def complete_with_fallback(self, _messages, **_kwargs):
        return None


def test_parse_decision_save_true() -> None:
    raw = json.dumps({
        "save": True,
        "id": "opp-skill",
        "tags": ["opp", "query"],
        "body": "Когда юзер спрашивает X — делай Y, конкретно. Это длинный текст с инструкциями для сохранения и проверки длины.",
    })
    decision = _parse_decision(raw)
    assert decision.save is True
    assert decision.skill_id == "opp-skill"
    assert "opp" in decision.tags


def test_parse_decision_save_false() -> None:
    raw = json.dumps({"save": False})
    decision = _parse_decision(raw)
    assert decision.save is False
    assert decision.skill_id is None


def test_parse_decision_strips_code_fence() -> None:
    raw = "```json\n" + json.dumps({
        "save": True, "id": "skill_x",
        "tags": ["a"], "body": "x" * 100,
    }) + "\n```"
    decision = _parse_decision(raw)
    assert decision.save is True


def test_parse_decision_invalid_json() -> None:
    decision = _parse_decision("not valid json")
    assert decision.save is False


def test_parse_decision_body_too_short() -> None:
    raw = json.dumps({"save": True, "id": "x", "tags": [], "body": "short"})
    decision = _parse_decision(raw)
    assert decision.save is False  # body < 50 chars


def test_parse_decision_normalizes_skill_id() -> None:
    """Сложные символы в id заменяются на _."""
    raw = json.dumps({
        "save": True, "id": "skill with spaces!@#",
        "tags": [], "body": "x" * 100,
    })
    decision = _parse_decision(raw)
    assert decision.save is True
    assert " " not in decision.skill_id
    assert "@" not in decision.skill_id


def test_format_turn_includes_user_assistant_tools() -> None:
    out = _format_turn(
        "Сколько ОПП?",
        "Найдено 32.",
        [{"name": "execute_query", "args": {"q": "SELECT..."}, "duration_ms": 50}],
    )
    assert "Сколько ОПП" in out
    assert "Найдено 32" in out
    assert "execute_query" in out


@pytest.mark.asyncio
async def test_review_turn_saves_skill(tmp_path: Path) -> None:
    skills_root = tmp_path / "skills"
    store = SkillStore(skills_root, "ch1")
    body = "Это длинный текст skill, который должен сохраниться. Описывает паттерн запроса для конкретного случая."
    aux = _FakeAuxOk(json.dumps({
        "save": True, "id": "test_skill",
        "tags": ["query"], "body": body,
    }))

    decision = await review_turn(
        user_msg="Сколько ОПП?",
        assistant_msg="Найдено 32.",
        tool_calls=[],
        skill_store=store,
        aux_client=aux,
    )
    assert decision.save is True
    # Сохранён с provenance=agent
    skill = store.read("test_skill")
    assert skill is not None
    assert skill.provenance == "agent"


@pytest.mark.asyncio
async def test_review_turn_aux_returns_none(tmp_path: Path) -> None:
    skills_root = tmp_path / "skills"
    store = SkillStore(skills_root, "ch1")
    aux = _FakeAuxNone()
    decision = await review_turn(
        user_msg="?",
        assistant_msg="!",
        tool_calls=[],
        skill_store=store,
        aux_client=aux,
    )
    assert decision.save is False
    assert store.list_active() == []


@pytest.mark.asyncio
async def test_review_turn_empty_assistant_msg(tmp_path: Path) -> None:
    """Если ответ пустой — даже не дёргаем aux."""
    skills_root = tmp_path / "skills"
    store = SkillStore(skills_root, "ch1")
    aux = _FakeAuxOk('{"save":true,"id":"x","tags":[],"body":"' + "y" * 100 + '"}')
    decision = await review_turn(
        user_msg="?",
        assistant_msg="",
        tool_calls=[],
        skill_store=store,
        aux_client=aux,
    )
    assert decision.save is False
    assert aux.calls == []  # aux не вызывался
