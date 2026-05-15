/**
 * Утилиты для работы с anon-токенами: подсветка, извлечение.
 * Plan 04-01.
 */

import React from "react";

/** Regex для поиска anon-токенов вида [ORG-001], [INN-001] и т.д. */
export const ANON_TOKEN_RE =
  /\[(ORG|INN|PER|PHONE|EMAIL|ACCT|AGREE|FIO|DOC|ADDR)-\d+\]/g;

/**
 * Подсвечивает anon-токены в тексте: возвращает массив строк и React-элементов.
 *
 * Если передан `replacements` — токены заменяются на реальные значения
 * с зелёной рамкой вместо amber.
 *
 * @param text — исходный текст
 * @param replacements — опциональный маппинг {[TOKEN]: "real value"}
 * @returns массив строк и React-элементов
 */
export function highlightAnonTokens(
  text: string,
  replacements?: Record<string, string>,
): React.ReactNode[] {
  const result: React.ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  // Сбрасываем lastIndex перед использованием глобального regex
  ANON_TOKEN_RE.lastIndex = 0;

  // eslint-disable-next-line no-cond-assign
  while ((match = ANON_TOKEN_RE.exec(text)) !== null) {
    const tokenStart = match.index;
    const token = match[0];

    // Текст до токена
    if (tokenStart > lastIndex) {
      result.push(text.slice(lastIndex, tokenStart));
    }

    // Есть замена → показываем реальное значение с зелёной рамкой
    const realValue = replacements?.[token];
    if (realValue !== undefined) {
      result.push(
        React.createElement(
          "span",
          {
            key: `${token}-${tokenStart}`,
            className:
              "bg-emerald-500/10 border border-emerald-500/30 rounded px-1 font-mono text-xs",
            title: `Раскрыто: ${token}`,
          },
          realValue,
        ),
      );
    } else {
      // Токен не раскрыт — amber подсветка
      result.push(
        React.createElement(
          "span",
          {
            key: `${token}-${tokenStart}`,
            className:
              "bg-amber-500/10 border border-amber-500/30 rounded px-1 font-mono text-xs",
            title: token,
          },
          token,
        ),
      );
    }

    lastIndex = tokenStart + token.length;
  }

  // Остаток текста
  if (lastIndex < text.length) {
    result.push(text.slice(lastIndex));
  }

  return result.length > 0 ? result : [text];
}

/**
 * Рекурсивно обходит JSON-like структуру и извлекает уникальные anon-токены.
 *
 * @returns отсортированный массив уникальных токенов
 */
export function extractAnonTokens(value: unknown): string[] {
  const found = new Set<string>();

  function walk(val: unknown): void {
    if (val === null || val === undefined) return;
    if (typeof val === "string") {
      // Сбрасываем lastIndex перед использованием
      ANON_TOKEN_RE.lastIndex = 0;
      let m: RegExpExecArray | null;
      // eslint-disable-next-line no-cond-assign
      while ((m = ANON_TOKEN_RE.exec(val)) !== null) {
        found.add(m[0]);
      }
    } else if (Array.isArray(val)) {
      for (const item of val) {
        walk(item);
      }
    } else if (typeof val === "object") {
      for (const v of Object.values(val as Record<string, unknown>)) {
        walk(v);
      }
    }
  }

  walk(value);
  return Array.from(found).sort();
}
