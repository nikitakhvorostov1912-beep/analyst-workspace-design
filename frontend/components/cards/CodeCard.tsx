"use client";

import { useMemo, useState } from "react";
import { Copy, Check, ChevronDown, ChevronUp, Maximize2, Minimize2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { highlight } from "@/lib/highlight";
import { JsonTree } from "@/lib/json-tree";
import type { CodeCardPayload } from "@/lib/types";
import { CardHeader } from "./CardHeader";

const CODE_TRUNCATE = 50_000; // T-04-12: DoS protection
/** Порог автосвёртывания. Меньше — показываем целиком, больше — collapsed с кнопкой. */
const COLLAPSE_LINES_THRESHOLD = 6;
/** Сколько строк видно когда блок свёрнут. */
const COLLAPSED_PREVIEW_LINES = 6;

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

  const lineCount = useMemo(() => displayCode.split("\n").length, [displayCode]);
  const collapsible = lineCount > COLLAPSE_LINES_THRESHOLD;
  // По умолчанию длинные блоки свёрнуты — захламляют ленту чата.
  const [expanded, setExpanded] = useState(!collapsible);

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

  const languageLabel = LANGUAGE_LABELS[language] ?? language;

  // Высота preview: line-height (xs leading-relaxed = ~1.625 от 12px ≈ 19.5px) × строки
  // + p-3 (24px вертикальные паддинги). Берём с запасом, чтобы prismjs spans не обрезались.
  const collapsedMaxHeight = `${COLLAPSED_PREVIEW_LINES * 20 + 24}px`;

  return (
    <div
      className="rounded-lg border border-[var(--border)] bg-[var(--bg-elevated)] overflow-hidden"
      aria-label={`Блок кода на языке ${languageLabel}`}
    >
      <CardHeader
        type="code"
        title={languageLabel}
        toolName={language}
        meta={collapsible && !expanded ? `${lineCount} строк · свёрнут` : undefined}
      />

      {/* Toolbar row */}
      <div className="flex items-center justify-end gap-1 px-3 py-1.5 border-b border-[var(--bd-1)] bg-[var(--bg-1)]">
        {collapsible && (
          <Button
            size="sm"
            variant="ghost"
            className="text-xs h-7 gap-1"
            onClick={() => setExpanded((v) => !v)}
            data-testid="code-collapse-toggle"
            title={expanded ? `Свернуть до ${COLLAPSED_PREVIEW_LINES} строк` : `Показать все ${lineCount} строк`}
          >
            {expanded ? (
              <>
                <Minimize2 className="h-3 w-3" />
                Свернуть
              </>
            ) : (
              <>
                <Maximize2 className="h-3 w-3" />
                Показать {lineCount} строк
              </>
            )}
          </Button>
        )}

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

      {/* Код с подсветкой. Когда свёрнут — фиксированная max-height + fade-gradient внизу. */}
      <div
        className="relative overflow-x-auto"
        style={
          collapsible && !expanded
            ? { maxHeight: collapsedMaxHeight, overflowY: "hidden" }
            : undefined
        }
      >
        <pre className="p-3 text-xs font-mono leading-relaxed">
          <code
            className={`language-${language}`}
            // prismjs output содержит только token spans с class атрибутами (без inline style)
            // Входные данные — output от prismjs, не от пользователя напрямую
            // eslint-disable-next-line react/no-danger
            dangerouslySetInnerHTML={{ __html: highlightedHtml }}
          />
        </pre>
        {collapsible && !expanded && (
          <button
            type="button"
            onClick={() => setExpanded(true)}
            className="absolute inset-x-0 bottom-0 h-12 flex items-end justify-center pb-1 bg-gradient-to-t from-[var(--bg-elevated)] via-[var(--bg-elevated)]/80 to-transparent cursor-pointer hover:from-[var(--bg-hover)]"
            aria-label={`Показать все ${lineCount} строк`}
            title="Кликните чтобы раскрыть"
          >
            <span className="text-[11px] text-[var(--fg-2)] font-medium flex items-center gap-1">
              <Maximize2 className="h-3 w-3" />
              ещё {lineCount - COLLAPSED_PREVIEW_LINES} {pluralizeLines(lineCount - COLLAPSED_PREVIEW_LINES)}
            </span>
          </button>
        )}
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

function pluralizeLines(n: number): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod100 >= 11 && mod100 <= 14) return "строк";
  if (mod10 === 1) return "строка";
  if (mod10 >= 2 && mod10 <= 4) return "строки";
  return "строк";
}
