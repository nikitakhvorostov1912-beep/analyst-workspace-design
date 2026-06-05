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
