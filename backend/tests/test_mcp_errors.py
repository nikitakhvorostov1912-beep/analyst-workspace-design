"""Unit-тесты для `app.clients.mcp_errors`.

Покрывают все ветки classify_ping_error — без сети, через искусственные
исключения. Без них регрессии в hint-строках уйдут незамеченными
(аналитик увидит «unknown error» вместо подсказки что чинить).
"""

from __future__ import annotations

import socket
from unittest.mock import patch

import httpx
import pytest

from app.clients.mcp import MCPDisconnectedError, MCPError
from app.clients.mcp_errors import (
    classify_ping_error,
    collect_local_diagnostics,
)


def _make_connect_error(msg: str) -> httpx.ConnectError:
    """Создаёт ConnectError с заданным текстом — для проверки маркеров."""
    return httpx.ConnectError(msg)


# ---------- MCP-специфичные ----------


def test_mcp_disconnected_error() -> None:
    failure = classify_ping_error(
        MCPDisconnectedError("session lost"),
        "http://127.0.0.1:6010/mcp",
    )
    assert failure.error_class == "mcp_disconnected"
    assert "перезапустите" in failure.hint.lower() or "перезапус" in failure.hint.lower()
    assert failure.exception_type.endswith("MCPDisconnectedError")


def test_mcp_protocol_error() -> None:
    failure = classify_ping_error(
        MCPError(-32601, "Method not found"),
        "http://127.0.0.1:6010/mcp",
    )
    assert failure.error_class == "mcp_protocol_error"
    assert "MCP Toolkit" in failure.hint


# ---------- HTTP-уровень ----------


def test_http_status_error() -> None:
    response = httpx.Response(404, text="not found")
    exc = httpx.HTTPStatusError("Not Found", request=httpx.Request("POST", "http://x"), response=response)
    failure = classify_ping_error(exc, "http://127.0.0.1:6010/mcp")
    assert failure.error_class == "http_status"
    assert "404" in failure.hint
    assert "127.0.0.1:6010" in failure.hint


# ---------- Сетевые ошибки ----------


def test_connect_timeout() -> None:
    failure = classify_ping_error(
        httpx.ConnectTimeout("timed out"),
        "http://127.0.0.1:6010/mcp",
    )
    assert failure.error_class == "timeout"
    assert "127.0.0.1:6010" in failure.hint


def test_tcp_refused_via_httpx_marker() -> None:
    """`All connection attempts failed` — главный маркер ECONNREFUSED от httpx."""
    failure = classify_ping_error(
        _make_connect_error("All connection attempts failed"),
        "http://127.0.0.1:6003/mcp",
    )
    assert failure.error_class == "tcp_refused"
    assert "127.0.0.1:6003" in failure.hint
    # Hint должен явно упомянуть проверки: обработка / порт / антивирус / 127.0.0.1
    lower_hint = failure.hint.lower()
    assert "обработк" in lower_hint  # «обработка MCP Toolkit»
    assert "порт" in lower_hint
    assert "127.0.0.1" in failure.hint


def test_tcp_refused_via_windows_errno() -> None:
    failure = classify_ping_error(
        _make_connect_error("[WinError 10061] No connection could be made"),
        "http://127.0.0.1:6010/mcp",
    )
    assert failure.error_class == "tcp_refused"


def test_tcp_refused_via_posix_errno() -> None:
    failure = classify_ping_error(
        _make_connect_error("[Errno 111] Connection refused"),
        "http://127.0.0.1:6010/mcp",
    )
    assert failure.error_class == "tcp_refused"


def test_dns_failed_via_windows_errno() -> None:
    failure = classify_ping_error(
        _make_connect_error("[WinError 11001] getaddrinfo failed"),
        "http://nonexistent.invalid:6010/mcp",
    )
    assert failure.error_class == "dns_failed"
    assert "nonexistent.invalid" in failure.hint


def test_dns_failed_via_posix_text() -> None:
    failure = classify_ping_error(
        _make_connect_error("Name or service not known"),
        "http://nope.local:6010/mcp",
    )
    assert failure.error_class == "dns_failed"


def test_proxy_error_class() -> None:
    failure = classify_ping_error(
        httpx.ProxyError("proxy auth required"),
        "http://127.0.0.1:6010/mcp",
    )
    assert failure.error_class == "proxy_error"


def test_generic_request_error() -> None:
    failure = classify_ping_error(
        httpx.RequestError("something went wrong"),
        "http://127.0.0.1:6010/mcp",
    )
    assert failure.error_class == "network_error"


# ---------- Unknown ----------


def test_unknown_exception_type() -> None:
    failure = classify_ping_error(
        RuntimeError("unexpected"),
        "http://127.0.0.1:6010/mcp",
    )
    assert failure.error_class == "unknown"
    assert "RuntimeError" in failure.hint
    # Полный exception_message сохраняется (не обрезается до 200)
    assert failure.exception_message == "unexpected"


# ---------- collect_local_diagnostics ----------


def test_collect_local_diagnostics_includes_resolved_addresses() -> None:
    diag = collect_local_diagnostics("http://127.0.0.1:6010/mcp")
    assert "resolved_addresses" in diag
    assert "127.0.0.1" in diag["resolved_addresses"]


def test_collect_local_diagnostics_includes_probe_ports() -> None:
    diag = collect_local_diagnostics("http://127.0.0.1:6010/mcp")
    assert "probe_ports_local" in diag
    assert set(diag["probe_ports_local"].keys()) == {"6003", "6010", "6080"}
    # Каждое значение — bool
    for v in diag["probe_ports_local"].values():
        assert isinstance(v, bool)


def test_collect_local_diagnostics_reports_proxy_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HTTP_PROXY", "http://corp-proxy:8080")
    monkeypatch.setenv("NO_PROXY", "localhost,127.0.0.1")
    diag = collect_local_diagnostics("http://127.0.0.1:6010/mcp")
    assert diag["proxy_env"].get("HTTP_PROXY") == "http://corp-proxy:8080"
    assert diag["proxy_env"].get("NO_PROXY") == "localhost,127.0.0.1"


def test_collect_local_diagnostics_handles_dns_failure() -> None:
    # Имитируем gaierror через mock
    with patch("app.clients.mcp_errors.socket.getaddrinfo", side_effect=socket.gaierror("test")):
        diag = collect_local_diagnostics("http://nonexistent.invalid:6010/mcp")
    assert diag["resolved_addresses"] == []
    assert "resolve_error" in diag
