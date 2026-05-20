"""Message sanitization — защита payload отправляемого в LLM.

Sprint 2 (Hermes E6): починка сообщений перед отправкой.

Что чиним:
1. Surrogate code points (lone halves) — UnicodeEncodeError при сериализации в JSON.
2. NUL-байты и control characters (кроме \\n \\t \\r) — некоторые LLM ругаются.
3. Tool_call.arguments — заполняем '{}' если пусто (некоторые модели возвращают
   '' или None, что валит pydantic-схему OpenAI).
4. Reasoning-only assistant messages — если content=None и tool_calls=[] и
   reasoning_content присутствует — merge'ем в content (иначе OpenAI API
   жалуется на "empty assistant turn").

Что НЕ чиним:
- Image strip — у нас vision auto-switch уже работает в loop.py.
- JSON content repair — наши tool results — это уже Python dict, а не строки от LLM.
"""

from __future__ import annotations

import json
import re
from typing import Any


# Surrogate pairs: D800-DFFF — половинки UTF-16 которые встречаются как одиночные
# в строках после некоторых стриминговых десериализаций. Превращаем в '?'.
_SURROGATE_RE = re.compile(r"[\ud800-\udfff]")

# Control characters кроме допустимых (TAB \t = 9, LF \n = 10, CR \r = 13).
# Удаляем NUL (0) и прочие 1-8, 11, 12, 14-31, 127.
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize_text(text: str) -> str:
    """Чистим строку от surrogate halves и control chars."""
    if not text:
        return text
    cleaned = _SURROGATE_RE.sub("?", text)
    cleaned = _CONTROL_RE.sub("", cleaned)
    return cleaned


def sanitize_tool_call_arguments(arguments: Any) -> str:
    """Превращает любой ввод в валидную JSON-строку.

    - None / '' → '{}'.
    - dict → json.dumps.
    - str — пытаемся распарсить и пере-сериализовать; если не парсится — оставляем,
      но всё равно прогоняем через sanitize_text для surrogate cleanup.
    """
    if arguments is None or arguments == "":
        return "{}"
    if isinstance(arguments, dict):
        return json.dumps(arguments, ensure_ascii=False)
    if isinstance(arguments, str):
        cleaned = sanitize_text(arguments)
        try:
            parsed = json.loads(cleaned)
            return json.dumps(parsed, ensure_ascii=False)
        except (json.JSONDecodeError, ValueError):
            return cleaned
    # Fallback — других типов не ждём, но не падаем.
    return json.dumps(arguments, ensure_ascii=False, default=str)


def sanitize_message(msg: dict[str, Any]) -> dict[str, Any]:
    """Чистим одно сообщение (user / assistant / tool / system).

    Возвращает НОВЫЙ dict (immutability). Не мутирует вход.
    """
    out: dict[str, Any] = dict(msg)
    content = out.get("content")

    # content: str — sanitize text
    if isinstance(content, str):
        out["content"] = sanitize_text(content)
    # content: list[dict] — multimodal parts (text + image_url). Чистим text-парты.
    elif isinstance(content, list):
        new_parts = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                p = dict(part)
                if isinstance(p.get("text"), str):
                    p["text"] = sanitize_text(p["text"])
                new_parts.append(p)
            else:
                new_parts.append(part)
        out["content"] = new_parts

    # tool_calls — чистим arguments.
    tool_calls = out.get("tool_calls")
    if isinstance(tool_calls, list):
        new_tool_calls = []
        for tc in tool_calls:
            new_tc = dict(tc)
            fn = dict(new_tc.get("function", {}))
            if "arguments" in fn:
                fn["arguments"] = sanitize_tool_call_arguments(fn["arguments"])
            new_tc["function"] = fn
            new_tool_calls.append(new_tc)
        out["tool_calls"] = new_tool_calls

    # Reasoning-only assistant message — fix: дублируем reasoning в content
    # если content пустой и tool_calls тоже отсутствуют.
    if (
        out.get("role") == "assistant"
        and not out.get("content")
        and not out.get("tool_calls")
        and isinstance(out.get("reasoning_content"), str)
        and out["reasoning_content"].strip()
    ):
        # OpenAI API не любит assistant turn с пустым content+tool_calls.
        # Подсовываем хотя бы пустую строку (или короткий fallback).
        out["content"] = ""

    return out


def sanitize_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Применяет sanitize_message ко всему списку. Возвращает новый список."""
    return [sanitize_message(m) for m in messages]


def repair_message_sequence(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Удаляет невалидные orphan tool messages.

    OpenAI требует: каждое сообщение role=tool ДОЛЖНО следовать после
    assistant с соответствующим tool_call_id. Если в истории остался
    осиротевший tool (например, после ручной редакции), API вернёт 400.

    Эта функция выкидывает tool message чей tool_call_id не присутствует
    ни в одном предыдущем assistant.tool_calls.
    """
    seen_tool_ids: set[str] = set()
    out: list[dict[str, Any]] = []
    for msg in messages:
        role = msg.get("role")
        if role == "assistant":
            for tc in msg.get("tool_calls") or []:
                tid = tc.get("id")
                if isinstance(tid, str) and tid:
                    seen_tool_ids.add(tid)
            out.append(msg)
        elif role == "tool":
            tcid = msg.get("tool_call_id")
            if isinstance(tcid, str) and tcid in seen_tool_ids:
                out.append(msg)
            # иначе — выбрасываем, это orphan
        else:
            out.append(msg)
    return out
