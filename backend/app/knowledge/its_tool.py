"""ITS Tool — `search_its` для LLM-orchestrator (M-K2.7).

Knowledge Foundation Phase 7 (последняя часть): экспозит ITS RAG как
внутренний async-tool, который LLM может вызвать когда:
- спрашивают «как избежать запроса в цикле?» (ИТС-стандарт)
- «какие методы БСП для длительных операций?» (паттерн)
- «что такое RLS?» (методология / справка)

LLM сама решает звать ли search_its по описанию в SYSTEM_PROMPT
(внутренние tools — наравне с MCP в openai_tools list).

**Singleton embedding-клиента:**
- Создаётся лениво при первом вызове dispatch_its_tool.
- Один на процесс backend (FastAPI uvicorn worker).
- aclose() при graceful shutdown — НЕ реализован в M-K2.7, утечка
  одного httpx.AsyncClient безопасна для long-running процесса.

**Связь с loop.py:**
- `is_its_enabled(settings)` решает, добавлять ли tool в
  `_build_openai_tools` (только при settings.is_its_ready).
- `dispatch_its_tool` вызывается из main loop между sync_internal
  и clarify (см. `_dispatch_async_internal_tool` если будет).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiosqlite

from app.config import Settings
from app.knowledge.embeddings import (
    EmbeddingClient,
    EmbeddingError,
    MockEmbeddingClient,
    OpenAIEmbeddingClient,
)
from app.knowledge.its_search import (
    DEFAULT_SEARCH_K,
    ITSSearchError,
    search_its,
)

logger = logging.getLogger(__name__)


SEARCH_ITS_TOOL_NAME = "search_its"


# Жёсткий cap на k — больше 20 чанков забьют context LLM.
_MAX_K = 20


ITS_TOOL_SCHEMA: dict = {
    "type": "function",
    "function": {
        "name": SEARCH_ITS_TOOL_NAME,
        "description": (
            "Поиск по корпусу ИТС-стандартов 1С (zeegin/v8std). "
            "Когда вызывать: вопросы о методологии 1С (запросы, "
            "блокировки, БСП, RLS, паттерны разработки), без привязки "
            "к конкретной базе клиента. Возвращает топ-K фрагментов "
            "с цитатами на исходные стандарты (std396, pattern-engineering-dry, "
            "diag-bslls-..., metod1590, lang-...). НЕ вызывай для вопросов "
            "о структуре или данных конкретной базы — там MCP-инструменты "
            "(get_metadata / execute_query)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Естественноязыковой запрос. Примеры: "
                        "«как избежать запроса в цикле», "
                        "«паттерн Long-running operations в БСП», "
                        "«стандарт оформления обработчика ОбработкаЗаполнения»."
                    ),
                },
                "k": {
                    "type": "integer",
                    "description": (
                        f"Сколько фрагментов вернуть. По умолчанию {DEFAULT_SEARCH_K}, "
                        f"максимум {_MAX_K}. Бери минимум, который покроет вопрос."
                    ),
                    "minimum": 1,
                    "maximum": _MAX_K,
                },
            },
            "required": ["query"],
        },
    },
}


def is_its_tool(name: str) -> bool:
    """True если name == search_its."""
    return name == SEARCH_ITS_TOOL_NAME


def is_its_enabled(settings: Settings) -> bool:
    """True если settings разрешают exposing search_its для LLM."""
    return settings.is_its_ready


async def its_index_ready(db: aiosqlite.Connection) -> bool:
    """True если индекс ИТС реально наполнен (есть хотя бы один чанк).

    Защита от ситуации «tool разрешён конфигом (is_its_enabled=True), но индекс
    пуст или таблицы нет» — тогда search_its падал бы «ITS RAG не настроен», а
    LLM делал вид, что искал в ИТС (жалоба пользователя). Если индекса нет —
    tool вообще не предлагаем модели. Missing-table / любая ошибка → не готов
    (консервативно).
    """
    try:
        cursor = await db.execute("SELECT 1 FROM its_chunks LIMIT 1")
        row = await cursor.fetchone()
        await cursor.close()
        return row is not None
    except Exception:  # noqa: BLE001 — таблицы может не быть → «не готов»
        return False


# ============================================================================
# Singleton embedding-клиента (lazy init, threadsafe через asyncio.Lock)
# ============================================================================

_embedding_client: EmbeddingClient | None = None
_embedding_client_lock = asyncio.Lock()


def _build_embedding_client(settings: Settings) -> EmbeddingClient:
    """Создаёт клиент по settings. Чистая функция (не singleton)."""
    if settings.its_embedding_provider == "mock":
        return MockEmbeddingClient(dim=settings.its_embedding_dim)
    if settings.its_embedding_provider == "openai":
        api_key = settings.resolved_its_api_key
        if not api_key:
            raise EmbeddingError(
                "ITS embedding provider='openai' но API key не задан "
                "(ITS_EMBEDDING_API_KEY или DEFAULT_LLM_API_KEY_OPENAI)"
            )
        return OpenAIEmbeddingClient(
            endpoint=settings.its_embedding_endpoint,
            api_key=api_key,
            model=settings.its_embedding_model,
            dim=settings.its_embedding_dim,
        )
    raise EmbeddingError(
        f"Неизвестный its_embedding_provider: {settings.its_embedding_provider}"
    )


async def get_embedding_client(settings: Settings) -> EmbeddingClient:
    """Lazy singleton. Создаёт клиент при первом вызове.

    Для тестов: `reset_embedding_client()` сбрасывает singleton, чтобы
    каждый test мог получить свежий MockEmbeddingClient.
    """
    global _embedding_client
    if _embedding_client is None:
        async with _embedding_client_lock:
            if _embedding_client is None:
                _embedding_client = _build_embedding_client(settings)
                logger.info(
                    "ITS embedding client initialized: provider=%s model=%s dim=%d",
                    settings.its_embedding_provider,
                    settings.its_embedding_model,
                    settings.its_embedding_dim,
                )
    return _embedding_client


async def reset_embedding_client() -> None:
    """Сброс singleton (для тестов / переинициализации после смены settings)."""
    global _embedding_client
    async with _embedding_client_lock:
        if _embedding_client is not None:
            try:
                await _embedding_client.aclose()
            except Exception:
                logger.warning("ITS embedding client aclose failed", exc_info=True)
        _embedding_client = None


def set_embedding_client_for_testing(client: EmbeddingClient | None) -> None:
    """Прямая инъекция клиента для тестов (без async lock).

    Используется в test fixtures чтобы скормить MockEmbeddingClient без
    зависимости от Settings/env.
    """
    global _embedding_client
    _embedding_client = client


# ============================================================================
# Dispatch
# ============================================================================


def _parse_args(args: dict) -> tuple[str, int]:
    """Парсит args в (query, k). Raises ValueError при невалидных."""
    if not isinstance(args, dict):
        raise ValueError(f"args должен быть dict, получен {type(args).__name__}")

    query_raw = args.get("query")
    if not isinstance(query_raw, str) or not query_raw.strip():
        raise ValueError("Параметр 'query' обязателен и должен быть непустой строкой")

    k_raw = args.get("k", DEFAULT_SEARCH_K)
    try:
        k = int(k_raw)
    except (TypeError, ValueError):
        raise ValueError(f"Параметр 'k' должен быть integer, получено {k_raw!r}")
    if k < 1:
        raise ValueError(f"k должен быть >= 1, получено {k}")
    if k > _MAX_K:
        k = _MAX_K  # cap, не raise — модель могла случайно запросить много

    return query_raw.strip(), k


def _format_results_for_llm(hits: list) -> dict:
    """Готовит JSON-friendly dict с результатами для tool_content в LLM history.

    Формат:
    {
      "results": [
        {"citation": "std396: Title (раздел 1.)", "category": "std",
         "source_path": "std/396.md", "content": "..."},
         ...
      ],
      "total": N,
    }

    Поле `distance` НЕ возвращаем модели — оно про vector math, не про
    смысл. Модель ориентируется на порядок (первый = ближайший) и
    контент.
    """
    if not hits:
        return {"results": [], "total": 0}
    formatted = []
    for hit in hits:
        formatted.append({
            "citation": hit.to_citation(),
            "category": hit.category,
            "source_path": hit.source_path,
            "content": hit.content,
        })
    return {"results": formatted, "total": len(formatted)}


async def dispatch_its_tool(
    db: aiosqlite.Connection,
    settings: Settings,
    name: str,
    args: dict,
) -> tuple[bool, Any, str | None]:
    """Single entry-point для loop.py.

    Args:
        db: aiosqlite connection (init_vector_store должен быть применён —
            обычно через index_its_corpus до первого search)
        settings: текущие Settings (для embedding client)
        name: имя tool — обязан быть search_its (caller проверил is_its_tool)
        args: args от LLM

    Returns:
        (ok, result_dict_or_None, error_str_or_None)
        - ok=True: result содержит {"results": [...], "total": N}
        - ok=False: error содержит human-readable причину
    """
    if name != SEARCH_ITS_TOOL_NAME:
        return False, None, f"Неизвестный ITS tool: {name}"

    try:
        query, k = _parse_args(args)
    except ValueError as exc:
        return False, None, str(exc)

    try:
        client = await get_embedding_client(settings)
    except EmbeddingError as exc:
        logger.warning("ITS tool dispatch: client init failed: %s", exc)
        return False, None, f"ITS RAG не настроен: {exc}"

    try:
        hits = await search_its(db, client, query, k=k)
    except ITSSearchError as exc:
        logger.warning("ITS search failed: %s", exc)
        return False, None, f"ITS search ошибка: {exc}"

    return True, _format_results_for_llm(hits), None
