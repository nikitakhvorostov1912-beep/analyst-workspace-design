/**
 * Выводит, из каких «источников знаний» собран ответ, по именам вызванных
 * инструментов. Человеческий ярлык поверх технической трассировки —
 * пользователь видит, чем grounded ответ (доверие + обучение модели работы).
 *
 *   buddy.* / search_its / search_bsp        → ИТС (методики, Напарник)
 *   *_typical* / compare_with_typical        → Типовая (граф + карточки)
 *   прочие MCP-инструменты (get_metadata…)   → Ваша база (живая 1С)
 *   memory_* / todo_* / clarify_*            → не источник (служебные)
 */

export type AnswerSource = "база" | "типовая" | "итс";

const TYPICAL_PREFIXES = [
  "list_typical",
  "search_typical",
  "explain_typical",
  "trace_typical",
  "compare_with_typical",
];

const INTERNAL_PREFIXES = ["memory_", "todo_", "clarify"];

export function deriveAnswerSources(
  toolCalls: ReadonlyArray<{ name?: string }>,
): AnswerSource[] {
  const found = new Set<AnswerSource>();
  for (const tc of toolCalls) {
    const n = (tc.name ?? "").toLowerCase().trim();
    if (!n) continue;
    if (INTERNAL_PREFIXES.some((p) => n.startsWith(p))) continue;
    if (n.startsWith("buddy.") || n === "search_its" || n === "search_bsp") {
      found.add("итс");
    } else if (TYPICAL_PREFIXES.some((p) => n.startsWith(p))) {
      found.add("типовая");
    } else {
      found.add("база");
    }
  }
  // Стабильный порядок: база → типовая → ИТС
  const order: AnswerSource[] = ["база", "типовая", "итс"];
  return order.filter((s) => found.has(s));
}

export const SOURCE_LABEL: Record<AnswerSource, string> = {
  база: "Ваша база",
  типовая: "Типовая",
  итс: "ИТС · Напарник",
};
