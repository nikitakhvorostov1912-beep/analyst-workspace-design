"""Tests for message sanitization (Sprint 2 — Hermes E6)."""

from __future__ import annotations

import json

from app.orchestrator.sanitize import (
    repair_message_sequence,
    sanitize_message,
    sanitize_messages,
    sanitize_text,
    sanitize_tool_call_arguments,
)


def test_sanitize_text_removes_surrogates() -> None:
    # Lone surrogate D800 — должна стать '?'
    dirty = "Hello\ud800World"
    assert sanitize_text(dirty) == "Hello?World"


def test_sanitize_text_removes_nul() -> None:
    dirty = "Привет\x00мир"
    assert sanitize_text(dirty) == "Приветмир"


def test_sanitize_text_keeps_allowed_whitespace() -> None:
    text = "Line1\nLine2\tTab\rCR"
    # \n \t \r — допустимы, не должны быть удалены
    assert sanitize_text(text) == "Line1\nLine2\tTab\rCR"


def test_sanitize_text_empty() -> None:
    assert sanitize_text("") == ""


def test_sanitize_text_removes_control() -> None:
    # \x01 \x05 \x1f — управляющие, удаляются
    assert sanitize_text("A\x01B\x05C\x1fD") == "ABCD"


def test_sanitize_tool_call_arguments_none() -> None:
    assert sanitize_tool_call_arguments(None) == "{}"


def test_sanitize_tool_call_arguments_empty_string() -> None:
    assert sanitize_tool_call_arguments("") == "{}"


def test_sanitize_tool_call_arguments_dict() -> None:
    result = sanitize_tool_call_arguments({"key": "value", "n": 42})
    parsed = json.loads(result)
    assert parsed == {"key": "value", "n": 42}


def test_sanitize_tool_call_arguments_str_valid_json() -> None:
    result = sanitize_tool_call_arguments('{"x": 1}')
    assert json.loads(result) == {"x": 1}


def test_sanitize_tool_call_arguments_str_invalid_json() -> None:
    """Невалидный JSON-string — оставляем как есть, но чистим."""
    dirty = '{"x"\x00: 1'
    result = sanitize_tool_call_arguments(dirty)
    # NUL должен быть убран
    assert "\x00" not in result


def test_sanitize_message_user_content() -> None:
    msg = {"role": "user", "content": "Hello\x00World"}
    out = sanitize_message(msg)
    assert out["content"] == "HelloWorld"
    # Immutability: исходный не изменился
    assert msg["content"] == "Hello\x00World"


def test_sanitize_message_multimodal_parts() -> None:
    msg = {
        "role": "user",
        "content": [
            {"type": "text", "text": "Hello\x01"},
            {"type": "image_url", "image_url": {"url": "data:..."}},
        ],
    }
    out = sanitize_message(msg)
    assert out["content"][0]["text"] == "Hello"
    # image_url нетронут
    assert out["content"][1]["image_url"]["url"] == "data:..."


def test_sanitize_message_tool_calls() -> None:
    msg = {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "t1",
                "type": "function",
                "function": {"name": "search", "arguments": ""},
            }
        ],
    }
    out = sanitize_message(msg)
    # Пустые arguments → '{}'
    assert out["tool_calls"][0]["function"]["arguments"] == "{}"


def test_sanitize_message_assistant_reasoning_only_gets_empty_content() -> None:
    msg = {
        "role": "assistant",
        "content": None,
        "reasoning_content": "thinking...",
    }
    out = sanitize_message(msg)
    # Content стал '' чтобы OpenAI API не падал.
    assert out["content"] == ""


def test_sanitize_messages_list() -> None:
    msgs = [
        {"role": "user", "content": "Hi\x00"},
        {"role": "assistant", "content": "Hello\x01"},
    ]
    out = sanitize_messages(msgs)
    assert out[0]["content"] == "Hi"
    assert out[1]["content"] == "Hello"


def test_repair_message_sequence_drops_orphan_tool() -> None:
    msgs = [
        {"role": "user", "content": "hi"},
        # Orphan: нет соответствующего assistant.tool_calls
        {"role": "tool", "tool_call_id": "ghost", "content": "result"},
        {"role": "assistant", "content": "ok"},
    ]
    out = repair_message_sequence(msgs)
    # Orphan tool message убран
    assert len(out) == 2
    assert out[0]["role"] == "user"
    assert out[1]["role"] == "assistant"


def test_repair_message_sequence_keeps_valid_tool() -> None:
    msgs = [
        {"role": "user", "content": "hi"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [{"id": "t1", "type": "function", "function": {"name": "x", "arguments": "{}"}}],
        },
        {"role": "tool", "tool_call_id": "t1", "content": "result"},
        {"role": "assistant", "content": "done"},
    ]
    out = repair_message_sequence(msgs)
    assert len(out) == 4


def test_repair_message_sequence_empty() -> None:
    assert repair_message_sequence([]) == []
