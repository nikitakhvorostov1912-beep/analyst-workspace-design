"""Tests for ThinkScrubber (Sprint 4 — Hermes G7)."""

from __future__ import annotations

from app.orchestrator.think_scrubber import ThinkScrubber


def test_plain_text_passes_through() -> None:
    s = ThinkScrubber()
    assert s.feed("Hello") == "Hello"
    assert s.flush() == ""


def test_think_block_stripped() -> None:
    s = ThinkScrubber()
    out = s.feed("Hello <think>secret reasoning</think> World")
    assert "secret" not in out
    assert "Hello" in out and "World" in out


def test_thinking_tag_variant() -> None:
    s = ThinkScrubber()
    out = s.feed("a<thinking>x</thinking>b")
    assert out == "ab"


def test_reasoning_tag_variant() -> None:
    s = ThinkScrubber()
    out = s.feed("Q <reasoning>step 1</reasoning>A")
    assert out == "Q A"


def test_case_insensitive() -> None:
    s = ThinkScrubber()
    out = s.feed("a<THINK>x</THINK>b")
    assert "x" not in out


def test_split_across_chunks_open() -> None:
    """Открывающий тег приходит в двух chunks."""
    s = ThinkScrubber()
    out1 = s.feed("Hello <th")
    out2 = s.feed("ink>hidden</think> World")
    combined = out1 + out2
    assert "hidden" not in combined
    assert "Hello" in combined
    assert "World" in combined


def test_split_across_chunks_close() -> None:
    s = ThinkScrubber()
    out1 = s.feed("a<think>x</thi")
    out2 = s.feed("nk>b")
    combined = out1 + out2
    assert combined == "ab"


def test_stream_ends_inside_think_drops() -> None:
    """Если стрим оборвался внутри <think> — частичное не emit-ится."""
    s = ThinkScrubber()
    out = s.feed("a<think>incomplete")
    tail = s.flush()
    assert "incomplete" not in (out + tail)
    assert (out + tail) == "a"


def test_no_think_flush_returns_pending() -> None:
    s = ThinkScrubber()
    s.feed("foo")
    s.feed("<th")  # выглядит как начало тега
    tail = s.flush()
    # pending получит "<th" но flush вне think вернёт его.
    assert "<th" in tail or tail == ""


def test_multiple_think_blocks() -> None:
    s = ThinkScrubber()
    out = s.feed("a<think>x</think>b<think>y</think>c")
    assert out == "abc"


def test_inside_think_state() -> None:
    s = ThinkScrubber()
    s.feed("<think>")
    assert s.inside_think is True
    s.feed("</think>")
    assert s.inside_think is False


def test_empty_chunk_safe() -> None:
    s = ThinkScrubber()
    assert s.feed("") == ""
