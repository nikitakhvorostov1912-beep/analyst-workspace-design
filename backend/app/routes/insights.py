"""GET /insights — sessions / messages / tools dashboard.

Sprint 4 (Hermes G8 lite).
"""

from __future__ import annotations

import logging

import aiosqlite
from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict

from app.orchestrator.insights import Period, collect_insights

logger = logging.getLogger(__name__)
router = APIRouter(tags=["insights"])


def _get_db(request: Request) -> aiosqlite.Connection:
    return request.app.state.db


class ToolStatDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    calls: int
    errors: int
    error_rate: float


class ChannelStatDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel_id: str
    sessions: int
    messages: int


class InsightsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period: str
    generated_at: str
    sessions: int
    messages: int
    tool_calls_total: int
    tool_errors_total: int
    avg_duration_ms: int | None
    top_channels: list[ChannelStatDTO]
    top_tools: list[ToolStatDTO]


@router.get("/insights", response_model=InsightsResponse)
async def insights_endpoint(
    period: Period = Query(default="7d", description="24h | 7d | 30d | all"),
    top_n: int = Query(default=10, ge=1, le=50),
    db=Depends(_get_db),
) -> InsightsResponse:
    report = await collect_insights(db, period=period, top_n=top_n)
    return InsightsResponse(
        period=report.period,
        generated_at=report.generated_at,
        sessions=report.sessions,
        messages=report.messages,
        tool_calls_total=report.tool_calls_total,
        tool_errors_total=report.tool_errors_total,
        avg_duration_ms=report.avg_duration_ms,
        top_channels=[
            ChannelStatDTO(channel_id=c.channel_id, sessions=c.sessions, messages=c.messages)
            for c in report.top_channels
        ],
        top_tools=[
            ToolStatDTO(name=t.name, calls=t.calls, errors=t.errors, error_rate=t.error_rate)
            for t in report.top_tools
        ],
    )
