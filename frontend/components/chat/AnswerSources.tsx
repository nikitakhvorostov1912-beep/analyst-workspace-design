"use client";

import { BookMarked, Boxes, Database } from "lucide-react";

import {
  deriveAnswerSources,
  SOURCE_LABEL,
  type AnswerSource,
} from "@/lib/answer-sources";

const ICON: Record<AnswerSource, typeof Database> = {
  база: Database,
  типовая: Boxes,
  итс: BookMarked,
};

/**
 * Ярлык-источник под ответом ассистента: какие из 3 источников знаний были
 * использованы (выводится по именам вызванных инструментов). Помогает
 * пользователю понять, откуда взялся ответ, не разворачивая трассировку.
 */
export function AnswerSources({
  toolCalls,
}: {
  toolCalls: ReadonlyArray<{ name?: string }>;
}) {
  const sources = deriveAnswerSources(toolCalls);
  if (sources.length === 0) return null;

  return (
    <div className="flex items-center gap-1.5 mb-1.5 flex-wrap" data-testid="answer-sources">
      <span className="text-[10px] uppercase tracking-[0.14em] text-[var(--fg-4)]">
        Источник:
      </span>
      {sources.map((s) => {
        const Icon = ICON[s];
        return (
          <span
            key={s}
            className="inline-flex items-center gap-1 rounded-full border border-[var(--bd-2)] bg-[var(--bg-2)] px-2 py-0.5 text-[10.5px] text-[var(--fg-2)]"
          >
            <Icon className="h-3 w-3 text-[var(--accent)]" />
            {SOURCE_LABEL[s]}
          </span>
        );
      })}
    </div>
  );
}
