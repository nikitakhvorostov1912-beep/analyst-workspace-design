"use client";

import { useState } from "react";
import { BookMarked, Boxes, ChevronDown, ChevronRight, Database, type LucideIcon } from "lucide-react";

import { deriveAnswerSources, SOURCE_LABEL, type AnswerSource } from "@/lib/answer-sources";
import { summarizeToolCall } from "@/lib/tool-summary";
import { formatDuration } from "@/lib/format-duration";
import type { ToolCallRecord } from "@/lib/types";

/**
 * «Грунт ответа» (redesign 2.0 §3.3, лечит F-02 · critical) — провенанс первым
 * классом. Поглощает прежний крошечный ярлык `AnswerSources`.
 *
 * Две части:
 *  1. Полоса «Грунт» — всегда видна, если были запросы: счётчик + иконки
 *     источников (База/Типовая/ИТС) + кнопка «показать».
 *  2. Раскрытие — сам запрос к 1С (на --code-bg) + длительность + итог,
 *     в один клик у ответа, а не в подвале трейса.
 */

const SOURCE_ICON: Record<AnswerSource, LucideIcon> = {
  база: Database,
  типовая: Boxes,
  итс: BookMarked,
};

const INTERNAL = ["memory_", "todo_", "clarify"];

/** Грунт-запрос = обращение к источнику знаний (не служебный memory/todo/clarify). */
function isGrounding(name: string): boolean {
  const n = (name ?? "").toLowerCase().trim();
  if (!n) return false;
  return !INTERNAL.some((p) => n.startsWith(p));
}

function pluralQuery(n: number): string {
  const m10 = n % 10;
  const m100 = n % 100;
  if (m100 >= 11 && m100 <= 14) return "запросов";
  if (m10 === 1) return "запрос";
  if (m10 >= 2 && m10 <= 4) return "запроса";
  return "запросов";
}

/** Извлекает читаемый текст запроса для раскрытия (или null если нечего показать). */
function extractQuery(tc: ToolCallRecord): string | null {
  const a = (tc.args ?? {}) as Record<string, unknown>;
  for (const key of ["query", "sql", "code", "bsl"]) {
    const v = a[key];
    if (typeof v === "string" && v.trim()) return v.trim();
  }
  const keys = Object.keys(a);
  if (keys.length === 0) return null;
  try {
    return JSON.stringify(a, null, 2);
  } catch {
    return null;
  }
}

export function AnswerProvenance({
  toolCalls,
}: {
  toolCalls: ReadonlyArray<ToolCallRecord>;
}) {
  const [open, setOpen] = useState(false);
  const grounding = toolCalls.filter((tc) => isGrounding(tc.name ?? ""));
  if (grounding.length === 0) return null;

  const sources = deriveAnswerSources(toolCalls);
  const n = grounding.length;

  return (
    <div className="mb-2" data-testid="answer-provenance">
      {/* Полоса «Грунт» */}
      <div
        className="flex items-center gap-2 rounded-[8px] border px-2.5 py-2"
        style={{
          background: "var(--accent-08)",
          borderColor: "var(--accent-20)",
        }}
      >
        <span
          className="h-1.5 w-1.5 rounded-full bg-[var(--accent)] flex-none"
          aria-hidden="true"
        />
        <span className="text-[12.5px] text-[var(--fg-1)]">
          Грунт: {n} {pluralQuery(n)}
        </span>

        {/* Иконки источников */}
        {sources.length > 0 && (
          <span className="flex items-center gap-1.5 ml-1">
            {sources.map((s) => {
              const Icon = SOURCE_ICON[s];
              return (
                <span
                  key={s}
                  className="inline-flex items-center gap-1 text-[11px] text-[var(--fg-2)]"
                  title={SOURCE_LABEL[s]}
                >
                  <Icon className="h-3 w-3 text-[var(--accent)]" />
                  {SOURCE_LABEL[s]}
                </span>
              );
            })}
          </span>
        )}

        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          data-testid="provenance-toggle"
          className="ml-auto inline-flex items-center gap-1 text-[11px] text-[var(--accent)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] focus-visible:ring-offset-1 rounded-sm"
        >
          {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
          {open ? "скрыть" : "показать"}
        </button>
      </div>

      {/* Раскрытие — сами запросы к источникам */}
      {open && (
        <div className="mt-1.5 space-y-1.5" data-testid="provenance-details">
          {grounding.map((tc, i) => {
            const s = summarizeToolCall(tc);
            const ok = tc.ok !== false;
            const query = extractQuery(tc);
            return (
              <div
                key={tc.id ?? i}
                className="rounded-md border border-[var(--bd-1)] overflow-hidden"
              >
                <div className="flex items-baseline gap-2 px-3 py-1.5 bg-[var(--bg-2)] text-[12px]">
                  <span className="font-medium text-[var(--fg-1)] break-words">{s.title}</span>
                  <span
                    className={ok ? "text-[var(--success)]" : "text-[var(--error)]"}
                  >
                    · {s.result}
                  </span>
                  {tc.duration_ms != null && (
                    <span
                      className="ml-auto tabular-nums text-[10.5px] text-[var(--fg-3)] flex-none"
                      style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
                    >
                      {formatDuration(tc.duration_ms)}
                    </span>
                  )}
                </div>
                {query && (
                  <pre
                    className="px-3 py-2 bg-[var(--code-bg)] text-[var(--code-fg)] text-[11px] leading-relaxed overflow-x-auto whitespace-pre-wrap break-words m-0"
                    style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
                  >
                    {query.length > 1200 ? `${query.slice(0, 1200)}…` : query}
                  </pre>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
