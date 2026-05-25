"""SSRF guard для пользовательских MCP endpoint'ов.

Пользователь вводит URL MCP-сервера в Settings → Connections. Без валидации
атакующий мог бы указать `http://169.254.169.254/` (AWS metadata),
`http://127.0.0.1:6379/` (локальный Redis), `http://192.168.1.1/` (роутер),
а backend на серверной стороне сделал бы запрос.

Атаки:
- SSRF к cloud metadata endpoints (AWS / GCP / Azure)
- SSRF к интранет-сервисам (внутренние REST API, БД, админ-панели)
- SSRF к локальным портам (Redis 6379, PostgreSQL 5432, etc.)
- DNS rebinding: домен резолвится в публичный IP при первой проверке,
  потом в `169.254.169.254` при реальном запросе

Защита:
1. Валидация URL: схема http/https, есть хост
2. Резолв всех IP хоста через socket.getaddrinfo
3. Reject если ХОТЯ БЫ ОДИН резолвенный IP попадает в blocked ranges
4. Whitelist для known-safe localhost (127.0.0.1, ::1, "localhost"):
   они разрешены ТОЛЬКО потому что MCP Toolkit обычно работает рядом

Использование:
    from app.security.mcp_endpoint_validator import (
        validate_mcp_endpoint,
        MCPEndpointError,
    )

    try:
        validate_mcp_endpoint("http://example.com/mcp")
    except MCPEndpointError as exc:
        raise HTTPException(status_code=400, detail=exc.user_message)
"""

from __future__ import annotations

import ipaddress
import logging
import socket
from dataclasses import dataclass
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# DNS resolve timeout — если резолв занимает > N секунд, считаем что endpoint
# подозрительный (нормальный домен резолвится за < 1 сек).
_DNS_TIMEOUT_S = 5.0

# Известные «безопасные» hostnames для MCP-сервера.
# Эти hostnames всегда разрешены даже если они резолвятся в loopback диапазон.
# Основной use-case: пользователь запустил MCP Toolkit EPF на той же машине.
_LOCALHOST_HOSTNAMES = frozenset({
    "localhost",
    "127.0.0.1",
    "::1",
    # IPv6 в URL формате
    "[::1]",
})

# Разрешённые схемы. Никаких file://, ftp://, gopher:// — это классические
# SSRF-векторы.
_ALLOWED_SCHEMES = frozenset({"http", "https"})


class MCPEndpointError(ValueError):
    """Базовое исключение для проблем с endpoint.

    Содержит человеко-читаемое сообщение (user_message) для показа в UI
    и техническое (str(exc)) для логов.
    """

    def __init__(self, message: str, user_message: str | None = None) -> None:
        super().__init__(message)
        self.user_message = user_message or message


@dataclass(frozen=True)
class ValidationResult:
    """Результат валидации endpoint."""

    hostname: str
    port: int | None
    scheme: str
    resolved_ips: tuple[str, ...]
    is_localhost: bool


def _is_localhost_hostname(hostname: str) -> bool:
    """Проверяет является ли hostname одним из known-safe localhost имён.

    Sensitive к регистру (DNS case-insensitive, но мы lowercase перед сравнением).
    """
    return hostname.lower() in _LOCALHOST_HOSTNAMES


def _is_blocked_ip(ip_str: str) -> tuple[bool, str | None]:
    """Проверяет попадает ли IP в blocked range.

    Возвращает (blocked, reason). Reason заполнен только если blocked=True.
    """
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        # Не валидный IP — это странно, но безопасно блокируем.
        return True, f"невалидный IP-адрес: {ip_str}"

    # Loopback (127.0.0.0/8 и ::1) — блокируем кроме явных 127.0.0.1 / ::1.
    # Это покрывает случаи когда хитрый домен резолвится в 127.0.0.X (X != 1).
    if ip.is_loopback:
        if ip_str not in ("127.0.0.1", "::1"):
            return True, f"запрещённый loopback-адрес: {ip_str}"
        return False, None

    # Link-local: 169.254.0.0/16 (AWS metadata!) + IPv6 fe80::/10.
    if ip.is_link_local:
        return True, f"запрещённый link-local адрес (вкл. cloud metadata): {ip_str}"

    # RFC 1918 private + IPv6 unique local (fc00::/7).
    if ip.is_private:
        # is_private включает loopback и link-local, но мы уже их отсеяли выше.
        # Остаются: 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, fc00::/7.
        return True, f"запрещённый приватный/интранет-адрес: {ip_str}"

    # Multicast (224.0.0.0/4 + ff00::/8).
    if ip.is_multicast:
        return True, f"запрещённый multicast-адрес: {ip_str}"

    # Reserved (240.0.0.0/4 — class E, etc.) и unspecified (0.0.0.0).
    if ip.is_reserved or ip.is_unspecified:
        return True, f"запрещённый зарезервированный адрес: {ip_str}"

    return False, None


def _resolve_hostname(hostname: str) -> tuple[str, ...]:
    """Резолвит hostname в IP-адреса через socket.getaddrinfo.

    Возвращает пустой tuple если DNS не резолвится — это НЕ SSRF риск:
    нет резолвенного IP = нет таргета для атаки. Пользователь увидит
    проблему при ping (502 «MCP не отвечает»).

    Использует timeout, чтобы не повиснуть на медленном DNS.
    """
    original_timeout = socket.getdefaulttimeout()
    try:
        socket.setdefaulttimeout(_DNS_TIMEOUT_S)
        # AF_UNSPEC = и IPv4, и IPv6.
        # SOCK_STREAM = TCP (нам нужны IP-адреса, не сервисная информация).
        infos = socket.getaddrinfo(
            hostname, None, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM
        )
    except (socket.gaierror, OSError) as exc:
        # DNS failure / timeout — endpoint просто недоступен сейчас. Не SSRF.
        # Атакующий не может через неразрешимый hostname получить response
        # с какого-либо real target. UX: пользователь может сохранить адрес
        # «на потом» (MCP сервер ещё не поднят) — это валидный сценарий.
        logger.info(
            "DNS lookup для '%s' не удался (endpoint будет saved, но pingable=False): %s",
            hostname,
            exc,
        )
        return ()
    finally:
        socket.setdefaulttimeout(original_timeout)

    # Извлекаем уникальные IP. infos = [(family, type, proto, canon, sockaddr), ...]
    # sockaddr для IPv4 = (ip, port), для IPv6 = (ip, port, flow, scope).
    ips = {info[4][0] for info in infos}
    return tuple(sorted(ips))


def validate_mcp_endpoint(endpoint: str) -> ValidationResult:
    """Валидирует пользовательский MCP endpoint на SSRF риски.

    Параметры:
        endpoint: URL вида http://host[:port][/path].

    Возвращает:
        ValidationResult с резолвенными IP — можно использовать для коннекта.

    Raises:
        MCPEndpointError: endpoint небезопасный (схема, hostname, IP).
    """
    if not endpoint or not isinstance(endpoint, str):
        raise MCPEndpointError(
            "endpoint пустой или не строка",
            user_message="Адрес MCP не указан.",
        )

    # Парсим URL.
    try:
        parsed = urlparse(endpoint.strip())
    except ValueError as exc:
        raise MCPEndpointError(
            f"Не удалось распарсить URL '{endpoint}': {exc}",
            user_message=f"Адрес '{endpoint}' некорректен (не URL).",
        ) from exc

    scheme = (parsed.scheme or "").lower()
    if scheme not in _ALLOWED_SCHEMES:
        raise MCPEndpointError(
            f"схема '{scheme}' запрещена (разрешены http/https)",
            user_message=(
                f"Адрес должен начинаться с http:// или https://, "
                f"а не {scheme}://."
            ),
        )

    # parsed.hostname приводит к lowercase, удаляет порт и user:pass.
    hostname = parsed.hostname
    if not hostname:
        raise MCPEndpointError(
            f"hostname отсутствует в URL '{endpoint}'",
            user_message=f"Адрес '{endpoint}' не содержит hostname.",
        )

    # Whitelist для localhost. Резолвить не нужно — мы и так знаем что это
    # 127.0.0.1 / ::1, основной use-case для MCP Toolkit EPF.
    is_localhost = _is_localhost_hostname(hostname)

    if is_localhost:
        # Для localhost подставляем явный 127.0.0.1 как «резолвенный IP».
        # Реальный коннект всё равно пойдёт по hostname.
        resolved_ips: tuple[str, ...] = ("127.0.0.1",)
    else:
        # Внешний hostname — резолвим и проверяем КАЖДЫЙ IP.
        # Если DNS не резолвится (пустой tuple) — endpoint валидный сохраняемый,
        # просто неработающий. Без резолвенного IP нет SSRF target.
        resolved_ips = _resolve_hostname(hostname)

        # Проверяем каждый IP на blocked ranges.
        for ip in resolved_ips:
            blocked, reason = _is_blocked_ip(ip)
            if blocked:
                logger.warning(
                    "SSRF guard: rejected endpoint %s (hostname=%s, ip=%s, reason=%s)",
                    endpoint,
                    hostname,
                    ip,
                    reason,
                )
                raise MCPEndpointError(
                    f"endpoint '{endpoint}' резолвится в blocked IP: {reason}",
                    user_message=(
                        f"Адрес '{hostname}' резолвится в небезопасный IP ({ip}). "
                        "Запрещены приватные (10.x, 192.168.x), link-local (169.254.x), "
                        "loopback и зарезервированные адреса. "
                        "Если MCP-сервер локальный — используйте localhost или 127.0.0.1."
                    ),
                )

    return ValidationResult(
        hostname=hostname,
        port=parsed.port,
        scheme=scheme,
        resolved_ips=resolved_ips,
        is_localhost=is_localhost,
    )
