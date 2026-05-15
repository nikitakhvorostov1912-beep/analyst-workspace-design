"use client";

import { useState } from "react";
import { Copy, Check, ChevronDown, ChevronUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { highlight } from "@/lib/highlight";
import { JsonTree } from "@/lib/json-tree";
import type { CodeCardPayload } from "@/lib/types";

const CODE_TRUNCATE = 50_000; // T-04-12: DoS protection

const LANGUAGE_LABELS: Record<string, string> = {
  bsl: "BSL",
  sql: "SQL",
  json: "JSON",
  text: "Text",
};

interface CodeCardProps {
  payload: CodeCardPayload;
}

export function CodeCard({ payload }: CodeCardProps) {
  const { language, code, executable, result } = payload;
  const [copied, setCopied] = useState(false);
  const [resultOpen, setResultOpen] = useState(false);

  // Обрезаем если превышает лимит (дополнительная защита на фронте)
  const displayCode = code.length > CODE_TRUNCATE
    ? code.slice(0, CODE_TRUNCATE) + "\n...truncated"
    : code;

  const highlightedHtml = highlight(displayCode, language);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard недоступен — нет alert
    }
  }

  return (
    <div
      className="rounded-lg border border-[var(--border)] bg-[var(--bg-elevated)] overflow-hidden"
      aria-label={`Блок кода на языке ${LANGUAGE_LABELS[language] ?? language}`}
    >
      {/* Заголовок */}
      <div className="flex items-center gap-2 px-3 py-1.5 border-b border-[var(--border)]">
        {/* Language badge */}
        <span className={cn(
          "px-1.5 py-0.5 rounded text-xs font-medium font-mono",
          language === "bsl" && "bg-violet-900/40 text-violet-300",
          language === "sql" && "bg-blue-900/40 text-blue-300",
          language === "json" && "bg-amber-900/40 text-amber-300",
          language === "text" && "bg-[var(--bg-surface)] text-[var(--fg-muted)]",
        )}>
          {LANGUAGE_LABELS[language] ?? language}
        </span>

        <div className="flex-1" />

        {/* Кнопка показать результат */}
        {executable && result != null && (
          <Button
            size="sm"
            variant="ghost"
            className="text-xs h-7 gap-1"
            onClick={() => setResultOpen((o) => !o)}
          >
            {resultOpen ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
            Результат
          </Button>
        )}

        {/* Copy button */}
        <Button
          size="sm"
          variant="ghost"
          className="text-xs h-7 gap-1"
          onClick={() => { void handleCopy(); }}
          title="Скопировать код"
        >
          {copied ? (
            <Check className="h-3 w-3 text-emerald-400" />
          ) : (
            <Copy className="h-3 w-3" />
          )}
        </Button>
      </div>

      {/* Код с подсветкой */}
      <div className="overflow-x-auto">
        <pre className="p-3 text-xs font-mono leading-relaxed">
          <code
            className={`language-${language}`}
            // prismjs output содержит только token spans с class атрибутами (без inline style)
            // Входные данные — output от prismjs, не от пользователя напрямую
            // eslint-disable-next-line react/no-danger
            dangerouslySetInnerHTML={{ __html: highlightedHtml }}
          />
        </pre>
      </div>

      {/* Результат выполнения */}
      {executable && result != null && resultOpen && (
        <div className="border-t border-[var(--border)] p-3">
          <p className="text-xs text-[var(--fg-muted)] mb-1">Результат выполнения:</p>
          <JsonTree value={result} defaultExpanded={1} />
        </div>
      )}
    </div>
  );
}
