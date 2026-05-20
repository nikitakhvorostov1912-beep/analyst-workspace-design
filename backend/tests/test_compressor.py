"""Tests for ContextCompressor (Sprint 2 — Hermes B1+B2+B4+B5)."""

from __future__ import annotations

import pytest

from app.orchestrator.compressor import (
    DEFAULT_HEAD_PROTECT,
    DEFAULT_TAIL_PROTECT,
    SUMMARY_PREAMBLE,
    TOOL_PRUNE_BYTES,
    compress,
    estimate_tokens,
    format_messages_for_summary,
    make_summary_message,
    needs_compression,
    prune_tool_outputs,
    split_protected,
)


# ── estimate_tokens ──


def test_estimate_tokens_text() -> None:
    """Текст 35 символов → ~10 токенов."""
    msgs = [{"role": "user", "content": "x" * 35}]
    assert 9 <= estimate_tokens(msgs) <= 11


def test_estimate_tokens_image_part() -> None:
    msgs = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "x" * 35},
                {"type": "image_url", "image_url": {"url": "data:..."}},
            ],
        }
    ]
    tokens = estimate_tokens(msgs)
    # 10 (text) + 1024 (image)
    assert tokens >= 1024


def test_estimate_tokens_tool_calls() -> None:
    """tool_calls.arguments тоже считаются."""
    msgs = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "1",
                    "type": "function",
                    "function": {"name": "x", "arguments": '{"q": "' + "y" * 30 + '"}'},
                }
            ],
        }
    ]
    assert estimate_tokens(msgs) > 0


def test_estimate_tokens_empty() -> None:
    assert estimate_tokens([]) == 0


# ── needs_compression ──


def test_needs_compression_below_threshold() -> None:
    msgs = [{"role": "user", "content": "short"}]
    assert needs_compression(msgs, max_context_tokens=128_000) is False


def test_needs_compression_above_threshold() -> None:
    # Большой текст
    huge_text = "x" * (128_000 * 3 * 4)  # >>75% от 128k
    msgs = [{"role": "user", "content": huge_text}]
    assert needs_compression(msgs, max_context_tokens=128_000) is True


def test_needs_compression_zero_max() -> None:
    msgs = [{"role": "user", "content": "x"}]
    assert needs_compression(msgs, max_context_tokens=0) is False


# ── prune_tool_outputs ──


def test_prune_tool_outputs_no_change_few_tools() -> None:
    """≤ 2 tool messages — pruning не запускается (нечего защищать)."""
    msgs = [
        {"role": "user", "content": "hi"},
        {"role": "tool", "tool_call_id": "t1", "content": "x" * 10_000},
    ]
    new_msgs, count = prune_tool_outputs(msgs, max_bytes=100)
    assert new_msgs == msgs
    assert count == 0


def test_prune_tool_outputs_protects_first_and_last() -> None:
    msgs = [
        {"role": "user", "content": "hi"},
        {"role": "tool", "tool_call_id": "t1", "content": "first" + "x" * 10_000},
        {"role": "tool", "tool_call_id": "t2", "content": "middle" + "x" * 10_000},
        {"role": "tool", "tool_call_id": "t3", "content": "last" + "x" * 10_000},
    ]
    new_msgs, count = prune_tool_outputs(msgs, max_bytes=100)
    # Middle pruned
    assert count == 1
    assert "pruned" in new_msgs[2]["content"]
    # First & last unchanged
    assert new_msgs[1]["content"].startswith("first")
    assert "pruned" not in new_msgs[1]["content"]
    assert new_msgs[3]["content"].startswith("last")
    assert "pruned" not in new_msgs[3]["content"]


def test_prune_tool_outputs_preserves_small() -> None:
    msgs = [
        {"role": "user", "content": "hi"},
        {"role": "tool", "tool_call_id": "t1", "content": "small1"},
        {"role": "tool", "tool_call_id": "t2", "content": "small2"},
        {"role": "tool", "tool_call_id": "t3", "content": "small3"},
    ]
    new_msgs, count = prune_tool_outputs(msgs, max_bytes=1000)
    assert count == 0  # все маленькие
    assert new_msgs == msgs


# ── split_protected ──


def test_split_protected_basic() -> None:
    msgs = [
        {"role": "system", "content": "sys"},
        *[{"role": "user", "content": f"m{i}"} for i in range(20)],
    ]
    head, middle, tail = split_protected(
        msgs, head_protect=DEFAULT_HEAD_PROTECT, tail_protect=DEFAULT_TAIL_PROTECT
    )
    # head = system + первые 3
    assert len(head) == 1 + DEFAULT_HEAD_PROTECT
    assert head[0]["role"] == "system"
    # tail = последние 4
    assert len(tail) == DEFAULT_TAIL_PROTECT
    # middle — то что между
    assert len(middle) == 20 - DEFAULT_HEAD_PROTECT - DEFAULT_TAIL_PROTECT


def test_split_protected_short_history() -> None:
    """Если сообщений мало — middle пустой."""
    msgs = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "1"},
        {"role": "assistant", "content": "2"},
    ]
    head, middle, tail = split_protected(msgs)
    assert middle == []


def test_split_protected_empty() -> None:
    head, middle, tail = split_protected([])
    assert head == middle == tail == []


# ── format_messages_for_summary ──


def test_format_for_summary_includes_roles() -> None:
    msgs = [
        {"role": "user", "content": "вопрос"},
        {"role": "assistant", "content": "ответ"},
        {"role": "tool", "tool_call_id": "abc12345", "content": "data"},
    ]
    formatted = format_messages_for_summary(msgs)
    assert "USER" in formatted
    assert "ASSISTANT" in formatted
    assert "TOOL" in formatted
    assert "вопрос" in formatted


def test_format_for_summary_image_placeholder() -> None:
    msgs = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "вот"},
                {"type": "image_url", "image_url": {"url": "..."}},
            ],
        }
    ]
    formatted = format_messages_for_summary(msgs)
    assert "[image]" in formatted
    assert "вот" in formatted


# ── make_summary_message ──


def test_summary_message_has_filter_safe_preamble() -> None:
    msg = make_summary_message("Summary text here")
    assert msg["role"] == "system"
    assert SUMMARY_PREAMBLE in msg["content"]
    assert "Summary text here" in msg["content"]


# ── compress ──


@pytest.mark.asyncio
async def test_compress_without_aux_uses_placeholder() -> None:
    """Без aux_client middle выкидывается с placeholder."""
    msgs = [
        {"role": "system", "content": "sys"},
        *[{"role": "user", "content": f"msg {i}"} for i in range(20)],
    ]
    result = await compress(msgs, aux_client=None)
    assert result.stats.summarized is True
    # head + summary + tail
    expected_count = 1 + DEFAULT_HEAD_PROTECT + 1 + DEFAULT_TAIL_PROTECT
    assert len(result.new_messages) == expected_count
    # Summary placeholder содержит "Пропущено"
    summary_msg = result.new_messages[1 + DEFAULT_HEAD_PROTECT]
    assert "Пропущено" in summary_msg["content"]


@pytest.mark.asyncio
async def test_compress_with_aux_client_uses_summary() -> None:
    """Aux client возвращает summary, мы его используем."""

    class FakeAux:
        async def complete_with_fallback(self, _messages, **_kwargs):
            return "## Активная задача\nВопрос про ОПП.\n\n## Решено\n- найдено 32 документа"

    msgs = [
        {"role": "system", "content": "sys"},
        *[{"role": "user", "content": f"msg {i}"} for i in range(20)],
    ]
    result = await compress(msgs, aux_client=FakeAux())
    assert result.stats.summarized is True
    summary_msg = result.new_messages[1 + DEFAULT_HEAD_PROTECT]
    assert "Активная задача" in summary_msg["content"]
    assert SUMMARY_PREAMBLE in summary_msg["content"]


@pytest.mark.asyncio
async def test_compress_aux_returns_none_uses_placeholder() -> None:
    """Если aux вернул None (упал) → placeholder."""

    class BrokenAux:
        async def complete_with_fallback(self, _messages, **_kwargs):
            return None

    msgs = [
        {"role": "system", "content": "sys"},
        *[{"role": "user", "content": f"msg {i}"} for i in range(15)],
    ]
    result = await compress(msgs, aux_client=BrokenAux())
    assert result.stats.summarized is True
    summary_msg = result.new_messages[1 + DEFAULT_HEAD_PROTECT]
    assert "Пропущено" in summary_msg["content"]


@pytest.mark.asyncio
async def test_compress_short_history_noop() -> None:
    """Короткая история — middle пустой → compress(noop)."""
    msgs = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "ok"},
    ]
    result = await compress(msgs)
    # summarized=False — компрессия не запустилась
    assert result.stats.summarized is False
    assert len(result.new_messages) == 3


@pytest.mark.asyncio
async def test_compress_prunes_tool_outputs() -> None:
    """Большие tool outputs в middle prune-нутся."""
    msgs = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "1"},
        {"role": "assistant", "content": None, "tool_calls": [
            {"id": "t1", "type": "function", "function": {"name": "x", "arguments": "{}"}}
        ]},
        # Первый и последний tool — защищены
        {"role": "tool", "tool_call_id": "t1", "content": "small first"},
        *[
            {"role": "user", "content": f"m{i}"} for i in range(5)
        ],
        # Огромный tool в middle
        {"role": "tool", "tool_call_id": "t2", "content": "x" * 10_000},
        *[
            {"role": "user", "content": f"n{i}"} for i in range(5)
        ],
        {"role": "tool", "tool_call_id": "t3", "content": "small last"},
        {"role": "user", "content": "q"},
        {"role": "assistant", "content": "a"},
    ]
    result = await compress(msgs, aux_client=None)
    assert result.stats.pruned_tool_calls >= 1


def test_estimate_tokens_immutability() -> None:
    """estimate_tokens не мутирует вход."""
    msgs = [{"role": "user", "content": "test"}]
    snapshot = list(msgs[0].items())
    estimate_tokens(msgs)
    assert list(msgs[0].items()) == snapshot


@pytest.mark.asyncio
async def test_compress_immutability() -> None:
    """compress() не мутирует вход."""
    msgs = [
        {"role": "system", "content": "sys"},
        *[{"role": "user", "content": f"m{i}"} for i in range(15)],
    ]
    msgs_copy = [dict(m) for m in msgs]
    await compress(msgs, aux_client=None)
    # Исходный список не изменился по содержимому
    assert all(
        msgs[i].get("content") == msgs_copy[i].get("content")
        for i in range(len(msgs))
    )
