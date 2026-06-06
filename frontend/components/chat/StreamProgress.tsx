"use client";

import { useEffect, useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { StreamingStages, type Stage, type StageKind } from "./StreamingStages";
import { getStreamStepsExpanded, setStreamStepsExpanded } from "@/lib/storage";

/**
 * StreamProgress — свёрнутый по умолчанию индикатор хода запроса.
 *
 *  • Свёрнут: дышащие точки (--accent, keyframe blink) + лейбл текущего этапа +
 *    живой таймер. Появляется мгновенно (caller рендерит пока isStreaming).
 *  • Развёрнут (по клику, запоминается в localStorage): детальный StreamingStages.
 *
 * Бренд: только --accent + keyframes blink/fade-up, без glow/gradient/glass.
 */

const COLLAPSED_LABEL: Record<StageKind, string> = {
  analyzing: "Анализирую",
  learn: "Ищу прошлые ответы",
  tool: "Выполняю запрос",
  tool_done: "Обрабатываю",
  finalizing: "Формирую ответ",
};

interface StreamProgressProps {
  stages: Stage[];
  activeIndex: number;
  /** Время старта стрима (Date.now()) для живого таймера; null — таймер скрыт. */
  startedAt: number | null;
}

export function StreamProgress({ stages, activeIndex, startedAt }: StreamProgressProps) {
  const [expanded, setExpanded] = useState<boolean>(() => getStreamStepsExpanded());
  const [elapsedMs, setElapsedMs] = useState<number>(0);

  useEffect(() => {
    if (startedAt === null) return;
    setElapsedMs(Date.now() - startedAt);
    const id = window.setInterval(() => {
      setElapsedMs(Date.now() - startedAt);
    }, 500);
    return () => window.clearInterval(id);
  }, [startedAt]);

  function toggle() {
    setExpanded((v) => {
      const next = !v;
      setStreamStepsExpanded(next);
      return next;
    });
  }

  const active = stages[activeIndex];
  const label = active ? COLLAPSED_LABEL[active.kind] : "Думаю";
  const seconds = startedAt !== null ? (elapsedMs / 1000).toFixed(1) : null;

  return (
    <div data-testid="stream-progress" className="mt-2 animate-fade-up">
      <button
        type="button"
        onClick={toggle}
        data-testid="stream-progress-toggle"
        aria-expanded={expanded}
        className="inline-flex items-center gap-2 h-8 px-2.5 rounded-md bg-[var(--bg-1)] border border-[var(--bd-2)] text-xs text-[var(--fg-2)] hover:border-[var(--bd-3)] transition-colors"
      >
        {/* Дышащие точки — --accent, keyframe blink со стаггером */}
        <span className="inline-flex items-center gap-0.5" aria-hidden="true">
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              className="inline-block h-1.5 w-1.5 rounded-full bg-[var(--accent)] animate-blink"
              style={{ animationDelay: `${i * 160}ms` }}
            />
          ))}
        </span>
        <span className="text-[var(--fg-1)]">{label}…</span>
        {seconds !== null && (
          <span
            data-testid="stream-progress-timer"
            className="tabular-nums text-[var(--fg-3)]"
            style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
          >
            {seconds}с
          </span>
        )}
        {expanded ? (
          <ChevronUp className="h-3.5 w-3.5 text-[var(--fg-3)]" />
        ) : (
          <ChevronDown className="h-3.5 w-3.5 text-[var(--fg-3)]" />
        )}
        <span className="sr-only">шаги</span>
      </button>

      {expanded && (
        <div className="mt-1.5">
          <StreamingStages stages={stages} activeIndex={activeIndex} />
        </div>
      )}
    </div>
  );
}
