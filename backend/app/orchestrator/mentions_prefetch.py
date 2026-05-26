"""Mentions pre-fetcher — оркестрационная обвязка для M-K1.14.

Между chat-request validation и LLM-итерациями (`loop.py` line ~1149):
- парсим `@Тип.Имя` в user-сообщении
- для каждого mention читаем dossier из metadata_cache
- возвращаем готовые ObjectCard payloads + system-prompt context block

Логика чистая (без yield SSE) — loop.py сам решает что делать с результатом:
emit cards + добавить block в system prompt.

Все ошибки swallowed (best-effort) — если что-то ломается, loop продолжает
работу как раньше: одна сломанная фича не должна валить весь chat.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import aiosqlite

from app.knowledge.dossier import (
    DossierNotFoundError,
    ObjectDossier,
    get_dossier,
)
from app.knowledge.mentions import (
    ObjectMention,
    dossier_to_object_card,
    parse_object_mentions,
    render_mentions_context_block,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class MentionPrefetchResult:
    """Результат предзагрузки mentions.

    Attrs:
        cards: list[dict] — готовых ObjectCard payloads для SSE emit.
                Пустой список если в сообщении не было mentions или ни один
                не нашёлся в кеше.
        context_block: текстовый блок для system prompt (None если нечего
                добавлять).
        mentions: распарсенные mentions (для диагностики / тестов).
        found_count: сколько dossiers удалось получить.
        not_found_count: сколько mentions не нашлось в кеше.
    """

    cards: list[dict]
    context_block: str | None
    mentions: list[ObjectMention]
    found_count: int
    not_found_count: int


async def prefetch_mentions(
    db: aiosqlite.Connection,
    channel_id: str,
    user_message: str,
) -> MentionPrefetchResult:
    """Парсит mentions в сообщении и подгружает dossiers из кеша.

    Args:
        db: SQLite connection (та же что использует /chat).
        channel_id: канал MCP — определяет namespace metadata_cache.
        user_message: оригинальный текст пользователя (без attachments).

    Returns:
        MentionPrefetchResult с cards, context_block и счётчиками.
        Если mentions нет вообще — возвращает пустой result (cards=[],
        context_block=None, mentions=[]).
    """
    mentions = parse_object_mentions(user_message)
    if not mentions:
        return MentionPrefetchResult(
            cards=[],
            context_block=None,
            mentions=[],
            found_count=0,
            not_found_count=0,
        )

    # Параллельная загрузка из кеша — один SQLite запрос на каждый mention.
    # Кешированный пул соединений уже asynchronous, но db.execute не
    # распараллеливается на одном connection — поэтому идём sequentially.
    # Для M-K1.14 typical N = 1-3 mentions, perf cost негативен.
    dossiers: dict[str, ObjectDossier] = {}
    for mention in mentions:
        try:
            dossier = await get_dossier(db, channel_id, mention.full)
        except DossierNotFoundError:
            logger.debug(
                "Mention %s не найден в metadata_cache канала %s",
                mention.full,
                channel_id,
            )
            continue
        except ValueError as exc:
            # ObjectPath.parse не справился — невалидный mention.
            # parse_object_mentions должен был отфильтровать, но на всякий случай.
            logger.warning(
                "Невалидный mention %r: %s",
                mention.full,
                exc,
            )
            continue
        except asyncio.CancelledError:
            # Не перехватываем отмену задачи — пробрасываем дальше
            # (loop.py может быть отменён через GeneratorExit / interrupt).
            raise
        except Exception:
            logger.exception(
                "Ошибка чтения dossier для %s (channel=%s)",
                mention.full,
                channel_id,
            )
            continue
        dossiers[mention.full] = dossier

    cards = [
        dossier_to_object_card(dossiers[mention.full])
        for mention in mentions
        if mention.full in dossiers
    ]
    context_block = render_mentions_context_block(mentions, dossiers)
    found_count = len(dossiers)
    not_found_count = len(mentions) - found_count

    if found_count or not_found_count:
        logger.info(
            "Mentions prefetch: %d found / %d not_found в канале %s",
            found_count,
            not_found_count,
            channel_id,
        )

    return MentionPrefetchResult(
        cards=cards,
        context_block=context_block,
        mentions=mentions,
        found_count=found_count,
        not_found_count=not_found_count,
    )
