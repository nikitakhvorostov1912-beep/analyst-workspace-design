"""Карточка «Источники ИТС» из результата buddy.search_its (markdown с ссылками)."""
from __future__ import annotations

from app.orchestrator.cards import (
    _its_doc_id_from_url,
    build_card_from_tool_result,
)

# Усечённый, но реальный по форме результат buddy.search_its (см. probe).
_SEARCH_ITS_TEXT = (
    "По запросу '*RLS*' в **Базе знаний ИТС** найдено **3** документов.\n"
    "[Молокозавод > Глава 2. ПРАВА ДОСТУПА]"
    "(https://its.1c.ru/db/molmoderpka25#content:711:hdoc)\n"
    "[Практическое пособие разработчика > Ограничение доступа]"
    "(https://its.1c.ru/db/pubdevguide83#content:461:hdoc)\n"
    "[Каталог без якоря](https://its.1c.ru/db/bsp321doc)\n"
    "# Ограничение доступа на уровне записей (RLS)\n\nТекст синтез-ответа...\n"
)


def _mcp_result(text: str) -> dict:
    return {"content": [{"type": "text", "text": text}]}


def test_doc_id_from_url_with_anchor():
    assert (
        _its_doc_id_from_url("https://its.1c.ru/db/pubdevguide83#content:461:hdoc")
        == "its-pubdevguide83-461-hdoc"
    )


def test_doc_id_from_url_without_anchor_is_none():
    assert _its_doc_id_from_url("https://its.1c.ru/db/bsp321doc") is None


def test_card_built_from_search_its():
    card = build_card_from_tool_result(
        "buddy.search_its", {"query": "RLS"}, _mcp_result(_SEARCH_ITS_TEXT)
    )
    assert card is not None
    assert card["type"] == "its_sources"
    sources = card["payload"]["sources"]
    assert len(sources) == 3
    # порядок сохранён, doc_id сконструирован из URL (или None без якоря)
    assert sources[0]["url"] == "https://its.1c.ru/db/molmoderpka25#content:711:hdoc"
    assert sources[0]["doc_id"] == "its-molmoderpka25-711-hdoc"
    assert sources[1]["doc_id"] == "its-pubdevguide83-461-hdoc"
    assert sources[2]["doc_id"] is None  # без якоря — кнопки не будет
    assert card["payload"]["total"] == 3
    assert card["payload"]["card_id"]  # uuid проставлен


def test_no_its_links_returns_none():
    # search_1c_documentation иногда без ссылок its.1c.ru — карточки нет.
    card = build_card_from_tool_result(
        "buddy.search_1c_documentation",
        {"query": "x"},
        _mcp_result("найдено 2 документов\nУправлениеБлокировкой/Элемент\n"),
    )
    assert card is None


def test_dedup_same_url():
    text = (
        "[A](https://its.1c.ru/db/x#content:1:hdoc)\n"
        "[A повтор](https://its.1c.ru/db/x#content:1:hdoc)\n"
    )
    card = build_card_from_tool_result("buddy.search_its", {}, _mcp_result(text))
    assert card is not None
    assert len(card["payload"]["sources"]) == 1
