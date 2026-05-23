"use client";

import type { ComponentType } from "react";
import { BookOpen, Check, Cog, PenLine, Search } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * StreamingStages — pipeline-style визуализация этапов LLM call.
 *
 * Phase 11.4 + REM-5 (2026-05-24): единственный рендерер streaming pipeline'а.
 * Старый StreamingIndicator (одно-строчный inline label) удалён в Sprint 01;
 * AssistantMessage всегда использует этот компонент.
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

// W3.2 (2026-05-22): маппинг snake_case tool_name → user-friendly русские
// фразы. Соответствует CLAUDE.md принципу «аналитик НЕ знает про
// get_metadata / execute_query / get_event_log — это работа LLM». Раньше
// в UI светилось `execute_query` — нарушение этого принципа.
const TOOL_LABELS: Record<string, string> = {
  execute_query: "Выполняю запрос",
  execute_code: "Выполняю код 1С",
  get_metadata: "Читаю структуру",
  get_object_by_link: "Читаю объект",
  get_link_of_object: "Получаю ссылку",
  get_event_log: "Читаю журнал",
  find_references_to_object: "Ищу ссылки",
  get_access_rights: "Проверяю права",
  get_bsl_syntax_help: "Справка BSL",
  submit_for_deanonymization: "Раскрываю значения",
  // bsl-context aux MCP (Sprint 1 Hermes)
  search: "Ищу в справочнике",
  info: "Получаю детали типа",
  getMember: "Читаю метод",
  getMembers: "Список методов",
  getConstructors: "Конструкторы",
  // Memory / Learning internal tools (Hermes)
  memory_read: "Читаю память",
  memory_write: "Запоминаю",
  memory_list: "Список записей памяти",
  clarify_question: "Уточняю вопрос",
};

function formatToolLabel(toolName: string | undefined): string {
  if (!toolName) return "";
  return TOOL_LABELS[toolName] ?? toolName;
}

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
          <span
            key={`stage-${i}`}
            className="inline-flex items-center gap-1"
            style={{
              animation: `fade-up 280ms ${i * 80}ms var(--ease, cubic-bezier(0.4,0,0.2,1)) both`,
            }}
          >
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
                    <span className="text-[var(--fg-1)]">
                      {formatToolLabel(s.tool)}
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
