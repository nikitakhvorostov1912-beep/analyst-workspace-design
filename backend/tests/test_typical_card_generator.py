"""Тесты для card_generator (M-K2.5.5)."""

from __future__ import annotations

import json

import pytest

from app.knowledge.typical.card_context import (
    CardContext,
    CardContextAttribute,
    CardContextMethod,
)
from app.knowledge.typical.card_generator import (
    CardGenerationError,
    LLMResponse,
    MockLLMCaller,
    PROMPT_VERSION,
    _extract_context_json,
    _parse_llm_response,
    _payload_to_card,
    build_messages,
    generate_card,
    generate_card_for_channel,
    load_prompt_template,
)
from app.knowledge.typical.card_models import TypicalObjectCard


def _ctx(name: str = "Заказ", kind: str = "Document") -> CardContext:
    return CardContext(
        object_qualified_name=f"{kind}.{name}",
        object_kind=kind,
        object_name=name,
        object_uuid=None,
        object_comment="Тестовый объект",
        object_source_path=None,
    )


# ─── Prompt template ─────────────────────────────────────────────────


def test_load_prompt_template_returns_markdown():
    text = load_prompt_template()
    assert "## System" in text
    assert "## User" in text
    assert "{context_json}" in text


def test_prompt_version_constant():
    assert PROMPT_VERSION == "v1"


def test_build_messages_has_system_and_user():
    ctx = _ctx()
    msgs = build_messages(ctx)
    assert len(msgs) == 2
    assert msgs[0]["role"] == "system"
    assert msgs[1]["role"] == "user"
    assert "Контекст объекта:" in msgs[1]["content"]
    # context_json подставлен
    assert "Document.Заказ" in msgs[1]["content"]


def test_build_messages_no_placeholder_in_output():
    ctx = _ctx()
    msgs = build_messages(ctx)
    # Placeholder заменён
    assert "{context_json}" not in msgs[1]["content"]


# ─── _parse_llm_response ─────────────────────────────────────────────


def test_parse_plain_json():
    payload = _parse_llm_response('{"summary": "Тест"}')
    assert payload["summary"] == "Тест"


def test_parse_fenced_json():
    text = "```json\n{\"summary\": \"Т\"}\n```"
    payload = _parse_llm_response(text)
    assert payload["summary"] == "Т"


def test_parse_unfenced_json_with_whitespace():
    payload = _parse_llm_response('  \n{"summary": "X"}\n  ')
    assert payload["summary"] == "X"


def test_parse_invalid_json_raises():
    with pytest.raises(CardGenerationError):
        _parse_llm_response("Not JSON at all")


def test_parse_non_object_raises():
    with pytest.raises(CardGenerationError):
        _parse_llm_response("[1, 2, 3]")


# ─── _payload_to_card ────────────────────────────────────────────────


def test_payload_to_card_minimal():
    ctx = _ctx()
    payload = {"summary": "S", "purpose": "P"}
    card = _payload_to_card(context=ctx, payload=payload)
    assert card.summary == "S"
    assert card.purpose == "P"
    assert card.object_qualified_name == ctx.object_qualified_name


def test_payload_to_card_with_attributes():
    ctx = _ctx()
    payload = {
        "summary": "S",
        "key_attributes": [
            {"name": "Контрагент", "role": "получатель"},
            {"name": "Сумма", "role": ""},
        ],
    }
    card = _payload_to_card(context=ctx, payload=payload)
    assert len(card.key_attributes) == 2
    assert card.key_attributes[0].name == "Контрагент"
    assert card.key_attributes[0].role == "получатель"


def test_payload_to_card_skips_attributes_without_name():
    ctx = _ctx()
    payload = {
        "key_attributes": [
            {"name": "Х"},
            {"role": "noname"},
            "not a dict",
        ],
    }
    card = _payload_to_card(context=ctx, payload=payload)
    assert len(card.key_attributes) == 1
    assert card.key_attributes[0].name == "Х"


def test_payload_to_card_movements():
    ctx = _ctx()
    payload = {
        "movements": [
            {"register": "AccumulationRegister.X", "direction": "расход", "condition": ""},
        ],
    }
    card = _payload_to_card(context=ctx, payload=payload)
    assert len(card.movements) == 1
    assert card.movements[0].direction == "расход"


def test_payload_to_card_handles_none_lists():
    ctx = _ctx()
    payload = {
        "posting_flow": None,
        "related_objects": None,
    }
    card = _payload_to_card(context=ctx, payload=payload)
    assert card.posting_flow == ()
    assert card.related_objects == ()


def test_payload_to_card_str_tuple_skips_empty():
    ctx = _ctx()
    payload = {"posting_flow": ["шаг1", "", "  ", "шаг2"]}
    card = _payload_to_card(context=ctx, payload=payload)
    assert card.posting_flow == ("шаг1", "шаг2")


# ─── _extract_context_json helper ────────────────────────────────────


def test_extract_context_json_basic():
    user_content = 'Контекст объекта:\n{"foo": 1}'
    extracted = _extract_context_json(user_content)
    assert json.loads(extracted) == {"foo": 1}


def test_extract_context_json_returns_empty_on_no_marker():
    extracted = _extract_context_json("nothing here")
    assert extracted == "{}"


# ─── MockLLMCaller ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_mock_llm_returns_valid_json():
    mock = MockLLMCaller()
    ctx = _ctx()
    msgs = build_messages(ctx)
    response = await mock.complete(msgs)
    assert response.content
    # Парсится в dict
    payload = json.loads(response.content)
    assert "summary" in payload
    assert "purpose" in payload


@pytest.mark.asyncio
async def test_mock_llm_includes_object_kind_label():
    mock = MockLLMCaller()
    ctx = _ctx(name="Заказ", kind="Document")
    msgs = build_messages(ctx)
    response = await mock.complete(msgs)
    payload = json.loads(response.content)
    assert "Документ" in payload["summary"]


@pytest.mark.asyncio
async def test_mock_llm_includes_writes_to():
    mock = MockLLMCaller()
    ctx = CardContext(
        object_qualified_name="Document.X",
        object_kind="Document",
        object_name="X",
        object_uuid=None,
        object_comment="",
        object_source_path=None,
        writes_to=("AccumulationRegister.ТоварыНаСкладах",),
    )
    msgs = build_messages(ctx)
    response = await mock.complete(msgs)
    payload = json.loads(response.content)
    assert len(payload["movements"]) == 1
    assert payload["movements"][0]["register"] == "AccumulationRegister.ТоварыНаСкладах"


@pytest.mark.asyncio
async def test_mock_llm_handlers_become_posting_flow():
    mock = MockLLMCaller()
    ctx = CardContext(
        object_qualified_name="Document.X",
        object_kind="Document",
        object_name="X",
        object_uuid=None,
        object_comment="",
        object_source_path=None,
        methods=(
            CardContextMethod(name="ОбработкаПроведения", module_kind="ObjectModule", is_exported=False, is_handler=True),
            CardContextMethod(name="ПередЗаписью", module_kind="ObjectModule", is_exported=False, is_handler=True),
        ),
    )
    msgs = build_messages(ctx)
    response = await mock.complete(msgs)
    payload = json.loads(response.content)
    assert len(payload["posting_flow"]) == 2


# ─── generate_card end-to-end ────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_card_with_mock_returns_typical_card():
    ctx = _ctx()
    mock = MockLLMCaller()
    result = await generate_card(context=ctx, llm=mock)
    assert isinstance(result.card, TypicalObjectCard)
    assert result.card.object_qualified_name == ctx.object_qualified_name
    assert result.card.summary  # mock всегда заполняет summary
    assert result.tokens_in is not None
    assert result.tokens_out is not None
    assert result.model == "mock-generator-v1"


@pytest.mark.asyncio
async def test_generate_card_for_channel_sets_channel_id():
    ctx = _ctx()
    mock = MockLLMCaller()
    result = await generate_card_for_channel(
        context=ctx, channel_id="_bp30_138_24", llm=mock,
    )
    assert result.card.channel_id == "_bp30_138_24"


@pytest.mark.asyncio
async def test_generate_card_propagates_bad_llm_response():
    class BadLLM:
        async def complete(self, messages):
            return LLMResponse(content="not json")

    ctx = _ctx()
    with pytest.raises(CardGenerationError):
        await generate_card(context=ctx, llm=BadLLM())


# ─── PROMPT_VERSION ──────────────────────────────────────────────────


def test_prompt_template_user_section_contains_placeholder():
    text = load_prompt_template()
    assert text.count("{context_json}") == 1
