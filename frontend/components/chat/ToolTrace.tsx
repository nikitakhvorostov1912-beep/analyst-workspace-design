"use client";
import { useState } from "react";
import { ChevronRight, ChevronDown, Copy, Wrench, AlertTriangle, CheckCircle2 } from "lucide-react";
import { JsonTree } from "@/lib/json-tree";
import { formatDuration } from "@/lib/format-duration";
import { buildCurlCommand } from "@/lib/curl-builder";
import { publishToast } from "@/lib/toast";
import { cn } from "@/lib/utils";
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
  const [open, setOpen] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(null);

  if (!toolCalls || toolCalls.length === 0) return null;

  const durationStr = totalDurationMs != null ? `, ${formatDuration(totalDurationMs)}` : "";

  async function handleCopyCurl(tc: ToolCallRecord) {
    try {
      const cmd = buildCurlCommand(tc, mcpEndpoint ?? "", mcpSessionId);
      await navigator.clipboard.writeText(cmd);
      publishToast({ type: "info", message: "Скопировано" });
    } catch {
      publishToast({ type: "error", message: "Не удалось скопировать" });
    }
  }

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

        {/* Mini chips inline — компактный preview */}
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

      {/* Expanded accordion */}
      {open && (
        <ul
          className="mt-2 space-y-2 border-l-2 border-[var(--bd-1)] pl-3 animate-fade-up"
          data-testid="trace-list"
        >
          {toolCalls.map((tc) => {
            const isActive = activeId === tc.id;
            const isError = tc.ok === false;
            return (
              <li
                key={tc.id}
                className={cn(
                  "space-y-1 rounded-md px-2 py-1.5 transition-colors duration-micro ease-design-ease",
                  isActive && "bg-[var(--bg-1)]",
                )}
                data-active={isActive ? "true" : "false"}
              >
                <div className="flex items-baseline gap-2 flex-wrap">
                  <ToolChip
                    tc={tc}
                    active={isActive}
                    onClick={() => setActiveId(isActive ? null : tc.id)}
                  />
                  {isError && (
                    <span className="text-[var(--error)] text-[11px]" data-testid="tool-error-badge">
                      · ошибка
                    </span>
                  )}
                  {/* Кнопка «Скопировать как curl» (TRACE-03) */}
                  <button
                    type="button"
                    onClick={() => { void handleCopyCurl(tc); }}
                    aria-label="Скопировать как curl"
                    className="text-xs text-[var(--fg-muted)] hover:text-[var(--fg)] inline-flex items-center gap-1 ml-auto"
                  >
                    <Copy size={12} />
                    <span>Скопировать как curl</span>
                  </button>
                </div>

                <details className="ml-2">
                  <summary className="cursor-pointer text-[var(--fg-muted)] hover:text-[var(--fg)] text-[11px]">
                    Аргументы
                  </summary>
                  <div className="mt-1 ml-2">
                    <JsonTree value={tc.args} defaultExpanded={1} />
                  </div>
                </details>

                {tc.result !== undefined && (
                  <details className="ml-2" data-testid="result-details">
                    <summary className="cursor-pointer text-[var(--fg-muted)] hover:text-[var(--fg)] text-[11px]">
                      Результат
                    </summary>
                    <div className="mt-1 ml-2">
                      <JsonTree value={tc.result} defaultExpanded={0} />
                    </div>
                  </details>
                )}

                {tc.error ? (
                  <div className="ml-2 text-[var(--error)] font-mono text-[11px]" data-testid="tool-error-text">
                    {tc.error}
                  </div>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
