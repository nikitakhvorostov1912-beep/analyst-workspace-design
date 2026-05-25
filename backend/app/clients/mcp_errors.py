"""User-facing классификация ошибок ping подключения к MCP.

Отличается от `orchestrator/error_classifier.py`:
    - тот — для loop retry decision (Action.RETRY / ABORT и т.п.)
    - этот — для **диагностики аналитику**: что конкретно сломано и что чинить.

Используется:
    - в `routes/connections.py:ping_connection` — структурированный лог + UI message
    - в `routes/diagnostics.py:connection_diagnostics` — полный отчёт для скачивания
"""

from __future__ import annotations

import os
import socket
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx

from app.clients.mcp import MCPDisconnectedError, MCPError


@dataclass(frozen=True)
class PingFailure:
    """Структурированное описание ошибки ping для лога и UI.

    error_class — машинно-читаемый код, frontend по нему выбирает иконку/цвет.
    hint — человеческое сообщение на русском, готовое к показу в UI.
    exception_type/message — полные (не обрезанные), для разработчика в логе.
    """

    error_class: str
    hint: str
    exception_type: str
    exception_message: str


# Маркеры в тексте httpx исключений. httpx не имеет отдельных классов
# для всех вариантов отказа TCP — приходится разбирать строку.
_CONNECT_REFUSED_MARKERS = (
    "all connection attempts failed",  # типичный httpx.ConnectError при ECONNREFUSED
    "connection refused",
    "winerror 10061",       # Windows: WSAECONNREFUSED
    "errno 111",            # Linux: ECONNREFUSED
)

_DNS_MARKERS = (
    "name or service not known",
    "nodename nor servname provided",
    "name resolution",
    "getaddrinfo failed",
    "winerror 11001",       # Windows: WSAHOST_NOT_FOUND
    "winerror 11004",       # Windows: WSANO_DATA
)

_PROXY_MARKERS = (
    "proxy authentication",
    "bad gateway",
    "502 bad gateway",
    "proxyerror",
)


def classify_ping_error(exc: Exception, endpoint: str) -> PingFailure:
    """Классифицирует исключение ping в `PingFailure`.

    Порядок проверок намеренно от специфичного к общему — MCP-ошибки до
    HTTP-ошибок, HTTP-ошибки до сетевых, сетевые до unknown.
    """
    msg_lower = str(exc).lower()
    exc_type = f"{type(exc).__module__}.{type(exc).__qualname__}"
    exc_msg = str(exc)
    host_port = _extract_host_port(endpoint)

    if isinstance(exc, MCPDisconnectedError):
        return PingFailure(
            error_class="mcp_disconnected",
            hint=(
                "Соединение с MCP-сервером оборвалось во время initialize. "
                "Перезапустите обработку MCP Toolkit в 1С."
            ),
            exception_type=exc_type,
            exception_message=exc_msg,
        )

    if isinstance(exc, MCPError):
        return PingFailure(
            error_class="mcp_protocol_error",
            hint=(
                "MCP-сервер ответил, но протокольно отказал (JSON-RPC error). "
                "Проверьте версию обработки MCP Toolkit в 1С — она должна поддерживать "
                "протокол 2025-03-26."
            ),
            exception_type=exc_type,
            exception_message=exc_msg,
        )

    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return PingFailure(
            error_class="http_status",
            hint=(
                f"Сервер по адресу {host_port} ответил HTTP {status}. "
                "Похоже, это не MCP-сервер, либо неверный путь /mcp. "
                "Проверьте адрес целиком."
            ),
            exception_type=exc_type,
            exception_message=exc_msg,
        )

    if isinstance(exc, httpx.ProxyError):
        return PingFailure(
            error_class="proxy_error",
            hint=(
                "Системный прокси перехватил запрос к 1С. "
                "Для localhost backend должен ходить мимо прокси (`trust_env=False`) — "
                "если эта ошибка дошла сюда, значит endpoint не распознан как локальный. "
                "Проверьте что в адресе используется 127.0.0.1 или localhost."
            ),
            exception_type=exc_type,
            exception_message=exc_msg,
        )

    if isinstance(exc, (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout)):
        return PingFailure(
            error_class="timeout",
            hint=(
                f"Таймаут при подключении к {host_port}. "
                "Сервер либо подвис, либо очень медленно отвечает. "
                "Перезапустите обработку MCP Toolkit в 1С."
            ),
            exception_type=exc_type,
            exception_message=exc_msg,
        )

    if isinstance(exc, httpx.ConnectError):
        if any(m in msg_lower for m in _DNS_MARKERS):
            return PingFailure(
                error_class="dns_failed",
                hint=(
                    f"Не удалось разрезолвить хост '{host_port}'. "
                    "Проверьте написание адреса — для локальной 1С используйте "
                    "`127.0.0.1` или `localhost`."
                ),
                exception_type=exc_type,
                exception_message=exc_msg,
            )
        if any(m in msg_lower for m in _PROXY_MARKERS):
            return PingFailure(
                error_class="proxy_error",
                hint=(
                    "Запрос ушёл через прокси и тот отдал ошибку. "
                    "Backend отключает прокси для localhost — проверьте что "
                    "адрес содержит 127.0.0.1 или localhost."
                ),
                exception_type=exc_type,
                exception_message=exc_msg,
            )
        if any(m in msg_lower for m in _CONNECT_REFUSED_MARKERS):
            return PingFailure(
                error_class="tcp_refused",
                hint=(
                    f"Сервер не слушает {host_port}. Проверьте по порядку: "
                    "1) В 1С открыта обработка MCP Toolkit и на вкладке "
                    "«Встроенный сервер» нажата кнопка «Запустить». "
                    f"2) Порт в обработке совпадает с {host_port} "
                    "(по умолчанию там 6010 — если в настройках 1С Аналитика "
                    "указан другой, исправьте либо в одном, либо в другом). "
                    "3) Антивирус или файрвол не блокирует процесс 1cv8.exe. "
                    "4) В адресе используется 127.0.0.1, а не localhost "
                    "(на Windows localhost иногда уходит в IPv6 и сервер его не слышит)."
                ),
                exception_type=exc_type,
                exception_message=exc_msg,
            )
        return PingFailure(
            error_class="network_error",
            hint=(
                f"Сетевая ошибка при подключении к {host_port}. "
                "Проверьте сеть и доступность хоста."
            ),
            exception_type=exc_type,
            exception_message=exc_msg,
        )

    if isinstance(exc, httpx.RequestError):
        return PingFailure(
            error_class="network_error",
            hint=f"Ошибка HTTP-запроса к {host_port}.",
            exception_type=exc_type,
            exception_message=exc_msg,
        )

    return PingFailure(
        error_class="unknown",
        hint=(
            f"Необработанная ошибка типа {exc_type}. "
            "Соберите диагностику и пришлите разработчику."
        ),
        exception_type=exc_type,
        exception_message=exc_msg,
    )


def _extract_host_port(endpoint: str) -> str:
    """`http://localhost:6003/mcp` → `localhost:6003`. Фолбэк — endpoint as-is."""
    try:
        u = urlparse(endpoint)
        if u.hostname and u.port:
            return f"{u.hostname}:{u.port}"
        return u.hostname or endpoint
    except Exception:  # noqa: BLE001
        return endpoint


def collect_local_diagnostics(endpoint: str) -> dict[str, Any]:
    """Доп. контекст для local endpoint: DNS, прокси-env, probe соседних портов.

    Вызывать ТОЛЬКО для loopback endpoint'ов (`_is_local_endpoint`) — иначе
    probe_ports_local не имеет смысла для удалённого хоста.
    """
    out: dict[str, Any] = {}

    # DNS resolve — что getaddrinfo() возвращает для host'а endpoint'а.
    # Помогает поймать классику Windows: localhost → ['::1', '127.0.0.1'].
    try:
        u = urlparse(endpoint)
        host = u.hostname or ""
        if host:
            try:
                infos = socket.getaddrinfo(
                    host,
                    u.port or 80,
                    proto=socket.IPPROTO_TCP,
                )
                out["resolved_addresses"] = sorted({info[4][0] for info in infos})
            except socket.gaierror as exc:
                out["resolved_addresses"] = []
                out["resolve_error"] = str(exc)
    except Exception as exc:  # noqa: BLE001
        out["parse_error"] = str(exc)

    # Прокси-env — даже если backend сам обходит прокси для localhost,
    # полезно увидеть что у пользователя стоит (часто Hiddify/корп. прокси
    # фоном меняют curl-логику для других инструментов).
    proxy_env: dict[str, str] = {}
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY"):
        for variant in (key, key.lower()):
            value = os.environ.get(variant)
            if value:
                proxy_env[variant] = value
                break
    out["proxy_env"] = proxy_env

    # Probe стандартных портов MCP Toolkit на 127.0.0.1.
    # 6010 — default встроенного сервера, 6003 — частый альтернатив,
    # 6080 — иногда используется для HTTP-сервиса базы. Если порт в настройках
    # 6003 а на самом деле слушается 6010 — диагностика это сразу покажет.
    probes: dict[str, bool] = {}
    for port in (6003, 6010, 6080):
        probes[str(port)] = _probe_port("127.0.0.1", port, timeout=0.3)
    out["probe_ports_local"] = probes

    return out


def _probe_port(host: str, port: int, timeout: float = 0.3) -> bool:
    """True если TCP-connect к host:port проходит за `timeout` сек."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((host, port))
        return True
    except OSError:
        return False
    finally:
        try:
            sock.close()
        except OSError:
            pass
