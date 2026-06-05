"""Тесты сборки config-блока system prompt (Phase 5)."""
from app.orchestrator.channel_config import ChannelTypicalContext
from app.orchestrator.loop import SYSTEM_PROMPT, _build_config_block, _build_full_system_prompt


def test_config_block_with_typical():
    ctx = ChannelTypicalContext(
        display_name="КА 2.5", typical_channel_id="_ka2_25_92",
        typical_display_name="Комплексная автоматизация 2.5",
        buddy_config_name="Комплексная автоматизация", source="auto",
    )
    block = _build_config_block(ctx)
    assert "КА 2.5" in block
    assert "_ka2_25_92" in block


def test_config_block_empty_when_no_context():
    ctx = ChannelTypicalContext(None, None, None, None, None)
    assert _build_config_block(ctx) == ""


def test_full_prompt_includes_config_block():
    ctx = ChannelTypicalContext(
        display_name="КА 2.5", typical_channel_id="_ka2_25_92",
        typical_display_name="Комплексная автоматизация 2.5",
        buddy_config_name="Комплексная автоматизация", source="auto",
    )
    prompt = _build_full_system_prompt("", "", "", config_block=_build_config_block(ctx))
    assert "_ka2_25_92" in prompt


def test_system_prompt_has_howto_style_guidance():
    # B.4d: для «как сделать X» — практические шаги, не дамп реквизитов.
    assert "практическ" in SYSTEM_PROMPT.lower()
    assert "как сделать" in SYSTEM_PROMPT.lower() or "how-to" in SYSTEM_PROMPT.lower()
