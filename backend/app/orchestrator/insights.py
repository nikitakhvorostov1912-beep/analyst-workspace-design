"""Insights engine — SQLite-аналитика сессий.

Sprint 4 (Hermes G8 lite): сжатый дашборд для аналитика 1С.
В оригинале Hermes 930 строк — у нас минимально жизнеспособное:

- Sessions / messages count.
- Top channels (multi-tenant view).
- Top tools (какие MCP-инструменты вызываются чаще).
- Tool error rate.
- Duration percentiles (если есть в БД).
- Период: last 24h / 7d / 30d / all.

API всегда read-only — никаких INSERT/UPDATE.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

import aiosqlite

logger = logging.getLogger(__name__)


Period = Literal["24h", "7d", "30d", "all"]


@dataclass(frozen=True)
class ToolStat:
    name: str
    calls: int
    errors: int

    @property
    def error_rate(self) -> float:
        if self.calls == 0:
            return 0.0
        return round(self.errors / self.calls, 4)


@dataclass(frozen=True)
class ChannelStat:
    channel_id: str
    sessions: int
    messages: int


@dataclass(frozen=True)
class InsightsReport:
    period: Period
    generated_at: str
    sessions: int
    messages: int
    tool_calls_total: int
    tool_errors_total: int
    avg_duration_ms: int | None
    top_channels: list[ChannelStat]
    top_tools: list[ToolStat]
    # Sprint 5 (I4): оценочные токены и стоимость (estimated, не от LLM provider).
    estimated_tokens: int = 0
    estimated_cost_usd: float = 0.0


def _period_cutoff(period: Period) -> str | None:
    """Возвращает ISO 8601 timestamp (UTC) или None для 'all'."""
    if period == "all":
        return None
    now = datetime.now(UTC)
    deltas = {"24h": timedelta(hours=24), "7d": timedelta(days=7), "30d": timedelta(days=30)}
    return (now - deltas[period]).isoformat()


async def collect_insights(
    db: aiosqlite.Connection,
    *,
    period: Period = "7d",
    top_n: int = 10,
) -> InsightsReport:
    """Собирает агрегированную статистику.

    Args:
        db: aiosqlite connection (read-only access).
        period: окно времени.
        top_n: размер top-N выдачи.

    Returns:
        InsightsReport.
    """
    cutoff = _period_cutoff(period)
    where_clause = ""
    params: tuple = ()
    if cutoff is not None:
        where_clause = "WHERE m.created_at >= ?"
        params = (cutoff,)

    # 1) Сессии и сообщения в окне.
    async with db.execute(
        f"""
        SELECT
            COUNT(DISTINCT m.session_id) AS sessions,
            COUNT(*) AS messages
        FROM messages m
        {where_clause}
        """,
        params,
    ) as cur:
        row = await cur.fetchone()
        sessions = int(row[0]) if row else 0
        messages = int(row[1]) if row else 0

    # 2) Top channels по сессиям.
    channels: list[ChannelStat] = []
    if cutoff is None:
        ch_query = """
            SELECT s.channel_id, COUNT(DISTINCT s.id), COUNT(m.id)
            FROM sessions s
            LEFT JOIN messages m ON m.session_id = s.id
            GROUP BY s.channel_id
            ORDER BY 2 DESC
            LIMIT ?
        """
        ch_params: tuple = (top_n,)
    else:
        ch_query = """
            SELECT s.channel_id, COUNT(DISTINCT s.id), COUNT(m.id)
            FROM sessions s
            LEFT JOIN messages m ON m.session_id = s.id
            WHERE m.created_at >= ?
            GROUP BY s.channel_id
            ORDER BY 2 DESC
            LIMIT ?
        """
        ch_params = (cutoff, top_n)
    async with db.execute(ch_query, ch_params) as cur:
        async for r in cur:
            channels.append(
                ChannelStat(
                    channel_id=str(r[0]) if r[0] else "?",
                    sessions=int(r[1]) if r[1] else 0,
                    messages=int(r[2]) if r[2] else 0,
                )
            )

    # 3) Tool calls / errors / top tools.
    # tool_calls хранятся как JSON в messages.tool_calls. Не парсим SQL-стороной
    # (медленно), а читаем строки и считаем в Python с лимитом.
    tool_query = "SELECT tool_calls FROM messages"
    if cutoff is not None:
        tool_query += " WHERE created_at >= ?"
    tool_params: tuple = (cutoff,) if cutoff is not None else ()
    tool_query += " ORDER BY id DESC LIMIT 5000"

    tool_calls_total = 0
    tool_errors_total = 0
    by_name: dict[str, dict[str, int]] = {}
    duration_samples: list[int] = []

    async with db.execute(tool_query, tool_params) as cur:
        async for r in cur:
            raw = r[0]
            if not raw:
                continue
            try:
                import json as _json

                items = _json.loads(raw)
            except Exception:
                continue
            if not isinstance(items, list):
                continue
            for it in items:
                if not isinstance(it, dict):
                    continue
                tool_calls_total += 1
                name = str(it.get("name") or "unknown")
                err = it.get("error")
                if err:
                    tool_errors_total += 1
                entry = by_name.setdefault(name, {"calls": 0, "errors": 0})
                entry["calls"] += 1
                if err:
                    entry["errors"] += 1
                dur = it.get("duration_ms")
                if isinstance(dur, int):
                    duration_samples.append(dur)

    top_tools = sorted(
        (
            ToolStat(name=n, calls=stats["calls"], errors=stats["errors"])
            for n, stats in by_name.items()
        ),
        key=lambda t: t.calls,
        reverse=True,
    )[:top_n]

    avg_duration = None
    if duration_samples:
        avg_duration = int(sum(duration_samples) / len(duration_samples))

    # Sprint 5 (I4): estimated tokens + cost.
    # Очень грубая оценка: содержимое messages.content + tool_calls.
    # Реальные usage tokens хотелось бы брать из LLM provider response —
    # но MiMo/OpenAI-compat не всегда возвращают usage в SSE, поэтому считаем сами.
    estimated_tokens, estimated_cost = await _estimate_tokens_and_cost(db, cutoff)

    return InsightsReport(
        period=period,
        generated_at=datetime.now(UTC).isoformat(),
        sessions=sessions,
        messages=messages,
        tool_calls_total=tool_calls_total,
        tool_errors_total=tool_errors_total,
        avg_duration_ms=avg_duration,
        top_channels=channels,
        top_tools=top_tools,
        estimated_tokens=estimated_tokens,
        estimated_cost_usd=round(estimated_cost, 4),
    )


async def _estimate_tokens_and_cost(
    db: aiosqlite.Connection, cutoff: str | None
) -> tuple[int, float]:
    """Грубая оценка токенов + стоимости по содержимому messages.

    Берём суммарную длину content + tool_calls, делим на 3.5 (chars per token),
    оцениваем как input для активной модели (используем дефолтную из настроек).
    """
    from app.config import get_settings
    from app.orchestrator.usage_pricing import compute_turn_cost

    where_clause = ""
    params: tuple = ()
    if cutoff is not None:
        where_clause = "WHERE created_at >= ?"
        params = (cutoff,)

    total_chars = 0
    output_chars = 0
    async with db.execute(
        f"""
        SELECT role, content, tool_calls FROM messages
        {where_clause}
        ORDER BY id DESC LIMIT 10000
        """,
        params,
    ) as cur:
        async for r in cur:
            role = r[0]
            content = r[1] or ""
            tool_calls = r[2] or ""
            chars = len(content) + len(tool_calls)
            total_chars += chars
            if role == "assistant":
                output_chars += chars

    if total_chars == 0:
        return 0, 0.0

    input_chars = total_chars - output_chars
    input_tokens = int(input_chars / 3.5)
    output_tokens = int(output_chars / 3.5)

    settings = get_settings()
    cost = compute_turn_cost(
        model=settings.default_llm_model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
    return (input_tokens + output_tokens), cost.total_cost_usd
