/**
 * Syntax highlighting через prismjs.
 * Импортируется только здесь — компоненты НЕ импортируют prismjs напрямую.
 */

import Prism from "prismjs";
import "prismjs/components/prism-sql";
import "prismjs/components/prism-json";

import { bslGrammar } from "./bsl-grammar";

// Регистрируем BSL grammar один раз
if (!Prism.languages.bsl) {
  Prism.languages.bsl = bslGrammar;
}

/** Экранирует HTML специальные символы. */
function escapeHtml(str: string): string {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#x27;");
}

/**
 * Подсвечивает код через prismjs.
 *
 * @param code  - исходный код
 * @param language - язык: bsl | sql | json | text
 * @returns HTML-строка с token spans (safe для dangerouslySetInnerHTML)
 */
export function highlight(code: string, language: "bsl" | "sql" | "json" | "text"): string {
  if (language === "text") {
    return escapeHtml(code);
  }

  const grammar = Prism.languages[language];
  if (!grammar) {
    return escapeHtml(code);
  }

  return Prism.highlight(code, grammar, language);
}
