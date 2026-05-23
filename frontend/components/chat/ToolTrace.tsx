"use client";
import { useState } from "react";
import { ChevronRight, ChevronDown, Wrench, AlertTriangle, CheckCircle2 } from "lucide-react";
import { formatDuration } from "@/lib/format-duration";
import { cn } from "@/lib/utils";
import { TraceSummary } from "./TraceSummary";
import type { ToolCallRecord } from "@/lib/types";

function pluralTools(n: number): string {
  if (n === 1) return "инструмент";
  if (n >= 2 && n <= 4) return "инструмента";
  return "инструментов";
}

/**
 * Категория инструмента — для визуального code мини-chip'а в ToolTrace.
 *
 * - mcp: реальные 1С MCP tools (execute_query, get_metadata, …) — orange
 * - memory: memory_append / memory_remove — blue
 * - todo: todo_add / todo_complete / todo_list — green
 * - clarify: clarify_question — purple (требует диалога)
 */
type ToolCategory = "mcp" | "memory" | "todo" | "clarify";

function getToolCategory(name: string): ToolCategory {
  if (name.startsWith("memory_")) return "memory";
  if (name.startsWith("todo_")) return "todo";
  if (name === "clarify_question") return "clarify";
  return "mcp";
}

/**
 * Цветовая палитра chip per категории — light/dark тема через CSS-переменные.
 * accent/success/warning — стандартные семантические токены design-tokens.css.
 */
const CATEGORY_STYLE: Record<ToolCategory, { ok: string; error: string }> = {
  mcp: {
    ok: "bg-[var(--bg-2)] text-[var(--fg-2)] border-[var(--bd-2)] hover:border-[var(--accent-32)]",
    error: "bg-[var(--error-12)] text-[var(--error)] border-[var(--error-20)] hover:bg-[var(--error-20)]",
  },
  memory: {
    ok: "bg-[var(--info-12,var(--bg-2))] text-[var(--info,var(--fg-2))] border-[var(--info-20,var(--bd-2))] hover:opacity-90",
    error: "bg-[var(--error-12)] text-[var(--error)] border-[var(--error-20)] hover:bg-[var(--error-20)]",
  },
  todo: {
    ok: "bg-[var(--success-12,var(--bg-2))] text-[var(--success,var(--fg-2))] border-[var(--success-20,var(--bd-2))] hover:opacity-90",
    error: "bg-[var(--error-12)] text-[var(--error)] border-[var(--error-20)] hover:bg-[var(--error-20)]",
  },
  clarify: {
    ok: "bg-[var(--warning-12)] text-[var(--warning)] border-[var(--warning-20)] hover:opacity-90",
    error: "bg-[var(--error-12)] text-[var(--error)] border-[var(--error-20)] hover:bg-[var(--error-20)]",
  },
};

type ToolTraceProps = {
  toolCalls: ToolCallRecord[];
  totalDurationMs?: number;
  /** URL MCP endpoint — для формирования curl-команды. Если не передан → placeholder в curl. */
  mcpEndpoint?: string;
  /** Mcp-Session-Id — опционально, не хранится на фронте */
  mcpSessionId?: string;
};

/**
 * Мини-chip для краткого превью tool call в collapsed-режиме.
 * Tone: ok | error.
 */
function ToolChip({
  tc,
  active,
  onClick,
}: {
  tc: ToolCallRecord;
  active: boolean;
  onClick: () => void;
}) {
  const isError = tc.ok === false;
  const Icon = isError ? AlertTriangle : tc.ok === true ? CheckCircle2 : Wrench;
  // TD-7 (2026-05-24): цветной accent per категории — пользователь
  // мгновенно понимает что LLM делает (1С запрос / память / план / уточнение).
  const category = getToolCategory(tc.name);
  const styleVariant = isError ? CATEGORY_STYLE[category].error : CATEGORY_STYLE[category].ok;
  return (
    <button
      type="button"
      onClick={onClick}
      data-tool-chip={tc.id}
      data-tone={isError ? "error" : "ok"}
      data-category={category}
      className={cn(
        "inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] border transition-colors duration-micro ease-design-ease",
        styleVariant,
        active && "ring-1 ring-[var(--accent)]",
      )}
      title={`${tc.name} · ${category}`}
    >
      <Icon className="h-3 w-3" />
      <span className="font-mono" data-testid="tool-name">{tc.name}</span>
      {tc.duration_ms != null && (
        <span className="text-[var(--fg-3)] tabular-nums">{formatDuration(tc.duration_ms)}</span>
      )}
    </button>
  );
}

export function ToolTrace({ toolCalls, totalDurationMs, mcpEndpoint, mcpSessionId }: ToolTraceProps) {
  // Sprint 03 (handoff E · TraceSummary): свёрнут по умолчанию — чтобы не
  // загромождать поток. При раскрытии — сразу human-readable summary через
  // TraceSummary (не raw JSON). Аналитик видит что сделала модель и
  // каков результат, без необходимости разбирать JSON. Raw — по клику
  // «JSON» в каждом шаге.
  const [open, setOpen] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(null);

  if (!toolCalls || toolCalls.length === 0) return null;

  const durationStr = totalDurationMs != null ? ` · ${formatDuration(totalDurationMs)}` : "";

  return (
    <div className="mt-2 text-xs text-[var(--fg-muted)]" data-component="tool-trace">
      {/* Заголовок-аккордеон */}
      <div className="flex items-center gap-2 flex-wrap">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="flex items-center gap-1 hover:text-[var(--fg)] transition-colors"
          aria-expanded={open}
          data-testid="trace-toggle"
        >
          {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
          <span>
            {toolCalls.length} {pluralTools(toolCalls.length)}{durationStr}
          </span>
        </button>

        {/* Mini chips inline — компактный preview только когда свёрнуто */}
        {!open && (
          <div className="flex items-center gap-1 flex-wrap" data-testid="trace-chips">
            {toolCalls.map((tc) => (
              <ToolChip
                key={tc.id}
                tc={tc}
                active={activeId === tc.id}
                onClick={() => {
                  setOpen(true);
                  setActiveId(tc.id);
                }}
              />
            ))}
          </div>
        )}
      </div>

      {/* Expanded accordion — human-readable summary через TraceSummary */}
      {open && (
        <div
          className="mt-2 border-l-2 border-[var(--bd-1)] pl-3 animate-fade-up"
          data-testid="trace-list"
        >
          {toolCalls.map((tc, i) => (
            <TraceSummary
              key={tc.id}
              toolCall={tc}
              index={i}
              mcpEndpoint={mcpEndpoint}
              mcpSessionId={mcpSessionId}
            />
          ))}
        </div>
      )}
    </div>
  );
}
