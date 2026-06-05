"""Онбординг-детекция конфигурации на подключении базы (Multi-base, Phase 4).

При первом успешном ping новой базы (configuration ещё не установлена) фоном
запускаем дешёвые live-пробы маркеров → дискриминативный детект → confidence-gate
→ пишем configuration + configuration_source. Не блокирует чат, не зависит от
полного индекса метаданных.
"""
from __future__ import annotations

import logging

import aiosqlite

from app.knowledge.config_detection import gate_decision, update_channel_configuration
from app.knowledge.config_probe import detect_from_live

logger = logging.getLogger(__name__)

# gate_decision → configuration_source
_GATE_TO_SOURCE = {
    "auto": "auto",
    "confirm": "ambiguous",
    "custom": "custom",
}


async def should_run_detection(db: aiosqlite.Connection, channel_id: str) -> bool:
    """True, если для канала ещё не установлена configuration (детект не делали).

    Не перезапускаем на «горячих» базах с известной конфой — иначе лишние
    MCP-вызовы на каждый ping. Форс — через ручной override / переиндексацию.
    """
    cur = await db.execute(
        "SELECT configuration FROM mcp_connections WHERE id = ?",
        (channel_id,),
    )
    row = await cur.fetchone()
    if row is None:
        return False
    return row[0] is None


async def run_detection_for_channel(
    db: aiosqlite.Connection,
    channel_id: str,
    mcp_endpoint: str,
    *,
    anon_headers: dict[str, str] | None = None,
) -> None:
    """Выполняет live-детект и пишет результат. Никогда не raise наружу.

    Сбой MCP → configuration_source='failed' (бейдж «↻»), НЕ ложный УТ.
    """
    try:
        result = await detect_from_live(mcp_endpoint, anon_headers=anon_headers)
    except Exception as exc:  # noqa: BLE001 — фон, best-effort
        logger.warning(
            "Онбординг-детект для канала %s не завершён: %s", channel_id, exc
        )
        await db.execute(
            "UPDATE mcp_connections SET configuration_source = 'failed' WHERE id = ?",
            (channel_id,),
        )
        await db.commit()
        return

    decision = gate_decision(result)
    source = _GATE_TO_SOURCE[decision]
    await update_channel_configuration(db, channel_id, result, source=source)
    logger.info(
        "Онбординг-детект канала %s: %s (gate=%s, margin=%.2f)",
        channel_id, result.display_name, decision, result.margin,
    )
