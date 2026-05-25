"""SEC-1: SSRF guard для MCP endpoint.

Закрывает CRITICAL finding из общего аудита проекта.

Сценарии атак:
- AWS metadata: http://169.254.169.254/
- Локальные сервисы: http://127.0.0.1:6379/ (Redis), http://localhost:5432
- Интранет: http://192.168.1.1/, http://10.0.0.1/, http://172.16.0.1/
- Link-local IPv6: http://[fe80::1]/
- ULA IPv6: http://[fc00::1]/
- DNS rebinding: домен резолвится в private IP
- Альтернативные схемы: file:///, ftp://, gopher://
- Hostname без схемы
- Невалидные URL
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.security.mcp_endpoint_validator import (
    MCPEndpointError,
    ValidationResult,
    validate_mcp_endpoint,
)


# ----------------------------------------------------------------------------
# Группа 1: Whitelist для localhost (основной use-case MCP Toolkit EPF)
# ----------------------------------------------------------------------------


class TestLocalhostWhitelist:
    """localhost / 127.0.0.1 / ::1 разрешены без DNS-резолва."""

    def test_localhost_allowed(self) -> None:
        result = validate_mcp_endpoint("http://localhost:6010/mcp")
        assert result.hostname == "localhost"
        assert result.port == 6010
        assert result.scheme == "http"
        assert result.is_localhost is True

    def test_127_0_0_1_allowed(self) -> None:
        result = validate_mcp_endpoint("http://127.0.0.1:6010/mcp")
        assert result.hostname == "127.0.0.1"
        assert result.is_localhost is True

    def test_ipv6_localhost_allowed(self) -> None:
        result = validate_mcp_endpoint("http://[::1]:6010/mcp")
        # urlparse возвращает hostname без скобок.
        assert result.hostname == "::1"
        assert result.is_localhost is True

    def test_localhost_case_insensitive(self) -> None:
        # LOCALHOST, Localhost, lOcAlHoSt — всё ОК.
        result = validate_mcp_endpoint("http://LOCALHOST:6010/mcp")
        # urlparse приводит hostname к lowercase, поэтому проверяем как lower.
        assert result.hostname == "localhost"
        assert result.is_localhost is True

    def test_localhost_https_allowed(self) -> None:
        result = validate_mcp_endpoint("https://localhost:6443/secure-mcp")
        assert result.scheme == "https"
        assert result.is_localhost is True


# ----------------------------------------------------------------------------
# Группа 2: Невалидные схемы — file/ftp/gopher/etc.
# ----------------------------------------------------------------------------


class TestInvalidSchemes:
    """Схемы кроме http/https должны быть отвергнуты."""

    def test_file_scheme_rejected(self) -> None:
        with pytest.raises(MCPEndpointError) as exc_info:
            validate_mcp_endpoint("file:///etc/passwd")
        assert "схема" in str(exc_info.value).lower()
        assert "file" in exc_info.value.user_message.lower()

    def test_ftp_scheme_rejected(self) -> None:
        with pytest.raises(MCPEndpointError):
            validate_mcp_endpoint("ftp://example.com/")

    def test_gopher_scheme_rejected(self) -> None:
        # Gopher — классический SSRF vector (можно делать произвольные TCP).
        with pytest.raises(MCPEndpointError):
            validate_mcp_endpoint("gopher://example.com:70/")

    def test_no_scheme_rejected(self) -> None:
        with pytest.raises(MCPEndpointError):
            validate_mcp_endpoint("example.com/mcp")

    def test_dict_scheme_rejected(self) -> None:
        # dict:// — ещё один SSRF vector через memcache/Redis.
        with pytest.raises(MCPEndpointError):
            validate_mcp_endpoint("dict://example.com:11211/")


# ----------------------------------------------------------------------------
# Группа 3: Cloud metadata endpoints (THE главный target SSRF)
# ----------------------------------------------------------------------------


class TestCloudMetadataBlocked:
    """AWS / GCP / Azure metadata endpoints должны быть заблокированы."""

    def test_aws_metadata_direct_ip_rejected(self) -> None:
        # AWS IMDSv1 — самая известная SSRF цель.
        with pytest.raises(MCPEndpointError) as exc_info:
            validate_mcp_endpoint("http://169.254.169.254/latest/meta-data/")
        # Cloud metadata резолвится через DNS на 169.254.169.254 — мы делаем
        # резолв и блокируем как link-local. Тут IP напрямую — попадает в
        # DNS check (getaddrinfo на IP вернёт сам IP).
        assert "link-local" in str(exc_info.value).lower() or "169.254" in str(exc_info.value)

    def test_aws_metadata_ipv6_rejected(self) -> None:
        # IMDSv2 IPv6.
        with pytest.raises(MCPEndpointError):
            validate_mcp_endpoint("http://[fd00:ec2::254]/")

    def test_gcp_metadata_rejected(self) -> None:
        # GCP metadata.google.internal резолвится в 169.254.169.254.
        with patch(
            "app.security.mcp_endpoint_validator._resolve_hostname",
            return_value=("169.254.169.254",),
        ):
            with pytest.raises(MCPEndpointError) as exc_info:
                validate_mcp_endpoint("http://metadata.google.internal/")
            assert "link-local" in str(exc_info.value).lower()


# ----------------------------------------------------------------------------
# Группа 4: Private/intranet IPs (RFC 1918)
# ----------------------------------------------------------------------------


class TestPrivateNetworksBlocked:
    """Приватные RFC 1918 сети должны быть заблокированы."""

    @pytest.mark.parametrize(
        "ip",
        [
            "10.0.0.1",        # RFC 1918 — class A
            "10.255.255.255",  # граница 10/8
            "172.16.0.1",      # RFC 1918 — class B (граница)
            "172.31.255.255",  # граница 172.16/12
            "192.168.0.1",     # RFC 1918 — class C
            "192.168.1.1",     # типичный роутер
        ],
    )
    def test_private_ip_direct_rejected(self, ip: str) -> None:
        # Прямые IP — getaddrinfo вернёт сам IP, _is_blocked_ip забанит.
        with pytest.raises(MCPEndpointError) as exc_info:
            validate_mcp_endpoint(f"http://{ip}/mcp")
        assert "приватн" in str(exc_info.value).lower() or ip in str(exc_info.value)

    def test_ipv6_ula_rejected(self) -> None:
        # IPv6 Unique Local Address (RFC 4193).
        with pytest.raises(MCPEndpointError):
            validate_mcp_endpoint("http://[fc00::1]/mcp")

    def test_private_via_dns_rebinding_rejected(self) -> None:
        """DNS rebinding: домен резолвится в private IP.

        Атакующий регистрирует evil.com → 192.168.1.1. Мы резолвим и блокируем.
        """
        with patch(
            "app.security.mcp_endpoint_validator._resolve_hostname",
            return_value=("192.168.1.1",),
        ):
            with pytest.raises(MCPEndpointError):
                validate_mcp_endpoint("http://evil.com/mcp")

    def test_mixed_resolution_one_bad_ip_rejected(self) -> None:
        """Если хотя бы ОДИН из резолвенных IP в blocked — reject.

        Хост может резолвиться сразу в несколько IP (IPv4 + IPv6, или round-robin).
        Если ОДИН небезопасный — блокируем всё (consistent stance).
        """
        with patch(
            "app.security.mcp_endpoint_validator._resolve_hostname",
            return_value=("1.2.3.4", "192.168.1.1"),  # один публичный, один приватный
        ):
            with pytest.raises(MCPEndpointError):
                validate_mcp_endpoint("http://tricky.example.com/mcp")


# ----------------------------------------------------------------------------
# Группа 5: Loopback атаки (127.x.x.x кроме 127.0.0.1)
# ----------------------------------------------------------------------------


class TestLoopbackEdgeCases:
    """Хитрые loopback адреса — 127.0.0.2 и пр. — НЕ разрешены."""

    @pytest.mark.parametrize(
        "ip",
        [
            "127.0.0.2",   # Linux distro alias
            "127.1.1.1",   # все 127.x.x.x — loopback
            "127.255.255.254",
        ],
    )
    def test_loopback_non_127_0_0_1_rejected(self, ip: str) -> None:
        # 127.0.0.0/8 — весь loopback. Только 127.0.0.1 явно разрешён.
        with pytest.raises(MCPEndpointError) as exc_info:
            validate_mcp_endpoint(f"http://{ip}/mcp")
        assert "loopback" in str(exc_info.value).lower() or ip in str(exc_info.value)

    def test_evil_dns_to_loopback_rejected(self) -> None:
        # evil.com → 127.0.0.5 (например, для эксплуатации локального сервиса).
        with patch(
            "app.security.mcp_endpoint_validator._resolve_hostname",
            return_value=("127.0.0.5",),
        ):
            with pytest.raises(MCPEndpointError):
                validate_mcp_endpoint("http://evil.example.com/mcp")


# ----------------------------------------------------------------------------
# Группа 6: Невалидные входы
# ----------------------------------------------------------------------------


class TestInvalidInput:
    """Empty / None / мусор."""

    def test_empty_string_rejected(self) -> None:
        with pytest.raises(MCPEndpointError):
            validate_mcp_endpoint("")

    def test_no_hostname_rejected(self) -> None:
        # http:// без хоста.
        with pytest.raises(MCPEndpointError):
            validate_mcp_endpoint("http:///mcp")

    def test_dns_failure_allowed_no_target(self) -> None:
        """DNS failure НЕ блокирует endpoint — нет резолвенного IP = нет SSRF target.

        Пользователь legitimately может сохранить endpoint «на потом» (MCP
        сервер ещё не поднят). Проблема покажется при ping → 502.

        Атакующий через неразрешимый hostname ничего не получает —
        backend просто не может пойти никуда.
        """
        # Невалидный домен → DNS gaierror → resolved_ips=()
        result = validate_mcp_endpoint(
            "http://this-domain-definitely-does-not-exist-12345.invalid/mcp"
        )
        assert result.resolved_ips == ()  # DNS не резолвится
        assert result.is_localhost is False
        # Но endpoint в целом валиден — pass.


# ----------------------------------------------------------------------------
# Группа 7: Публичные IP — РАЗРЕШЕНЫ
# ----------------------------------------------------------------------------


class TestPublicAddressesAllowed:
    """Реальные публичные IP/домены должны проходить."""

    def test_public_ip_allowed(self) -> None:
        # 1.1.1.1 — Cloudflare DNS, гарантированно публичный.
        result = validate_mcp_endpoint("http://1.1.1.1/")
        assert result.hostname == "1.1.1.1"
        assert "1.1.1.1" in result.resolved_ips
        assert result.is_localhost is False

    def test_public_domain_via_mock(self) -> None:
        # Не делаем реальный DNS lookup в unit-тесте — мокаем.
        with patch(
            "app.security.mcp_endpoint_validator._resolve_hostname",
            return_value=("93.184.216.34",),  # example.com IP
        ):
            result = validate_mcp_endpoint("https://example.com/mcp")
            assert result.hostname == "example.com"
            assert result.scheme == "https"
            assert "93.184.216.34" in result.resolved_ips
            assert result.is_localhost is False
