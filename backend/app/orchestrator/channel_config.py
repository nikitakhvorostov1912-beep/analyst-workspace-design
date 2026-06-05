"""Мост: detected-конфигурация канала → typical channel_id + buddy-имя.

loop.py использует это, чтобы (а) сказать LLM, какой типовой channel_id брать
для конфо-зависимых вопросов, (б) подставить configuration в buddy.search_its.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import aiosqlite

from app.knowledge.config_detection import KNOWN_CONFIGURATIONS
from app.knowledge.typical.registry import TypicalConfigKind

logger = logging.getLogger(__name__)

# detection display_name («КА 2.5») → detection key («ka_2_5»).
_DISPLAY_TO_KEY: dict[str, str] = {
    sig.display_name: sig.key for sig in KNOWN_CONFIGURATIONS
}

# detection key → typical config_kind (для запроса typical_configurations).
# bgu_2_0 не имеет typical-снапшота → отсутствует в маппинге.
_KEY_TO_TYPICAL_KIND: dict[str, TypicalConfigKind] = {
    "ut_11_5": TypicalConfigKind.UT_115,
    "erp_2_5": TypicalConfigKind.ERP_25,
    "ka_2_5": TypicalConfigKind.KA_2,
    "bp_3_0": TypicalConfigKind.BP_30,
    "zup_3_1": TypicalConfigKind.ZUP_31,
    "uso_2_5": TypicalConfigKind.USO_25,
}

# detection key → строка configuration для buddy.search_its (Open Q4 дизайна:
# Напарник ждёт имя без версии; «Управление торговлей» сработало в тесте).
# bgu_2_0 — без typical-снапшота, но buddy-имя есть: иначе search_its даёт -32603.
_KEY_TO_BUDDY_CONFIG: dict[str, str] = {
    "ut_11_5": "Управление торговлей",
    "erp_2_5": "ERP Управление предприятием",
    "ka_2_5": "Комплексная автоматизация",
    "bp_3_0": "Бухгалтерия предприятия",
    "zup_3_1": "Зарплата и управление персоналом",
    "uso_2_5": "Управление строительной организацией",
    "bgu_2_0": "Бухгалтерия государственного учреждения",
}

_READY_TYPICAL_STATUSES = ("ready", "enriched", "graph_built")


@dataclass(frozen=True, slots=True)
class ChannelTypicalContext:
    """Контекст конфигурации канала для сборки промпта/диспетча buddy."""

    display_name: str | None        # «КА 2.5» (детект) или None
    typical_channel_id: str | None  # «_ka2_25_92» или None (типовая не загружена)
    typical_display_name: str | None
    buddy_config_name: str | None   # «Комплексная автоматизация» или None
    source: str | None              # auto/confirmed/manual/ambiguous/custom/failed

    @property
    def has_typical(self) -> bool:
        return self.typical_channel_id is not None


_EMPTY = ChannelTypicalContext(None, None, None, None, None)


async def resolve_channel_typical_context(
    db: aiosqlite.Connection,
    channel_id: str,
) -> ChannelTypicalContext:
    """Резолвит конфигурацию канала в typical channel_id + buddy-имя.

    Best-effort: при отсутствии конфы/типовой возвращает частично/полностью
    пустой контекст (loop.py работает как раньше — без инжекта).
    """
    cur = await db.execute(
        "SELECT configuration, configuration_source FROM mcp_connections WHERE id = ?",
        (channel_id,),
    )
    row = await cur.fetchone()
    if row is None or not row[0] or row[0] == "Самописная":
        return _EMPTY

    display_name, source = row[0], row[1]
    key = _DISPLAY_TO_KEY.get(display_name)
    if key is None:
        return ChannelTypicalContext(display_name, None, None, None, source)

    buddy_name = _KEY_TO_BUDDY_CONFIG.get(key)
    kind = _KEY_TO_TYPICAL_KIND.get(key)
    if kind is None:
        return ChannelTypicalContext(display_name, None, None, buddy_name, source)

    # Берём самую свежую готовую типовую этого kind.
    placeholders = ",".join("?" * len(_READY_TYPICAL_STATUSES))
    cur2 = await db.execute(
        f"SELECT channel_id, display_name FROM typical_configurations "
        f"WHERE config_kind = ? AND status IN ({placeholders}) "
        f"ORDER BY config_version DESC LIMIT 1",
        (kind.value, *_READY_TYPICAL_STATUSES),
    )
    trow = await cur2.fetchone()
    if trow is None:
        return ChannelTypicalContext(display_name, None, None, buddy_name, source)

    return ChannelTypicalContext(
        display_name=display_name,
        typical_channel_id=trow[0],
        typical_display_name=trow[1],
        buddy_config_name=buddy_name,
        source=source,
    )
