"use client";

import type { ComponentType } from "react";
import { BookOpen, Check, Cog, PenLine, Search } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * StreamingStages — pipeline-style визуализация этапов LLM call.
 *
 * Phase 11.4 prep — компонент готов, интеграция с useChatStream идёт отдельно
 * (StreamingIndicator пока остаётся, переключение через AssistantMessage в
 * следующем заходе).
 *
 * Маппинг SSE-событий → Stage[] делает caller (useChatStream / AssistantMessage):
 *   - status="thinking" → { kind: "analyzing" }
 *   - status="learn_lookup" (Phase 10) → { kind: "learn" }
 *   - tool_call.start → { kind: "tool", tool: "execute_query" }
 *   - tool_call.end → { kind: "tool_done", doneIn: 123 }
 *   - status="formatting" → { kind: "finalizing" }
 *
 * activeIndex показывает на текущую активную стадию. Все < activeIndex считаются
 * завершёнными (Check icon, success tone), > activeIndex — будущими (dim).
 */

export type StageKind =
  | "analyzing"
  | "learn"
  | "tool"
  | "tool_done"
  | "finalizing";

export interface Stage {
  kind: StageKind;
  tool?: string;
  doneIn?: number;
}

interface StreamingStagesProps {
  stages: Stage[];
  activeIndex: number;
  className?: string;
}

interface StageMeta {
  Icon: ComponentType<{ className?: string }>;
  label: string;
  tone: "muted" | "accent" | "success";
}

const STAGE_META: Record<StageKind, StageMeta> = {
  analyzing: { Icon: Search, label: "Анализирую", tone: "muted" },
  learn: { Icon: BookOpen, label: "Ищу прошлые ответы", tone: "accent" },
  tool: { Icon: Cog, label: "Вызываю", tone: "accent" },
  tool_done: { Icon: Check, label: "Получил данные", tone: "success" },
  finalizing: { Icon: PenLine, label: "Формирую ответ", tone: "accent" },
};

const TONE_BG: Record<StageMeta["tone"], string> = {
  muted: "bg-transparent text-[var(--fg-2)]",
  accent: "bg-[var(--accent-08)] text-[var(--accent)]",
  success: "bg-[var(--success-12)] text-[var(--success)]",
};

export function StreamingStages({
  stages,
  activeIndex,
  className,
}: StreamingStagesProps) {
  if (stages.length === 0) return null;

  return (
    <div
      data-testid="streaming-stages"
      data-active-index={activeIndex}
      className={cn(
        "inline-flex flex-wrap items-center gap-1 px-3 py-2 rounded-lg bg-[var(--bg-1)] border border-[var(--bd-2)] text-xs animate-fade-up",
        className,
      )}
      role="status"
      aria-live="polite"
    >
      {stages.map((s, i) => {
        const meta = STAGE_META[s.kind];
        const isActive = i === activeIndex;
        const isDone = i < activeIndex;
        const Icon = isDone ? Check : meta.Icon;
        const toneClass = isDone
          ? TONE_BG.success
          : isActive
            ? TONE_BG[meta.tone]
            : "bg-transparent text-[var(--fg-4)]";

        return (
          <span key={`stage-${i}`} className="inline-flex items-center gap-1">
            {i > 0 && (
              <span
                className={cn(
                  "text-[12px]",
                  i <= activeIndex
                    ? "text-[var(--bd-3)]"
                    : "text-[var(--bd-2)]",
                )}
                aria-hidden="true"
              >
                →
              </span>
            )}
            <span
              data-stage-kind={s.kind}
              data-stage-state={isDone ? "done" : isActive ? "active" : "future"}
              className={cn(
                "inline-flex items-center gap-1 px-1.5 py-0.5 rounded transition-all duration-normal ease-design-ease",
                toneClass,
                i > activeIndex && "opacity-45",
              )}
            >
              <span
                className={cn(
                  "inline-flex",
                  isActive && s.kind === "tool" && "animate-spin",
                )}
              >
                <Icon className="h-3 w-3" />
              </span>
              {s.kind === "tool" ? (
                <>
                  <span>{meta.label}</span>
                  {s.tool && (
                    <span className="font-mono text-[var(--fg-1)]">
                      {s.tool}
                    </span>
                  )}
                  {isActive && (
                    <span
                      className="inline-block h-1.5 w-1.5 rounded-full bg-current animate-blink"
                      aria-hidden="true"
                    />
                  )}
                </>
              ) : s.kind === "tool_done" ? (
                <span>
                  {meta.label}
                  {typeof s.doneIn === "number" && ` (${s.doneIn}ms)`}
                </span>
              ) : (
                <span>
                  {meta.label}
                  {isActive ? "…" : ""}
                </span>
              )}
            </span>
          </span>
        );
      })}
    </div>
  );
}
