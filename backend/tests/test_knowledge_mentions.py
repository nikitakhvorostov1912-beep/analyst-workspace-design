"""Тесты для backend/app/knowledge/mentions.py (M-K1.14).

Покрытие:
- parse_object_mentions: грамматика, дедупликация, ложные срабатывания
- dossier_to_object_card: маппинг полей, fallback на name при пустой presentation
- render_mentions_context_block: found / not_found / mixed / пустой
"""

from __future__ import annotations

from datetime import datetime

from app.knowledge.dossier import ObjectDossier
from app.knowledge.mentions import (
    ObjectMention,
    dossier_to_object_card,
    parse_object_mentions,
    render_mentions_context_block,
)
from app.knowledge.types import ObjectPath


def _make_dossier(
    full: str,
    presentation: str | None = None,
    kind: str | None = None,
    attributes: list[dict] | None = None,
) -> ObjectDossier:
    path = ObjectPath.parse(full)
    return ObjectDossier(
        object_path=path,
        presentation=presentation,
        kind=kind or path.kind,
        channel_id="ch-1",
        fetched_at=datetime(2026, 5, 25, 22, 0),
        source="cache",
        attributes=attributes or [],
    )


# ---------- parse_object_mentions ----------


def test_parse_single_mention():
    mentions = parse_object_mentions("расскажи про @Документ.ОПП")
    assert len(mentions) == 1
    assert mentions[0] == ObjectMention(
        full="Документ.ОПП", kind="Документ", name="ОПП", raw="@Документ.ОПП"
    )


def test_parse_multiple_mentions_preserves_order():
    mentions = parse_object_mentions(
        "сравни @Документ.ОПП и @Справочник.Контрагенты"
    )
    assert [m.full for m in mentions] == ["Документ.ОПП", "Справочник.Контрагенты"]


def test_parse_deduplicates_repeated_mentions():
    mentions = parse_object_mentions(
        "@Документ.ОПП а потом ещё раз @Документ.ОПП"
    )
    assert len(mentions) == 1
    assert mentions[0].full == "Документ.ОПП"


def test_parse_supports_latin_names():
    mentions = parse_object_mentions("проверь @Catalog.Counterparties")
    assert len(mentions) == 1
    assert mentions[0].kind == "Catalog"
    assert mentions[0].name == "Counterparties"


def test_parse_supports_underscore_and_digits_in_name():
    mentions = parse_object_mentions("@РегистрСведений.КурсыВалют_2026")
    assert len(mentions) == 1
    assert mentions[0].name == "КурсыВалют_2026"


def test_parse_ignores_email_addresses():
    """Email — `name@host.tld` — НЕ должен схватиться как mention."""
    mentions = parse_object_mentions("пиши на user@example.com")
    assert mentions == []


def test_parse_ignores_mention_without_dot():
    mentions = parse_object_mentions("плохая ссылка @Документ")
    assert mentions == []


def test_parse_ignores_lone_at_sign():
    assert parse_object_mentions("просто @ символ") == []
    assert parse_object_mentions("@") == []


def test_parse_at_start_of_string():
    mentions = parse_object_mentions("@Документ.ОПП — что это")
    assert len(mentions) == 1
    assert mentions[0].full == "Документ.ОПП"


def test_parse_after_punctuation():
    """После запятой / скобки / кавычки mention должен распознаваться."""
    mentions = parse_object_mentions("объекты (@Документ.ОПП) и «@Справочник.К»")
    fulls = [m.full for m in mentions]
    assert "Документ.ОПП" in fulls
    assert "Справочник.К" in fulls


def test_parse_empty_text_returns_empty_list():
    assert parse_object_mentions("") == []
    assert parse_object_mentions("   ") == []


def test_parse_double_at_is_not_mention():
    """`@@something.X` — НЕ должно матчиться (граница перед @ запрещает @)."""
    mentions = parse_object_mentions("@@Документ.ОПП")
    assert mentions == []


# ---------- dossier_to_object_card ----------


def test_dossier_to_card_basic():
    dossier = _make_dossier(
        "Документ.ОПП", presentation="Отгрузка под перевозку"
    )
    card = dossier_to_object_card(dossier)
    assert card["type"] == "object"
    payload = card["payload"]
    assert payload["header"] == {
        "name": "Отгрузка под перевозку",
        "type": "Документ",
        "path": "Документ.ОПП",
    }
    assert payload["attributes"] == []
    assert payload["tabular_sections"] == []
    assert payload["forms"] == []
    assert payload["templates"] == []
    assert payload["card_id"] is None


def test_dossier_to_card_fallback_name_when_no_presentation():
    """Если presentation отсутствует — в name идёт ObjectPath.name."""
    dossier = _make_dossier("Справочник.Контрагенты", presentation=None)
    card = dossier_to_object_card(dossier)
    assert card["payload"]["header"]["name"] == "Контрагенты"


def test_dossier_to_card_preserves_attributes():
    attrs = [{"name": "Номер", "type": "Строка", "value": "ОПП-0001"}]
    dossier = _make_dossier(
        "Документ.ОПП", presentation="ОПП", attributes=attrs
    )
    card = dossier_to_object_card(dossier)
    assert card["payload"]["attributes"] == attrs


def test_dossier_to_card_payload_validates_against_pydantic_model():
    """payload должен проходить app.orchestrator.cards.ObjectCardPayload."""
    from app.orchestrator.cards import ObjectCardPayload

    dossier = _make_dossier("Документ.ОПП", presentation="ОПП")
    card = dossier_to_object_card(dossier)
    # Не должно бросить ValidationError
    ObjectCardPayload.model_validate(card["payload"])


# ---------- render_mentions_context_block ----------


def test_render_block_with_found_dossiers():
    mentions = [
        ObjectMention(full="Документ.ОПП", kind="Документ", name="ОПП", raw="@Документ.ОПП"),
        ObjectMention(
            full="Справочник.Контрагенты",
            kind="Справочник",
            name="Контрагенты",
            raw="@Справочник.Контрагенты",
        ),
    ]
    dossiers = {
        "Документ.ОПП": _make_dossier("Документ.ОПП", presentation="ОПП"),
        "Справочник.Контрагенты": _make_dossier(
            "Справочник.Контрагенты", presentation="Контрагенты"
        ),
    }
    block = render_mentions_context_block(mentions, dossiers)
    assert block is not None
    assert "Документ.ОПП" in block
    assert "Справочник.Контрагенты" in block
    assert "паспорта переданы" in block


def test_render_block_with_only_not_found_mentions():
    mentions = [
        ObjectMention(full="Документ.X", kind="Документ", name="X", raw="@Документ.X"),
    ]
    block = render_mentions_context_block(mentions, dossiers={})
    assert block is not None
    assert "Документ.X" in block
    assert "metadata_cache" in block
    assert "паспорта" not in block  # found_lines пустой


def test_render_block_with_mixed_found_and_not_found():
    mentions = [
        ObjectMention(full="Документ.ОПП", kind="Документ", name="ОПП", raw="@Документ.ОПП"),
        ObjectMention(
            full="Документ.Missing", kind="Документ", name="Missing", raw="@Документ.Missing"
        ),
    ]
    dossiers = {
        "Документ.ОПП": _make_dossier("Документ.ОПП", presentation="ОПП"),
    }
    block = render_mentions_context_block(mentions, dossiers)
    assert block is not None
    assert "Документ.ОПП" in block
    assert "Документ.Missing" in block
    assert "паспорта переданы" in block
    assert "metadata_cache" in block


def test_render_block_returns_none_for_empty_mentions():
    assert render_mentions_context_block([], {}) is None
