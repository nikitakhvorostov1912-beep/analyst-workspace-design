"""#3: честный fallback когда у LLM нет источника ИТС.

ИТС-поиск идёт через живого Напарника (buddy MCP). Если он offline И статического
RAG-индекса тоже нет — модель не должна «делать вид, что искала», а обязана
спросить пользователя: искать по его базе или пройтись по типовой.
"""
from __future__ import annotations

from app.orchestrator.loop import _build_full_system_prompt, _its_unavailable_block


def test_block_empty_when_buddy_up():
    assert _its_unavailable_block(buddy_status="up", its_tool_available=False) == ""


def test_block_empty_when_rag_fallback_available():
    # Напарник лежит, но есть статический ИТС-RAG — пусть использует его, не спрашивает.
    assert _its_unavailable_block(buddy_status="down", its_tool_available=True) == ""


def test_block_empty_when_unknown_not_yet_pinged():
    # «unknown» — статус ещё не подтверждён; не дёргаем пользователя ложно.
    assert _its_unavailable_block(buddy_status="unknown", its_tool_available=False) == ""


def test_block_present_when_buddy_down_no_rag():
    b = _its_unavailable_block(buddy_status="down", its_tool_available=False)
    assert b != ""
    assert "clarify_question" in b
    assert "вашей базе" in b.lower() or "вашей базе" in b
    assert "типов" in b  # «типовой конфигурации»


def test_block_present_when_buddy_disabled_no_rag():
    b = _its_unavailable_block(buddy_status="disabled", its_tool_available=False)
    assert b != ""
    assert "clarify_question" in b


def test_full_prompt_includes_its_block():
    p = _build_full_system_prompt("", "", "", its_block="БЛОК-ИТС-МАРКЕР-XYZ")
    assert "БЛОК-ИТС-МАРКЕР-XYZ" in p


def test_full_prompt_omits_empty_its_block():
    p = _build_full_system_prompt("mem", "", "", its_block="")
    # пустой блок не должен добавлять лишних пустых секций перед памятью
    assert "ИТС НЕДОСТУПЕН" not in p
