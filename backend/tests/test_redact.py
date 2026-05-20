"""Tests for redact (Sprint 4 — Hermes E8)."""

from __future__ import annotations

from app.orchestrator.redact import redact, redact_dict


def test_openai_key_masked() -> None:
    text = "ключ sk-proj-AbCdEfGhIjKlMnOpQrStUvWx_1234"
    out = redact(text)
    assert "sk-proj-AbCdEf" not in out  # длинный — head preserved, хвост скрыт
    # Должно содержать head/tail сегменты согласно formatter
    assert "…" in out


def test_anthropic_key_masked() -> None:
    text = "Authorization: sk-ant-api03-AbcDefGhIjKlMnOpQrStUvWxYzAbCdEfGh"
    out = redact(text)
    assert "sk-ant-api03-AbcDefGhIjKlMnOpQrStUvWxYzAbCdEfGh" not in out
    assert "…" in out


def test_github_token_masked() -> None:
    text = "token ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ012345"
    out = redact(text)
    assert "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ012345" not in out


def test_aws_key_masked() -> None:
    text = "AKIAIOSFODNN7EXAMPLE"
    assert redact(text) == "***" or "AKIAIOSFOD" not in redact(text)


def test_bearer_keeps_prefix() -> None:
    text = "Bearer abc1234567890XYZ_long_token_value_xx"
    out = redact(text)
    assert out.startswith("Bearer ")
    assert "abc1234567890XYZ_long_token_value_xx" not in out


def test_api_key_pair_keeps_label() -> None:
    text = 'api_key = "AbCdEfGhIjKlMnOpQrStUv12345"'
    out = redact(text)
    # Префикс "api_key = \"" сохранён.
    assert "api_key" in out.lower()
    assert "AbCdEfGhIjKlMnOpQrStUv12345" not in out


def test_short_secret_fully_masked() -> None:
    # 16-символьный AWS access key — полностью маскируется ("AKIA" + 16 хвост, итого 20)
    # → длинный preserve. Берём через redact_dict вместо regex — там короткие маскируются.
    data = {"password": "shortpass"}
    out = redact_dict(data)
    assert out["password"] == "***"


def test_empty_input_returned_as_is() -> None:
    assert redact("") == ""
    assert redact(None) is None  # type: ignore[arg-type]


def test_no_secret_text_unchanged() -> None:
    text = "Обычный текст без секретов на русском."
    assert redact(text) == text


def test_redact_dict_password_key() -> None:
    data = {"username": "admin", "password": "longsupersecretpassword"}
    out = redact_dict(data)
    assert out["username"] == "admin"
    assert out["password"] != "longsupersecretpassword"


def test_redact_dict_nested() -> None:
    data = {
        "config": {
            "api_key": "sk-test123456789012345",
            "url": "https://example.com",
        },
        "items": ["text", {"token": "abc1234567890_long_value"}],
    }
    out = redact_dict(data)
    assert out["config"]["api_key"] != "sk-test123456789012345"
    assert out["config"]["url"] == "https://example.com"
    assert out["items"][1]["token"] != "abc1234567890_long_value"


def test_redact_dict_immutable() -> None:
    data = {"password": "supersecretvalueforpassword"}
    redact_dict(data)
    # Original не изменён
    assert data["password"] == "supersecretvalueforpassword"
