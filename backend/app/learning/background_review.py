"""Background review fork — после каждого turn'а решаем "сохранить ли skill?".

Sprint 3 (Hermes A5): daemon-task через asyncio.create_task() форкает aux LLM,
который анализирует завершённый turn (user message + assistant + tools) и
решает, есть ли в нём паттерн, заслуживающий сохранения как skill.

Strict invariants (из Hermes):
- Не блокирует основной loop (fire-and-forget через asyncio.create_task).
- Aux LLM ≠ main → не съедает prompt cache main модели.
- Toolset ограничен memory+skill ops.
- Provenance = 'agent' — Curator потом сможет авто-архивировать.

Минимально жизнеспособное:
- Простой prompt aux LLM: "вот turn. Заслуживает ли он skill? Если да — придумай
  id (kebab), tags, body."
- Response — JSON: {"save": bool, "id": str, "tags": [str], "body": str}.
- В случае save=True → SkillStore.write() с provenance='agent'.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from app.learning.skill_provenance import provenance
from app.learning.skill_store import Skill, SkillStore

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """Ты — куратор знаний AI-аналитика 1С. Тебе показывают завершённый turn диалога:
вопрос пользователя + ответ ассистента (с возможными tool calls).

Реши: есть ли в этом turn ПОВТОРЯЕМЫЙ паттерн, который стоит сохранить как
готовое решение (skill)? Skill — это короткая инструкция вида «когда юзер
спрашивает X — делай Y». Сохраняй ТОЛЬКО:
- Конкретные запросы / коды / последовательности tool_call, которые сработали.
- Терминологию пользователя (как он называет объекты).
- Соглашения базы (имена справочников, регистров, нестандартные поля).

НЕ сохраняй:
- Тривиальные вопросы / приветствия.
- Ошибочные ответы / неудачные turn'ы.
- Очень общие правила (это уже в system prompt).

Ответь СТРОГО валидным JSON одной строкой:
{
  "save": true|false,
  "id": "skill-id-kebab",           // 1-64 символа [a-z0-9_-], только если save=true
  "tags": ["tag1", "tag2"],          // 1-5 коротких тегов, только если save=true
  "body": "..."                     // 100-2000 символов markdown, только если save=true
}

Если save=false — остальные поля можно опустить (или дать пустыми).
"""


@dataclass(frozen=True)
class ReviewDecision:
    save: bool
    skill_id: str | None
    tags: list[str]
    body: str


def _format_turn(user_msg: str, assistant_msg: str, tool_calls: list[dict]) -> str:
    """Plain text representation для aux LLM."""
    parts: list[str] = []
    parts.append(f"USER: {user_msg[:2000]}")
    if tool_calls:
        for tc in tool_calls[:10]:  # cap на случай runaway
            name = tc.get("name", "?")
            args = json.dumps(tc.get("args", {}), ensure_ascii=False)[:500]
            error = tc.get("error")
            if error:
                parts.append(f"TOOL[{name}] ERROR: {error[:200]}")
            else:
                duration = tc.get("duration_ms", 0)
                parts.append(f"TOOL[{name}] OK ({duration}ms): {args}")
    parts.append(f"ASSISTANT: {assistant_msg[:3000]}")
    return "\n".join(parts)


def _parse_decision(raw: str) -> ReviewDecision:
    """Парсит JSON-ответ aux LLM в ReviewDecision. Безопасно к мусору."""
    # Aux может вернуть response с обёртками типа "```json\n{...}\n```" — снимаем.
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\n", "", text)
        text = re.sub(r"\n```$", "", text)

    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return ReviewDecision(save=False, skill_id=None, tags=[], body="")

    if not isinstance(data, dict):
        return ReviewDecision(save=False, skill_id=None, tags=[], body="")

    save = bool(data.get("save"))
    if not save:
        return ReviewDecision(save=False, skill_id=None, tags=[], body="")

    skill_id = data.get("id")
    body = data.get("body", "")
    tags_raw = data.get("tags") or []

    if (
        not isinstance(skill_id, str)
        or not isinstance(body, str)
        or not isinstance(tags_raw, list)
    ):
        return ReviewDecision(save=False, skill_id=None, tags=[], body="")

    if not body.strip() or len(body) < 50:
        return ReviewDecision(save=False, skill_id=None, tags=[], body="")

    # Нормализуем skill_id — приводим к нашему формату [A-Za-z0-9_-].
    skill_id = re.sub(r"[^A-Za-z0-9_-]", "_", skill_id)[:64]
    if not skill_id:
        return ReviewDecision(save=False, skill_id=None, tags=[], body="")

    tags = [str(t)[:32] for t in tags_raw if isinstance(t, str)][:5]
    return ReviewDecision(save=True, skill_id=skill_id, tags=tags, body=body)


async def review_turn(
    *,
    user_msg: str,
    assistant_msg: str,
    tool_calls: list[dict],
    skill_store: SkillStore,
    aux_client: Any,  # AuxiliaryClient, избегаем circular import
    max_body_chars: int = 2_000,
) -> ReviewDecision:
    """Однократный review одного turn'а через aux LLM.

    Returns:
        ReviewDecision с save=True если skill был сохранён.
    """
    if not assistant_msg or not assistant_msg.strip():
        return ReviewDecision(save=False, skill_id=None, tags=[], body="")

    turn_text = _format_turn(user_msg, assistant_msg, tool_calls)
    aux_messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": turn_text},
    ]
    try:
        raw = await aux_client.complete_with_fallback(
            aux_messages, max_tokens=800, temperature=0.1
        )
    except Exception:
        logger.exception("Background review: aux client exception")
        return ReviewDecision(save=False, skill_id=None, tags=[], body="")

    if not raw:
        return ReviewDecision(save=False, skill_id=None, tags=[], body="")

    decision = _parse_decision(raw)
    if not decision.save or not decision.skill_id:
        return decision

    # Cap body
    body = decision.body[:max_body_chars]

    try:
        with provenance("agent"):
            skill = Skill(
                id=decision.skill_id,
                body=body,
                provenance="agent",
                tags=decision.tags,
            )
            skill_store.write(skill)
        logger.info("Background review сохранил skill %s", decision.skill_id)
    except ValueError as exc:
        logger.info("Background review skill rejected: %s", exc)
        return ReviewDecision(save=False, skill_id=None, tags=[], body="")
    except Exception:
        logger.exception("Background review write failed")
        return ReviewDecision(save=False, skill_id=None, tags=[], body="")

    return ReviewDecision(
        save=True, skill_id=decision.skill_id, tags=decision.tags, body=body
    )


def schedule_review(
    *,
    user_msg: str,
    assistant_msg: str,
    tool_calls: list[dict],
    skill_store: SkillStore | None,
    aux_client: Any | None,
) -> None:
    """Fire-and-forget: запускает review_turn в background task.

    Если skill_store или aux_client = None — no-op.
    Exceptions из task не пробрасываются — это side-task.
    """
    if skill_store is None or aux_client is None:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.warning("schedule_review вызван вне event loop — пропускаем")
        return

    async def _runner() -> None:
        try:
            await review_turn(
                user_msg=user_msg,
                assistant_msg=assistant_msg,
                tool_calls=tool_calls,
                skill_store=skill_store,
                aux_client=aux_client,
            )
        except Exception:
            logger.exception("Background review task failed")

    loop.create_task(_runner())
