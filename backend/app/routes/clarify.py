"""POST /chat/clarify — ответ пользователя на clarify_question.

Sprint 4 (Hermes D1).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.orchestrator.clarify import CLARIFY

logger = logging.getLogger(__name__)
router = APIRouter(tags=["clarify"])


class ClarifyAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clarify_id: str = Field(min_length=1)
    answer: str | list[str]


@router.post("/chat/clarify", status_code=204)
async def clarify_answer(body: ClarifyAnswer):
    """Подтверждает ответ на clarify_question.

    Returns:
        204 если pending был зарегистрирован и future закрыт.
        404 если clarify_id не найден или таймаут наступил раньше.
    """
    resolved = CLARIFY.resolve(body.clarify_id, body.answer)
    if not resolved:
        raise HTTPException(status_code=404, detail="clarify_id не найден или истёк")
    return None
