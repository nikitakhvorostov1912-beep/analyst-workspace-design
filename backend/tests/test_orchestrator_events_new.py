"""Новые тесты ErrorEvent.retry_after_s (Plan 03-01, Task 1 RED)."""

import json

import pytest

from app.orchestrator.events import ErrorEvent


def _parse_sse(raw: str) -> tuple[str, dict]:
    from app.orchestrator.events import format_sse
    lines = raw.strip().split("\n")
    event_name = ""
    data_str = ""
    for line in lines:
        if line.startswith("event: "):
            event_name = line[7:]
        elif line.startswith("data: "):
            data_str = line[6:]
    return event_name, json.loads(data_str)


def test_error_event_has_retry_after_s_optional_null_default():
    """ErrorEvent без retry_after_s → поле существует, значение null."""
    event = ErrorEvent(message="test error", code="llm_rate_limit")
    data = json.loads(event.model_dump_json())
    assert "retry_after_s" in data
    assert data["retry_after_s"] is None


def test_error_event_with_retry_after_30():
    """ErrorEvent(retry_after_s=30) → JSON содержит retry_after_s: 30."""
    event = ErrorEvent(message="too many", code="llm_rate_limit", retry_after_s=30)
    data = json.loads(event.model_dump_json())
    assert data["retry_after_s"] == 30


def test_error_event_code_literal_accepts_all_known_codes():
    """ErrorEvent принимает все 12 легитимных кодов без ValidationError."""
    valid_codes = [
        "llm_rate_limit", "llm_invalid_key", "llm_network_error", "llm_server_error",
        "mcp_disconnected", "mcp_connect_error", "tool_loop_limit", "unknown_channel",
        "init_error", "internal_error", "user_declined", "dangerous_keyword_blocked",
    ]
    for code in valid_codes:
        event = ErrorEvent(message="test", code=code)
        assert event.code == code
