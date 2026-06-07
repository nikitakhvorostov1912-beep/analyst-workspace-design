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


def test_prompt_its_fetch_top1_directive():
    # ИТС: search_its -> fetch_its топ-1, ссылки не дублировать (есть карточка).
    assert "fetch_its" in SYSTEM_PROMPT
    assert "карточк" in SYSTEM_PROMPT.lower()
    assert (
        "не дублируй" in SYSTEM_PROMPT.lower()
        or "не повторяй ссылк" in SYSTEM_PROMPT.lower()
    )


def test_prompt_trimmed_under_budget():
    # Консервативный трим: ≤ 18000 символов (было ~22535). Режем примеры, не правила.
    assert len(SYSTEM_PROMPT) <= 18000
    # Ключевые ПРАВИЛА на месте (не вырезать):
    assert "НИКОГДА не отвечай по «общим знаниям»" in SYSTEM_PROMPT
    assert "СТРАТЕГИЯ ВЫБОРА ИСТОЧНИКОВ" in SYSTEM_PROMPT
    assert "meta_type" in SYSTEM_PROMPT
    assert "ТекущаяДатаСеанса" in SYSTEM_PROMPT
    assert "memory_append" in SYSTEM_PROMPT
    assert "```chart" in SYSTEM_PROMPT  # формат графика сохранён (хотя бы 1 пример)
