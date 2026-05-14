"""Главный tool-calling loop: NL → LLM → MCP → LLM → done."""

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

import aiosqlite
import httpx

from app.clients.llm import LLMClient
from app.clients.mcp import MCPClient, MCPError
from app.models import ChatRequest
from app.orchestrator.cards import build_card_from_tool_result
from app.orchestrator.events import (
    CardEvent,
    DeltaEvent,
    DoneEvent,
    ErrorEvent,
    StatusEvent,
    ToolCallEvent,
    ToolResultEvent,
    format_sse,
)
from app.orchestrator.persistence import (
    ensure_session,
    lookup_mcp_endpoint,
    save_assistant_message,
    save_user_message,
    touch_session,
)

logger = logging.getLogger(__name__)

MAX_TOOL_ITERATIONS = 10
RETRY_DELAY_S = 0.2
TOOL_CONTENT_CAP = 50_000  # байт — cap для payload в LLM context

SYSTEM_PROMPT = (
    "Ты аналитик 1С. У тебя есть MCP-инструменты для работы с базой данных 1С. "
    "Отвечай по-русски, кратко и по делу. "
    "Для получения данных всегда используй инструменты — не придумывай данные. "
    "После получения результата инструмента дай краткий TL;DR на русском."
)


def _mcp_tools_to_openai(mcp_tools: list[dict]) -> list[dict]:
    """Конвертирует MCP-схемы инструментов в OpenAI function format."""
    result = []
    for tool in mcp_tools:
        result.append({
            "type": "function",
            "function": {
                "name": tool.get("name", ""),
                "description": tool.get("description", ""),
                "parameters": tool.get("inputSchema", {"type": "object", "properties": {}}),
            },
        })
    return result


def _cap_content(content: str) -> str:
    """Обрезает строку до TOOL_CONTENT_CAP с маркером."""
    if len(content) <= TOOL_CONTENT_CAP:
        return content
    return content[:TOOL_CONTENT_CAP] + "...truncated"


async def _call_tool_with_retry(
    mcp: MCPClient,
    name: str,
    args: dict,
) -> tuple[bool, Any, str | None]:
    """Вызывает MCP-инструмент с 1 retry на сетевые ошибки и 5xx.

    Returns:
        (ok, result, error_message)
    """
    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            result = await mcp.call_tool(name, args)
            return True, result, None
        except MCPError as e:
            # JSON-RPC ошибка — 0 retry
            return False, None, str(e)
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            if status < 500:
                # 4xx — 0 retry
                return False, None, f"HTTP {status}: {e}"
            last_exc = e
            if attempt == 0:
                await asyncio.sleep(RETRY_DELAY_S)
        except httpx.RequestError as e:
            # Сетевая ошибка — 1 retry
            last_exc = e
            if attempt == 0:
                await asyncio.sleep(RETRY_DELAY_S)
        except Exception as e:
            return False, None, f"Ошибка вызова инструмента: {e}"

    error_msg = f"Ошибка после повтора: {last_exc}"
    return False, None, error_msg


async def run_chat_loop(
    db: aiosqlite.Connection,
    request: ChatRequest,
    api_key: str,
    llm_endpoint: str,
    llm_model: str,
) -> AsyncIterator[str]:
    """Async-генератор SSE-событий: tool-calling loop.

    Yields:
        SSE-строки в формате event: <name>\\ndata: <json>\\n\\n
    """
    loop_start = time.monotonic()

    # Первый байт ≤ 500 мс (NFR-1) — до всех I/O операций
    yield format_sse("status", StatusEvent(stage="thinking"))

    # --- Инициализация ---
    try:
        session_id = await ensure_session(
            db, request.session_id, request.channel_id, request.message[:60]
        )
        await save_user_message(db, session_id, request.message)

        mcp_endpoint = await lookup_mcp_endpoint(db, request.channel_id)
    except Exception as exc:
        logger.exception("Ошибка инициализации loop")
        yield format_sse("error", ErrorEvent(message="Внутренняя ошибка", code="init_error"))
        return

    if mcp_endpoint is None:
        yield format_sse("error", ErrorEvent(
            message=f"Канал '{request.channel_id}' не найден. Настройте MCP-подключение.",
            code="unknown_channel",
        ))
        return

    # --- Получаем список инструментов ---
    try:
        mcp = MCPClient(mcp_endpoint)
        await mcp.initialize()
        mcp_tools = await mcp.list_tools()
        openai_tools = _mcp_tools_to_openai(mcp_tools)
    except Exception as exc:
        logger.exception("Ошибка инициализации MCP")
        yield format_sse("error", ErrorEvent(message="Ошибка подключения к 1С MCP", code="mcp_connect_error"))
        return

    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": request.message},
    ]

    accumulated_content = ""
    accumulated_tool_calls: list[dict] = []
    accumulated_cards: list[dict] = []

    try:
        for iteration in range(MAX_TOOL_ITERATIONS):
            yield format_sse("status", StatusEvent(stage="thinking"))

            # Накапливаем tool_calls из streaming chunks
            chunk_tool_calls: dict[int, dict] = {}
            chunk_content = ""
            finish_reason: str | None = None

            try:
                llm = LLMClient(endpoint=llm_endpoint, model=llm_model)
                try:
                    async for chunk in llm.stream_chat_completion(
                        messages=messages,
                        api_key=api_key,
                        tools=openai_tools if openai_tools else None,
                    ):
                        delta = chunk.get("delta", {})

                        # Накапливаем текстовый контент
                        content_piece = delta.get("content")
                        if content_piece:
                            chunk_content += content_piece
                            yield format_sse("delta", DeltaEvent(content=content_piece))

                        # Накапливаем tool_calls по index (arguments приходят частями)
                        tool_calls_delta = delta.get("tool_calls", [])
                        for tc in tool_calls_delta:
                            idx = tc.get("index", 0)
                            if idx not in chunk_tool_calls:
                                chunk_tool_calls[idx] = {
                                    "id": tc.get("id", ""),
                                    "name": tc.get("function", {}).get("name", ""),
                                    "arguments": "",
                                }
                            if tc.get("id"):
                                chunk_tool_calls[idx]["id"] = tc["id"]
                            fn = tc.get("function", {})
                            if fn.get("name"):
                                chunk_tool_calls[idx]["name"] = fn["name"]
                            if fn.get("arguments"):
                                chunk_tool_calls[idx]["arguments"] += fn["arguments"]

                        fr = chunk.get("finish_reason")
                        if fr:
                            finish_reason = fr
                finally:
                    await llm.aclose()
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if status < 500:
                    yield format_sse("error", ErrorEvent(
                        message=f"Ошибка LLM (HTTP {status})", code="llm_4xx"
                    ))
                    return
                # 5xx — пробуем ещё раз (простой retry через continue)
                logger.warning("LLM 5xx: %s", exc)
                yield format_sse("error", ErrorEvent(
                    message="Ошибка сервера LLM", code="llm_5xx"
                ))
                return
            except httpx.RequestError as exc:
                logger.warning("LLM network error: %s", exc)
                yield format_sse("error", ErrorEvent(
                    message="Сетевая ошибка при обращении к LLM", code="llm_network_error"
                ))
                return

            accumulated_content += chunk_content

            # Нет tool_calls — обычный финальный ответ
            if not chunk_tool_calls or finish_reason == "stop":
                break

            # Финализируем tool_calls: парсим JSON arguments
            finalized: list[dict] = []
            for idx in sorted(chunk_tool_calls.keys()):
                tc = chunk_tool_calls[idx]
                raw_args = tc.get("arguments", "{}")
                try:
                    args_dict = json.loads(raw_args) if raw_args.strip() else {}
                except json.JSONDecodeError:
                    args_dict = {}
                finalized.append({
                    "id": tc["id"],
                    "name": tc["name"],
                    "args": args_dict,
                })

            # Добавляем assistant-сообщение с tool_calls в историю
            assistant_tool_calls = [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": tc.get("arguments", "{}")},
                }
                for tc in chunk_tool_calls.values()
            ]
            messages.append({
                "role": "assistant",
                "content": chunk_content or None,
                "tool_calls": assistant_tool_calls,
            })

            # Вызываем каждый tool
            yield format_sse("status", StatusEvent(stage="calling_tool"))

            for tc in finalized:
                tool_id = tc["id"]
                tool_name = tc["name"]
                tool_args = tc["args"]

                yield format_sse("tool_call", ToolCallEvent(
                    id=tool_id, name=tool_name, args=tool_args
                ))

                start_ts = time.monotonic()
                ok, tool_result, tool_error = await _call_tool_with_retry(mcp, tool_name, tool_args)
                duration_ms = int((time.monotonic() - start_ts) * 1000)

                yield format_sse("tool_result", ToolResultEvent(
                    id=tool_id,
                    ok=ok,
                    result=tool_result if ok else None,
                    error=tool_error,
                    duration_ms=duration_ms,
                ))

                # Детектируем карточку
                if ok and tool_result is not None:
                    card = build_card_from_tool_result(tool_name, tool_args, tool_result)
                    if card is not None:
                        yield format_sse("card", CardEvent(type=card["type"], payload=card["payload"]))
                        accumulated_cards.append(card)

                # Сохраняем для последующей персистенции
                accumulated_tool_calls.append({
                    "id": tool_id,
                    "name": tool_name,
                    "args": tool_args,
                    "result": tool_result,
                    "error": tool_error,
                    "duration_ms": duration_ms,
                })

                # Добавляем tool-результат в историю для LLM
                tool_content = json.dumps(tool_result, ensure_ascii=False) if tool_result else (tool_error or "")
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_id,
                    "content": _cap_content(tool_content),
                })

            yield format_sse("status", StatusEvent(stage="formatting"))

        else:
            # Вышли по лимиту итераций
            yield format_sse("error", ErrorEvent(
                message="Превышен лимит вызовов tools (10)",
                code="tool_loop_limit",
            ))
            return

    except Exception as exc:
        logger.exception("Непредвиденная ошибка в tool-calling loop")
        yield format_sse("error", ErrorEvent(
            message="Внутренняя ошибка обработки запроса",
            code="internal_error",
        ))
        return
    finally:
        await mcp.aclose()

    # --- Сохраняем результат в БД ---
    total_duration_ms = int((time.monotonic() - loop_start) * 1000)
    try:
        message_id = await save_assistant_message(
            db,
            session_id,
            accumulated_content,
            accumulated_tool_calls,
            accumulated_cards,
            total_duration_ms,
        )
        await touch_session(db, session_id)
    except Exception:
        logger.exception("Ошибка сохранения assistant message")
        message_id = "unknown"

    yield format_sse("done", DoneEvent(
        message_id=message_id,
        total_duration_ms=total_duration_ms,
    ))
