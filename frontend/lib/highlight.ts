/**
 * Syntax highlighting через prismjs.
 * Импортируется только здесь — компоненты НЕ импортируют prismjs напрямую.
 *
 * W1.6 (2026-05-22): двойная защита от XSS:
 * 1) Prism v1.30 САМ encoded'ит выходные tokens через util.encode (HTML escape)
 * 2) DOMPurify санирует выход с whitelist'ом — оставляет только Prism-теги
 *    (<span>, <code> и class атрибуты).
 *
 * Untrusted-вектор: LLM возвращает code-блок с `</span><script>...` —
 * Prism может пропустить через ошибочную grammar regex. DOMPurify — second
 * layer of defense.
 */

import DOMPurify from "dompurify";
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

// DOMPurify config: разрешаем только Prism span-теги с class. Никаких script/
// iframe/onerror/style — даже если LLM протолкнёт их через сложную regex.
// KEEP_CONTENT=true означает что текст внутри strip'нутых тегов сохранится
// как plain text (а сам тег пропадёт).
const DOMPURIFY_CONFIG = {
  ALLOWED_TAGS: ["span", "code", "br"],
  ALLOWED_ATTR: ["class"],
  ALLOW_DATA_ATTR: false,
  KEEP_CONTENT: true,
};

/**
 * Подсвечивает код через prismjs + санирует через DOMPurify.
 *
 * @param code  - исходный код (untrusted, может содержать XSS-payload)
 * @param language - язык: bsl | sql | json | text
 * @returns HTML-строка с token spans, безопасная для dangerouslySetInnerHTML.
 */
export function highlight(code: string, language: "bsl" | "sql" | "json" | "text"): string {
  if (language === "text") {
    return escapeHtml(code);
  }

  const grammar = Prism.languages[language];
  if (!grammar) {
    return escapeHtml(code);
  }

  const prismHtml = Prism.highlight(code, grammar, language);

  // SSR-guard: DOMPurify требует window. На сервере возвращаем escape — Prism
  // output почти всегда безопасен, но без strict sanitize в SSR пути.
  if (typeof window === "undefined") {
    return prismHtml;
  }

  return DOMPurify.sanitize(prismHtml, DOMPURIFY_CONFIG);
}
