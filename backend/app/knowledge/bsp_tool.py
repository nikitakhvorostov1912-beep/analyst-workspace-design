"""BSP Tool — `search_bsp` для LLM-orchestrator (M-K2.8).

Knowledge Foundation Phase 8 (LLM-обвязка): экспозит БСП RAG как
async-internal tool. Когда LLM получает вопрос про БСП API
(«методы для длительных операций», «безопасное хранилище паролей»,
«цифровая подпись из БСП»), она вызывает search_bsp вместо
блуждания по MCP get_metadata.

**Singleton embedding-клиента:**
- Переиспользуем `get_embedding_client` из its_tool — модель/dim
  общие, один vec0 покрывает оба корпуса (channel_id разный).
"""

from __future__ import annotations

import logging
from typing import Any

import aiosqlite

from app.config import Settings
from app.knowledge.bsp_search import (
    DEFAULT_SEARCH_K,
    BSPSearchError,
    search_bsp,
)
from app.knowledge.its_tool import get_embedding_client

logger = logging.getLogger(__name__)


SEARCH_BSP_TOOL_NAME = "search_bsp"


_MAX_K = 20


BSP_TOOL_SCHEMA: dict = {
    "type": "function",
    "function": {
        "name": SEARCH_BSP_TOOL_NAME,
        "description": (
            "Поиск по корпусу экспортных методов БСП (Библиотека "
            "Стандартных Подсистем, версии 3.1 и 3.2). Когда вызывать: "
            "вопросы про конкретные API БСП — «как запустить длительную "
            "операцию», «как сохранить пароль безопасно», «как подписать "
            "данные цифровой подписью», «какие методы у ДатыПериода». "
            "Возвращает топ-K методов с doc-комментарием + сигнатурой + "
            "куском body, цитата формата 'БСП 3.2 → "
            "ДлительныеОперации.ВыполнитьФункцию (Функция)'. "
            "НЕ вызывай для вопросов про общую методологию 1С — "
            "там search_its. НЕ вызывай для структуры или данных "
            "конкретной базы — там MCP-инструменты."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Естественноязыковой запрос. Примеры: "
                        "«запустить длительную операцию в фоне», "
                        "«сохранить пароль интеграции», "
                        "«проверить подключение к интернету»."
                    ),
                },
                "k": {
                    "type": "integer",
                    "description": (
                        f"Количество методов. По умолчанию {DEFAULT_SEARCH_K}, "
                        f"максимум {_MAX_K}. Бери минимум — большие списки "
                        "перегружают context."
                    ),
                    "minimum": 1,
                    "maximum": _MAX_K,
                },
                "version": {
                    "type": "string",
                    "description": (
                        "Фильтр по версии БСП ('3.1' или '3.2'). "
                        "По умолчанию — без фильтра, возвращаются методы "
                        "обеих версий (если индексированы). Указывай "
                        "только если знаешь версию БСП в базе клиента."
                    ),
                    "enum": ["3.1", "3.2"],
                },
            },
            "required": ["query"],
        },
    },
}


def is_bsp_tool(name: str) -> bool:
    return name == SEARCH_BSP_TOOL_NAME


def is_bsp_enabled(settings: Settings) -> bool:
    return settings.is_bsp_ready


def _parse_args(args: dict) -> tuple[str, int, str | None]:
    """Парсит args в (query, k, version_filter)."""
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
        k = _MAX_K

    version = args.get("version")
    if version is not None:
        if not isinstance(version, str) or version not in ("3.1", "3.2"):
            raise ValueError(
                f"Параметр 'version' должен быть '3.1' или '3.2', получено {version!r}"
            )

    return query_raw.strip(), k, version


def _format_results_for_llm(hits: list) -> dict:
    """JSON-friendly результат для tool_content."""
    if not hits:
        return {"results": [], "total": 0}
    formatted = []
    for hit in hits:
        formatted.append({
            "citation": hit.to_citation(),
            "full_name": hit.full_name,
            "method_kind": hit.method_kind,
            "version": hit.version,
            "source_path": hit.source_path,
            "signature": hit.signature,
            "doc_comment": hit.doc_comment,
            "content": hit.content,
        })
    return {"results": formatted, "total": len(formatted)}


async def dispatch_bsp_tool(
    db: aiosqlite.Connection,
    settings: Settings,
    name: str,
    args: dict,
) -> tuple[bool, Any, str | None]:
    """Single entry-point для loop.py.

    Returns:
        (ok, result_dict_or_None, error_str_or_None)
    """
    if name != SEARCH_BSP_TOOL_NAME:
        return False, None, f"Неизвестный BSP tool: {name}"

    try:
        query, k, version = _parse_args(args)
    except ValueError as exc:
        return False, None, str(exc)

    try:
        client = await get_embedding_client(settings)
    except Exception as exc:  # noqa: BLE001 — граница LLM-tool, любая ошибка → user message
        logger.warning("BSP tool: client init failed: %s", exc)
        return False, None, f"BSP RAG не настроен: {exc}"

    try:
        hits = await search_bsp(
            db, client, query, k=k, version_filter=version,
        )
    except BSPSearchError as exc:
        logger.warning("BSP search failed: %s", exc)
        return False, None, f"BSP search ошибка: {exc}"

    return True, _format_results_for_llm(hits), None
