"""Тесты инжекта configuration в buddy.search_its/fetch_its (Phase 5.4)."""
from app.orchestrator.channel_config import ChannelTypicalContext
from app.orchestrator.loop import _inject_buddy_configuration


def test_inject_adds_configuration_for_search_its():
    ctx = ChannelTypicalContext("КА 2.5", "_ka2_25_92", "КА 2.5",
                                "Комплексная автоматизация", "auto")
    args = {"query": "настройка обеспечения"}
    out = _inject_buddy_configuration("buddy.search_its", args, ctx)
    assert out["configuration"] == "Комплексная автоматизация"
    assert out["query"] == "настройка обеспечения"


def test_inject_does_not_override_explicit_configuration():
    ctx = ChannelTypicalContext("КА 2.5", "_ka2_25_92", "КА 2.5",
                                "Комплексная автоматизация", "auto")
    args = {"query": "x", "configuration": "Бухгалтерия предприятия"}
    out = _inject_buddy_configuration("buddy.search_its", args, ctx)
    assert out["configuration"] == "Бухгалтерия предприятия"


def test_inject_noop_for_non_buddy_and_missing_ctx():
    ctx_empty = ChannelTypicalContext(None, None, None, None, None)
    args = {"query": "x"}
    assert "configuration" not in _inject_buddy_configuration("buddy.search_its", args, ctx_empty)
    ctx = ChannelTypicalContext("КА 2.5", "_ka2_25_92", "КА 2.5",
                                "Комплексная автоматизация", "auto")
    assert "configuration" not in _inject_buddy_configuration("buddy.other", dict(args), ctx)


def test_inject_config_into_ask_1c_ai():
    ctx = ChannelTypicalContext("КА 2.5", "_ka2_25_92", "КА 2.5",
                                "Комплексная автоматизация", "auto")
    out = _inject_buddy_configuration("buddy.ask_1c_ai", {"question": "Как настроить RLS?"}, ctx)
    assert out["configuration"] == "Комплексная автоматизация"
    # явно переданное не перетираем
    out2 = _inject_buddy_configuration(
        "buddy.ask_1c_ai", {"question": "x", "configuration": "ERP"}, ctx
    )
    assert out2["configuration"] == "ERP"


# --- Детерминированная карточка источников после ask_1c_ai ---


class _FakeBuddyClient:
    def __init__(self, text):
        self._text = text

    async def call_tool(self, name, args):
        return {"content": [{"type": "text", "text": self._text}]}


class _FakeBuddyPool:
    def __init__(self, text):
        self._client = _FakeBuddyClient(text)

    def client_for(self, name):
        return self._client


def test_build_sources_card_via_search_its_builds_card():
    import asyncio
    from app.orchestrator.loop import _build_sources_card_via_search_its
    ctx = ChannelTypicalContext("КА 2.5", "_ka2_25_92", "КА 2.5",
                                "Комплексная автоматизация", "auto")
    pool = _FakeBuddyPool(
        "[Пособие разработчика](https://its.1c.ru/db/pubdevguide83#content:461:hdoc)\n"
    )
    card = asyncio.run(_build_sources_card_via_search_its(pool, ctx, "RLS"))
    assert card is not None
    assert card["type"] == "its_sources"
    assert card["payload"]["sources"][0]["doc_id"] == "its-pubdevguide83-461-hdoc"


def test_build_sources_card_via_search_its_none_when_no_links():
    import asyncio
    from app.orchestrator.loop import _build_sources_card_via_search_its
    ctx = ChannelTypicalContext("КА 2.5", "_ka", "КА", "Комплексная автоматизация", "auto")
    pool = _FakeBuddyPool("в выдаче нет ссылок its.1c.ru")
    assert asyncio.run(_build_sources_card_via_search_its(pool, ctx, "x")) is None
