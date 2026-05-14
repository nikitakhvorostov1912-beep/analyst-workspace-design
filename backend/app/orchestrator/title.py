"""Auto-title генерация после первого сообщения пользователя.

Две стратегии:
1. Cheap LLM call — если llm_client и api_key переданы.
2. Эвристика — первые 5-7 слов до знака препинания; fallback «Новый чат».
"""

import logging
import re

from app.clients.llm import LLMClient

logger = logging.getLogger(__name__)

_PUNCT_PATTERN = re.compile(r"[.!?,;:]")

FALLBACK_TITLE = "Новый чат"
MAX_TITLE_LEN = 60
MAX_TITLE_WORDS = 7


def heuristic_title(message: str) -> str:
    """Генерирует короткий заголовок из первых слов сообщения.

    Берёт первые MAX_TITLE_WORDS слов до первого знака препинания.
    Обрезает до MAX_TITLE_LEN символов + «...» при превышении.
    Fallback «Новый чат» если сообщение пустое.
    """
    text = message.strip()
    if not text:
        return FALLBACK_TITLE

    # Обрезаем по первому знаку препинания
    match = _PUNCT_PATTERN.search(text)
    if match:
        text = text[: match.start()].strip()

    # Берём первые MAX_TITLE_WORDS слов
    words = text.split()
    if not words:
        return FALLBACK_TITLE

    title = " ".join(words[:MAX_TITLE_WORDS])

    # Обрезаем по длине
    if len(title) > MAX_TITLE_LEN:
        title = title[:57] + "..."

    return title or FALLBACK_TITLE


async def generate_title(
    message: str,
    llm_client: LLMClient | None,
    api_key: str | None,
) -> str:
    """Генерирует заголовок сессии.

    Если llm_client и api_key переданы — использует cheap LLM call (temperature=0.1).
    При любой ошибке LLM — fallback на heuristic_title(message).
    Если llm_client None — сразу возвращает heuristic_title(message).
    """
    if llm_client is None or not api_key:
        return heuristic_title(message)

    try:
        messages = [
            {
                "role": "system",
                "content": (
                    "Сформулируй короткое название чата (3-7 слов на русском) "
                    "по первому сообщению. Без кавычек, без точки в конце."
                ),
            },
            {"role": "user", "content": message[:500]},
        ]

        collected = ""
        async for chunk in llm_client.stream_chat_completion(
            messages=messages,
            api_key=api_key,
            tools=None,
            temperature=0.1,
        ):
            delta = chunk.get("delta", {})
            piece = delta.get("content", "")
            if piece:
                collected += piece
            if len(collected) > 100:
                break

        title = collected.strip()
        return title if title else heuristic_title(message)

    except Exception:
        logger.warning("LLM title generation failed, using heuristic", exc_info=True)
        return heuristic_title(message)
