"use client";
import { useState } from "react";
import { ChevronRight, ChevronDown, Copy } from "lucide-react";
import { JsonTree } from "@/lib/json-tree";
import { formatDuration } from "@/lib/format-duration";
import { buildCurlCommand } from "@/lib/curl-builder";
import { publishToast } from "@/lib/toast";
import type { ToolCallRecord } from "@/lib/types";

function pluralTools(n: number): string {
  if (n === 1) return "инструмент";
  if (n >= 2 && n <= 4) return "инструмента";
  return "инструментов";
}

type ToolTraceProps = {
  toolCalls: ToolCallRecord[];
  totalDurationMs?: number;
  /** URL MCP endpoint — для формирования curl-команды. Если не передан → placeholder в curl. */
  mcpEndpoint?: string;
  /** Mcp-Session-Id — опционально, не хранится на фронте */
  mcpSessionId?: string;
};

export function ToolTrace({ toolCalls, totalDurationMs, mcpEndpoint, mcpSessionId }: ToolTraceProps) {
  const [open, setOpen] = useState(false);

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
    <div className="mt-2 text-xs text-[var(--fg-muted)]">
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

      {open && (
        <ul className="mt-2 space-y-3 border-l-2 border-[var(--border)] pl-3" data-testid="trace-list">
          {toolCalls.map((tc) => (
            <li key={tc.id} className="space-y-1">
              <div className="flex items-baseline gap-2 flex-wrap">
                <span className="font-mono text-[var(--fg)]" data-testid="tool-name">{tc.name}</span>
                {tc.duration_ms != null ? (
                  <span className="text-[var(--fg-muted)]">· {formatDuration(tc.duration_ms)}</span>
                ) : null}
                {tc.ok === false ? (
                  <span className="text-red-400" data-testid="tool-error-badge">· ошибка</span>
                ) : null}
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
                <summary className="cursor-pointer text-[var(--fg-muted)] hover:text-[var(--fg)]">
                  Аргументы
                </summary>
                <div className="mt-1 ml-2">
                  <JsonTree value={tc.args} defaultExpanded={1} />
                </div>
              </details>

              {tc.result !== undefined && (
                <details className="ml-2" data-testid="result-details">
                  <summary className="cursor-pointer text-[var(--fg-muted)] hover:text-[var(--fg)]">
                    Результат
                  </summary>
                  <div className="mt-1 ml-2">
                    <JsonTree value={tc.result} defaultExpanded={0} />
                  </div>
                </details>
              )}

              {tc.error ? (
                <div className="ml-2 text-red-400 font-mono" data-testid="tool-error-text">
                  {tc.error}
                </div>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
