import type { ToolCallRecord } from "./types";

/**
 * Sprint 03 (handoff E · TraceSummary): человекочитаемые сводки tool calls.
 *
 * `ToolTrace.tsx` показывает чипы с именами инструментов (`execute_query`,
 * `get_metadata`, …). Для расширенного режима — нужна вторая, человекочитаемая
 * формулировка: «Запрос к 1С — 24 записи · 380 мс». Это убирает «технический
 * шок» и помогает аналитику сразу понять что именно сделала модель.
 *
 * Источник tool names — `mcp-tool-descriptions.ts` (есть ключи всех 10 1С MCP
 * tools + 5 bsl-context + memory_/todo_/clarify_question).
 */

export interface ToolCallSummary {
  /** Что сделал инструмент — короткая фраза с глаголом и предметом */
  title: string;
  /** Что вернул — итог (число записей, статус, размер) */
  result: string;
}

function plural(n: number, one: string, few: string, many: string): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod100 >= 11 && mod100 <= 14) return many;
  if (mod10 === 1) return one;
  if (mod10 >= 2 && mod10 <= 4) return few;
  return many;
}

function rowCount(result: unknown): number {
  if (Array.isArray(result)) return result.length;
  if (result && typeof result === "object") {
    const rows = (result as { rows?: unknown }).rows;
    if (Array.isArray(rows)) return rows.length;
    const data = (result as { data?: unknown }).data;
    if (Array.isArray(data)) return data.length;
  }
  return 0;
}

function trimSnippet(value: string, max: number): string {
  const trimmed = value.trim().replace(/\s+/g, " ");
  if (trimmed.length <= max) return trimmed;
  return `${trimmed.slice(0, max - 1)}…`;
}

function pickArg(args: Record<string, unknown> | undefined, ...keys: string[]): string {
  if (!args) return "";
  for (const key of keys) {
    const value = args[key];
    if (typeof value === "string" && value.trim()) return value;
    if (typeof value === "number") return String(value);
  }
  return "";
}

/**
 * Возвращает human-readable summary для tool call.
 *
 * Покрывает все инструменты из `mcp-tool-descriptions.ts` + memory_/todo_/clarify.
 * Для незнакомых имён — fallback на имя инструмента + статус.
 */
export function summarizeToolCall(call: ToolCallRecord): ToolCallSummary {
  const { name, args, result } = call;
  const ok = call.ok !== false;

  switch (name) {
    case "execute_query": {
      const q = trimSnippet(pickArg(args, "query", "sql"), 60);
      const count = rowCount(result);
      return {
        title: q ? `Запрос к 1С — «${q}»` : "Запрос к 1С",
        result: ok
          ? count > 0
            ? `${count} ${plural(count, "запись", "записи", "записей")}`
            : "пусто"
          : "ошибка запроса",
      };
    }

    case "execute_code": {
      const code = trimSnippet(pickArg(args, "code", "bsl"), 50);
      return {
        title: code ? `Код BSL — «${code}»` : "Код BSL",
        result: ok ? "выполнено" : "ошибка выполнения",
      };
    }

    case "get_metadata": {
      const path = pickArg(args, "path", "object", "name");
      return {
        title: path ? `Структура — ${path}` : "Структура базы",
        result: ok ? "получено" : "не найдено",
      };
    }

    case "get_event_log": {
      const fromTs = pickArg(args, "from", "date_from", "start_date");
      const count = rowCount(result);
      return {
        title: fromTs ? `Журнал регистрации с ${fromTs}` : "Журнал регистрации",
        result: ok
          ? count > 0
            ? `${count} ${plural(count, "запись", "записи", "записей")}`
            : "записей нет"
          : "ошибка чтения",
      };
    }

    case "get_object_by_link": {
      const link = trimSnippet(pickArg(args, "link", "navigation_link", "url"), 40);
      return {
        title: link ? `Объект по ссылке — ${link}` : "Объект по ссылке",
        result: ok ? "найден" : "не найден",
      };
    }

    case "get_link_of_object": {
      const obj = pickArg(args, "object", "type", "name");
      return {
        title: obj ? `Ссылка на ${obj}` : "Ссылка на объект",
        result: ok ? "получена" : "не удалось",
      };
    }

    case "find_references_to_object": {
      const target = pickArg(args, "object", "name", "type");
      const count = rowCount(result);
      return {
        title: target ? `Где используется ${target}` : "Поиск ссылок",
        result: ok
          ? count > 0
            ? `${count} ${plural(count, "ссылка", "ссылки", "ссылок")}`
            : "не найдено"
          : "ошибка",
      };
    }

    case "get_access_rights": {
      const subj = pickArg(args, "user", "role", "subject");
      return {
        title: subj ? `Права — ${subj}` : "Проверка прав",
        result: ok ? "проверено" : "ошибка",
      };
    }

    case "get_bsl_syntax_help": {
      const symbol = pickArg(args, "name", "symbol", "query");
      return {
        title: symbol ? `Справка BSL — ${symbol}` : "Справка BSL",
        result: ok ? "получена" : "не найдена",
      };
    }

    case "submit_for_deanonymization": {
      const count = rowCount(result);
      return {
        title: "Восстановление маскированных значений",
        result: ok
          ? count > 0
            ? `${count} ${plural(count, "значение", "значения", "значений")}`
            : "выполнено"
          : "ошибка",
      };
    }

    case "get_screenshot":
      return {
        title: "Снимок формы 1С",
        result: ok ? "сделан" : "не удалось",
      };

    case "restart_1c_session":
      return {
        title: "Перезапуск сессии 1С",
        result: ok ? "выполнен" : "ошибка",
      };

    case "close_1c_session":
      return {
        title: "Закрытие сессии 1С",
        result: ok ? "выполнено" : "ошибка",
      };

    // bsl-context (справочник API платформы)
    case "search": {
      const q = pickArg(args, "query", "name");
      const count = rowCount(result);
      return {
        title: q ? `Поиск API — ${q}` : "Поиск по API платформы",
        result: ok
          ? `${count} ${plural(count, "совпадение", "совпадения", "совпадений")}`
          : "ошибка",
      };
    }
    case "info": {
      const subj = pickArg(args, "name", "symbol");
      return {
        title: subj ? `Описание API — ${subj}` : "Описание API",
        result: ok ? "получено" : "не найдено",
      };
    }
    case "getMember": {
      const type = pickArg(args, "type", "object");
      const member = pickArg(args, "member", "name");
      return {
        title: type && member ? `${type}.${member}` : "Член типа платформы",
        result: ok ? "получено" : "не найдено",
      };
    }
    case "getMembers": {
      const type = pickArg(args, "type", "name");
      const count = rowCount(result);
      return {
        title: type ? `Члены типа ${type}` : "Члены типа",
        result: ok
          ? `${count} ${plural(count, "член", "члена", "членов")}`
          : "ошибка",
      };
    }
    case "getConstructors": {
      const type = pickArg(args, "type", "name");
      const count = rowCount(result);
      return {
        title: type ? `Конструкторы ${type}` : "Конструкторы типа",
        result: ok
          ? `${count} ${plural(count, "вариант", "варианта", "вариантов")}`
          : "ошибка",
      };
    }

    // Внутренние tools (память, todo, clarify)
    case "memory_append":
      return {
        title: "Запись в память",
        result: ok ? "сохранено" : "ошибка",
      };
    case "memory_remove":
      return {
        title: "Удаление из памяти",
        result: ok ? "удалено" : "ошибка",
      };
    case "memory_list": {
      const count = rowCount(result);
      return {
        title: "Просмотр памяти",
        result: ok
          ? `${count} ${plural(count, "запись", "записи", "записей")}`
          : "ошибка",
      };
    }
    case "todo_add":
      return {
        title: "План — добавлен пункт",
        result: ok ? "добавлено" : "ошибка",
      };
    case "todo_complete":
      return {
        title: "План — пункт выполнен",
        result: ok ? "отмечено" : "ошибка",
      };
    case "todo_list": {
      const count = rowCount(result);
      return {
        title: "План работ",
        result: ok
          ? `${count} ${plural(count, "пункт", "пункта", "пунктов")}`
          : "ошибка",
      };
    }
    case "clarify_question": {
      const q = trimSnippet(pickArg(args, "question", "text"), 60);
      return {
        title: q ? `Уточнение — «${q}»` : "Запрос уточнения",
        result: ok ? "задан вопрос" : "ошибка",
      };
    }

    default:
      return {
        title: name,
        result: ok ? "выполнено" : "ошибка",
      };
  }
}
