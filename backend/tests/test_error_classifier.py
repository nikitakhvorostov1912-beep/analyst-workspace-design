"""Tests for error_classifier (Sprint 2 — Hermes E1)."""

from __future__ import annotations

from unittest.mock import Mock

import httpx
import pytest

from app.clients.llm import LLMRateLimitError
from app.clients.mcp import MCPDisconnectedError, MCPError
from app.orchestrator.error_classifier import (
    Action,
    FailoverReason,
    classify,
)


def _make_response(status: int, body: str = "", headers: dict | None = None) -> httpx.Response:
    return httpx.Response(
        status_code=status,
        content=body.encode("utf-8") if body else b"",
        headers=headers or {},
    )


def test_rate_limit_error() -> None:
    response = _make_response(429)
    request = httpx.Request("POST", "http://x")
    exc = LLMRateLimitError("rate limit hit", request=request, response=response)
    exc.retry_after_s = 30
    decision = classify(exc)
    assert decision.reason == FailoverReason.RATE_LIMIT
    assert decision.action == Action.ABORT
    assert decision.retry_after_s == 30


def test_mcp_disconnected() -> None:
    exc = MCPDisconnectedError("connection lost")
    decision = classify(exc)
    assert decision.reason == FailoverReason.MCP_DISCONNECTED
    assert decision.action == Action.ABORT
    assert decision.error_code == "mcp_disconnected"


def test_mcp_protocol_error() -> None:
    exc = MCPError(-32602, "invalid params")
    decision = classify(exc)
    assert decision.reason == FailoverReason.MCP_PROTOCOL
    assert decision.action == Action.ABORT


def test_http_429_with_retry_after() -> None:
    response = _make_response(429, headers={"retry-after": "12"})
    request = httpx.Request("POST", "http://x")
    exc = httpx.HTTPStatusError("429", request=request, response=response)
    decision = classify(exc, context={"where": "llm"})
    assert decision.reason == FailoverReason.RATE_LIMIT
    assert decision.retry_after_s == 12.0


def test_http_401_auth_fail() -> None:
    response = _make_response(401)
    request = httpx.Request("POST", "http://x")
    exc = httpx.HTTPStatusError("401", request=request, response=response)
    decision = classify(exc, context={"where": "llm"})
    assert decision.reason == FailoverReason.AUTH
    assert decision.action == Action.ABORT
    assert decision.error_code == "llm_invalid_key"


def test_http_413_context_overflow() -> None:
    response = _make_response(413, body="Request entity too large")
    request = httpx.Request("POST", "http://x")
    exc = httpx.HTTPStatusError("413", request=request, response=response)
    decision = classify(exc)
    assert decision.reason == FailoverReason.CONTEXT_OVERFLOW
    assert decision.action == Action.COMPRESS_AND_RETRY


def test_http_400_body_context_length() -> None:
    """LLM-провайдеры часто возвращают 400 с body 'context length exceeded'."""
    body = '{"error": {"message": "This model has a maximum context length of 128000 tokens..."}}'
    response = _make_response(400, body=body)
    request = httpx.Request("POST", "http://x")
    exc = httpx.HTTPStatusError("400", request=request, response=response)
    decision = classify(exc)
    assert decision.reason == FailoverReason.CONTEXT_OVERFLOW
    assert decision.action == Action.COMPRESS_AND_RETRY


def test_http_500_retry() -> None:
    response = _make_response(500)
    request = httpx.Request("POST", "http://x")
    exc = httpx.HTTPStatusError("500", request=request, response=response)
    decision = classify(exc)
    assert decision.reason == FailoverReason.HTTP_5XX
    assert decision.action == Action.RETRY


def test_http_502_retry() -> None:
    response = _make_response(502)
    request = httpx.Request("POST", "http://x")
    exc = httpx.HTTPStatusError("502", request=request, response=response)
    decision = classify(exc)
    assert decision.reason == FailoverReason.HTTP_5XX


def test_http_404_abort() -> None:
    response = _make_response(404)
    request = httpx.Request("POST", "http://x")
    exc = httpx.HTTPStatusError("404", request=request, response=response)
    decision = classify(exc)
    assert decision.reason == FailoverReason.HTTP_4XX
    assert decision.action == Action.ABORT


def test_connect_error() -> None:
    exc = httpx.ConnectError("connection refused")
    decision = classify(exc, context={"where": "llm"})
    assert decision.reason == FailoverReason.TRANSIENT_NETWORK
    assert decision.action == Action.RETRY


def test_read_timeout() -> None:
    exc = httpx.ReadTimeout("timeout")
    decision = classify(exc)
    assert decision.reason == FailoverReason.TRANSIENT_NETWORK
    assert decision.action == Action.RETRY


def test_unknown_exception_aborts() -> None:
    exc = RuntimeError("unknown error")
    decision = classify(exc)
    assert decision.reason == FailoverReason.UNKNOWN
    assert decision.action == Action.ABORT
    assert decision.log_level == "error"


def test_context_overflow_via_message_only() -> None:
    """Если HTTPStatusError даёт неявную context-overflow строку в exc str."""
    exc = RuntimeError("Request too long: context length exceeded")
    decision = classify(exc)
    assert decision.reason == FailoverReason.CONTEXT_OVERFLOW
    assert decision.action == Action.COMPRESS_AND_RETRY


def test_retry_after_parsing_invalid() -> None:
    """Невалидный retry-after header → None."""
    response = _make_response(429, headers={"retry-after": "Wed, 21 Oct 2015 07:28:00 GMT"})
    request = httpx.Request("POST", "http://x")
    exc = httpx.HTTPStatusError("429", request=request, response=response)
    decision = classify(exc)
    assert decision.retry_after_s is None  # date format не поддерживаем
