"use client";

import { useState } from "react";
import {
  ChevronRight,
  ChevronDown,
  Check,
  AlertTriangle,
  Copy,
} from "lucide-react";
import { JsonTree } from "@/lib/json-tree";
import { summarizeToolCall } from "@/lib/tool-summary";
import { formatDuration } from "@/lib/format-duration";
import { buildCurlCommand } from "@/lib/curl-builder";
import { publishToast } from "@/lib/toast";
import { cn } from "@/lib/utils";
import type { ToolCallRecord } from "@/lib/types";

interface TraceSummaryProps {
  toolCall: ToolCallRecord;
  index: number;
  /** Для buildCurlCommand — endpoint и session-id из ToolTrace props */
  mcpEndpoint?: string;
  mcpSessionId?: string;
}

/**
 * Sprint 03 (handoff E · TraceSummary): человекочитаемый блок одного tool call.
 *
 * Вместо raw JsonTree аналитик видит «Запрос к 1С — 24 записи · 380 мс».
 * По клику «JSON» — раскрывается raw view (с правильными --syntax-* цветами
 * из REM-1 Sprint 01).
 */
export function TraceSummary({
  toolCall,
  index,
  mcpEndpoint,
  mcpSessionId,
}: TraceSummaryProps) {
  const [showRaw, setShowRaw] = useState(false);
  const summary = summarizeToolCall(toolCall);
  const ok = toolCall.ok !== false;
  const { duration_ms, error } = toolCall;

  async function handleCopyCurl() {
    try {
      const cmd = buildCurlCommand(toolCall, mcpEndpoint ?? "", mcpSessionId);
      await navigator.clipboard.writeText(cmd);
      publishToast({ type: "info", message: "Скопировано" });
    } catch {
      publishToast({ type: "error", message: "Не удалось скопировать" });
    }
  }

  return (
    <div
      className="border-b border-[var(--bd-1)] last:border-b-0 px-3 py-2.5"
      data-testid={`trace-step-${index}`}
    >
      <div className="flex items-start gap-3">
        <span
          className="text-[10px] tracking-[0.14em] text-[var(--fg-4)] tabular-nums pt-0.5 select-none flex-none"
          style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
        >
          {String(index + 1).padStart(2, "0")}
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1 text-xs">
            <span className="font-medium text-[var(--accent)] break-words">
              {summary.title}
            </span>
            <span className="text-[var(--fg-4)]">·</span>
            <span
              className={cn(
                "inline-flex items-center gap-1",
                ok ? "text-[var(--success)]" : "text-[var(--error)]",
              )}
            >
              {ok ? (
                <Check className="h-3 w-3" aria-hidden="true" />
              ) : (
                <AlertTriangle className="h-3 w-3" aria-hidden="true" />
              )}
              {summary.result}
            </span>
            {duration_ms !== undefined && (
              <span
                className="text-[var(--fg-4)] tabular-nums text-[10px] tracking-[0.06em]"
                style={{
                  fontFamily: "var(--font-jb-mono), ui-monospace, monospace",
                }}
              >
                {formatDuration(duration_ms)}
              </span>
            )}
            <button
              type="button"
              onClick={() => setShowRaw((s) => !s)}
              className="ml-auto text-[9px] tracking-[0.18em] uppercase text-[var(--fg-3)] hover:text-[var(--fg-1)] transition-colors flex items-center gap-1"
              style={{
                fontFamily: "var(--font-jb-mono), ui-monospace, monospace",
              }}
              aria-expanded={showRaw}
              data-testid={`trace-toggle-json-${index}`}
            >
              {showRaw ? (
                <ChevronDown className="h-2.5 w-2.5" aria-hidden="true" />
              ) : (
                <ChevronRight className="h-2.5 w-2.5" aria-hidden="true" />
              )}
              JSON
            </button>
          </div>
          {error && !showRaw && (
            <div
              className="text-[var(--error)] font-mono text-[11px] mt-1 break-all"
              data-testid="tool-error-text"
            >
              {error}
            </div>
          )}
          {showRaw && (
            <div className="mt-2 p-3 bg-[var(--code-bg)] rounded border border-[var(--bd-2)] text-[var(--code-fg)] animate-fade-up text-xs">
              <div className="flex items-center justify-between mb-2">
                <span
                  className="text-[9px] tracking-[0.16em] uppercase text-[var(--fg-4)]"
                  style={{
                    fontFamily:
                      "var(--font-jb-mono), ui-monospace, monospace",
                  }}
                >
                  Имя · {toolCall.name}
                </span>
                <button
                  type="button"
                  onClick={() => {
                    void handleCopyCurl();
                  }}
                  aria-label="Скопировать как curl"
                  className="text-[9px] tracking-[0.16em] uppercase text-[var(--fg-3)] hover:text-[var(--fg-1)] inline-flex items-center gap-1"
                  style={{
                    fontFamily:
                      "var(--font-jb-mono), ui-monospace, monospace",
                  }}
                >
                  <Copy className="h-3 w-3" aria-hidden="true" />
                  curl
                </button>
              </div>
              <div
                className="text-[9px] tracking-[0.16em] uppercase text-[var(--fg-4)] mb-1"
                style={{
                  fontFamily: "var(--font-jb-mono), ui-monospace, monospace",
                }}
              >
                Параметры
              </div>
              <JsonTree value={toolCall.args ?? null} defaultExpanded={2} />
              {toolCall.result !== undefined && (
                <>
                  <div
                    className="text-[9px] tracking-[0.16em] uppercase text-[var(--fg-4)] mb-1 mt-3"
                    style={{
                      fontFamily:
                        "var(--font-jb-mono), ui-monospace, monospace",
                    }}
                  >
                    Результат
                  </div>
                  <JsonTree value={toolCall.result ?? null} defaultExpanded={1} />
                </>
              )}
              {error && (
                <>
                  <div
                    className="text-[9px] tracking-[0.16em] uppercase text-[var(--error)] mb-1 mt-3"
                    style={{
                      fontFamily:
                        "var(--font-jb-mono), ui-monospace, monospace",
                    }}
                  >
                    Ошибка
                  </div>
                  <div className="text-[var(--error)] font-mono text-[11px] break-all">
                    {error}
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
