"""Tests for skill bundles + preprocessing (Sprint 5 A10/A11)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.skills.bundles import (
    Bundle,
    BundleRegistry,
    load_bundles_from_dir,
    parse_bundle_yaml,
)
from app.skills.preprocessor import (
    MAX_OUTPUT_BYTES,
    build_default_context,
    preprocess_skill_body,
)


# ── Bundle parser ──


def test_parse_basic_yaml() -> None:
    text = """
name: closing-month
title: Закрытие месяца
description: Подсказки по закрытию периода
skills:
  - check-postings
  - reconcile-acts
  - balance-check
"""
    bundle = parse_bundle_yaml(text)
    assert bundle.name == "closing-month"
    assert bundle.title == "Закрытие месяца"
    assert len(bundle.skills) == 3
    assert "check-postings" in bundle.skills


def test_parse_inline_list() -> None:
    text = """
name: quick
title: Quick
skills: [a, b, c]
"""
    bundle = parse_bundle_yaml(text)
    assert bundle.skills == ["a", "b", "c"]


def test_parse_missing_name_raises() -> None:
    with pytest.raises(ValueError, match="missing 'name'"):
        parse_bundle_yaml("title: hello")


def test_bundle_invalid_name() -> None:
    with pytest.raises(ValueError):
        Bundle(name="contains spaces", title="x")


def test_bundle_too_many_skills() -> None:
    with pytest.raises(ValueError, match=">"):
        Bundle(name="big", title="x", skills=[f"s{i}" for i in range(30)])


def test_registry_add_get() -> None:
    reg = BundleRegistry()
    reg.add(Bundle(name="a", title="A"))
    reg.add(Bundle(name="b", title="B"))
    assert reg.get("a") is not None
    assert reg.get("c") is None
    assert len(reg.list_all()) == 2


def test_registry_remove() -> None:
    reg = BundleRegistry()
    reg.add(Bundle(name="x", title="X"))
    assert reg.remove("x") is True
    assert reg.remove("x") is False


def test_load_bundles_from_dir(tmp_path: Path) -> None:
    (tmp_path / "b1.yaml").write_text(
        "name: bundle-one\ntitle: First\nskills:\n  - a\n", encoding="utf-8"
    )
    (tmp_path / "b2.yml").write_text(
        "name: bundle-two\ntitle: Second\nskills: [x]\n", encoding="utf-8"
    )
    (tmp_path / "ignored.txt").write_text("ignored")
    reg = load_bundles_from_dir(tmp_path)
    names = {b.name for b in reg.list_all()}
    assert names == {"bundle-one", "bundle-two"}


def test_load_bundles_nonexistent_dir(tmp_path: Path) -> None:
    reg = load_bundles_from_dir(tmp_path / "missing")
    assert reg.list_all() == []


# ── Preprocessor ──


def test_substitute_var() -> None:
    body = "Session: ${ANALYST_SESSION_ID}, channel: ${ANALYST_CHANNEL_ID}"
    out = preprocess_skill_body(
        body,
        context={"ANALYST_SESSION_ID": "s1", "ANALYST_CHANNEL_ID": "ch-a"},
    )
    assert "s1" in out
    assert "ch-a" in out
    assert "${" not in out


def test_missing_var_left_intact() -> None:
    body = "Hello ${MISSING}"
    out = preprocess_skill_body(body, context={})
    assert "${MISSING}" in out


def test_shell_disabled_by_default() -> None:
    body = "Today: !`echo hi`!"
    out = preprocess_skill_body(body)
    # Команда НЕ выполнена — текст остаётся
    assert "!`echo hi`!" in out


def test_default_context_has_today() -> None:
    ctx = build_default_context(session_id="s1", channel_id="ch")
    assert ctx["ANALYST_SESSION_ID"] == "s1"
    assert ctx["ANALYST_CHANNEL_ID"] == "ch"
    assert "ANALYST_TODAY" in ctx
    # date формат YYYY-MM-DD
    assert len(ctx["ANALYST_TODAY"]) == 10


def test_cap_max_output() -> None:
    body = "x" * (MAX_OUTPUT_BYTES + 1000)
    out = preprocess_skill_body(body)
    assert len(out) <= MAX_OUTPUT_BYTES + 50  # + truncation marker
    assert "truncated" in out


def test_empty_body() -> None:
    assert preprocess_skill_body("") == ""
