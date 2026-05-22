"""ResultSizeGate (P2.2, 2026-05-23) — защита от 100k-row crash'ей.

Проблема (см. IDEAS-ADDENDUM-2026-05-21 §P0-3): MCP `execute_query` может
вернуть произвольное количество строк. На запрос «дай все заказы за год»
к крупному клиенту приходит 50 MB JSON. Это:

- ломает LLM (контекст переполнен, модель отказывает или жжёт деньги впустую)
- вешает frontend (React пытается отрендерить 100k row'ов сразу)

Решение — двухстороннее ограничение:

1. **Для LLM**: первые `MAX_ROWS_FOR_LLM=500` строк попадают в messages,
   остальное заменяется маркером «truncated for prompt»
2. **Для UI**: те же первые 500 строк отправляются в TableCard payload,
   но с флагом `truncated=true` и `total_available` — UI показывает баннер
   «Показаны первые 500 из N. Скачать CSV (полный набор)»

Что мы НЕ делаем (out of scope):
- Persistent storage полного result'а — уже есть `tool_result_storage.py`
  (D7 Sprint 5), которое сохраняет outputs > 50KB на диск
- Пагинированный load-more endpoint — backlog (P4 не критичен для v1.3.0)
- Real-time streaming row'ов — overkill для аналитического случая
"""

from __future__ import annotations

from typing import Any

# Лимиты — настроены под нормальный аналитический use case.
# 500 строк позволяет LLM сделать содержательный анализ (топ-10, тренды),
# при этом payload остаётся в разумных границах (~50-100 KB JSON).
MAX_ROWS_FOR_LLM: int = 500

# Какие tool'ы возвращают rows-структуру, к которой применим gate.
# get_event_log возвращает entries, не rows — но логика аналогична.
_ROW_BEARING_TOOLS: frozenset[str] = frozenset({"execute_query"})


def apply_row_gate(
    tool_name: str,
    tool_result: Any,
    max_rows: int = MAX_ROWS_FOR_LLM,
) -> tuple[Any, dict[str, Any]]:
    """Применяет row-level cap к большим results.

    Возвращает (capped_result, gate_info).

    `gate_info` — словарь с метаданными:
        - applied: bool — был ли cap применён
        - original_rows: int — сколько строк было до cap
        - kept_rows: int — сколько строк осталось
        - truncated: bool — flag для UI

    Если tool не row-bearing или result не имеет понятной row-структуры,
    возвращаем неизменённый result с `applied=False`.
    """
    if tool_name not in _ROW_BEARING_TOOLS:
        return tool_result, {"applied": False}

    if not isinstance(tool_result, dict):
        return tool_result, {"applied": False}

    rows = tool_result.get("rows")
    if not isinstance(rows, list):
        return tool_result, {"applied": False}

    original = len(rows)
    if original <= max_rows:
        return tool_result, {
            "applied": False,
            "original_rows": original,
            "kept_rows": original,
            "truncated": False,
        }

    # Делаем shallow copy чтобы не мутировать original (он ещё попадает в
    # accumulated_tool_calls для persistence).
    capped = dict(tool_result)
    capped["rows"] = rows[:max_rows]
    capped["_result_gate"] = {
        "truncated": True,
        "total_rows": original,
        "kept_rows": max_rows,
        "reason": f"result-gate: shown {max_rows} of {original}",
    }

    gate_info = {
        "applied": True,
        "original_rows": original,
        "kept_rows": max_rows,
        "truncated": True,
    }
    return capped, gate_info


def build_llm_summary_for_truncated(
    tool_name: str,
    gate_info: dict[str, Any],
) -> str:
    """Строка которая дописывается к tool_result_content для LLM.

    LLM должна знать что данные неполные, чтобы не сочинять выводы
    «всего 500 строк». Текст добавляется к json-payload tool message.
    """
    if not gate_info.get("applied"):
        return ""

    original = gate_info.get("original_rows", 0)
    kept = gate_info.get("kept_rows", 0)
    return (
        f"\n\n[ResultSizeGate: показаны первые {kept} строк из {original}. "
        "Если пользователю нужен полный набор — посоветуй скачать CSV "
        "через UI (карточка таблицы → кнопка «Скачать CSV») или "
        "сузить запрос (WHERE, LIMIT, временной диапазон).]"
    )
