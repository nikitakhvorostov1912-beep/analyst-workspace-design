"use client";

import { useMemo, useState } from "react";
import { Download, ChevronUp, ChevronDown, ChevronLeft, ChevronRight, Eye } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/Alert";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table";
import { cn } from "@/lib/utils";
import { rowsToCsv, downloadCsv } from "@/lib/csv";
import { publishToast } from "@/lib/toast";
import { extractAnonTokens, highlightAnonTokens } from "@/lib/anon-tokens";
import type { TableCardPayload } from "@/lib/types";
import { CardHeader } from "./CardHeader";

const PAGE_SIZE = 50;
/** Лимит строк для client-side сортировки — свыше показываем предупреждение. */
const SORT_CAP = 1000;

type SortDir = "asc" | "desc";

function compareValues(a: unknown, b: unknown, dir: SortDir): number {
  // null/undefined всегда вниз
  const aNull = a === null || a === undefined;
  const bNull = b === null || b === undefined;
  if (aNull && bNull) return 0;
  if (aNull) return 1;
  if (bNull) return -1;

  let result = 0;
  if (typeof a === "number" && typeof b === "number") {
    result = a - b;
  } else {
    // Разные типы — конвертируем в строку
    result = String(a).localeCompare(String(b), "ru");
  }
  return dir === "asc" ? result : -result;
}

function formatCell(
  value: unknown,
  colType: string,
  revealedMap?: Record<string, string> | null,
): React.ReactNode {
  if (value === null || value === undefined) {
    return <span className="text-[var(--fg-muted)]">—</span>;
  }
  if (typeof value === "boolean") {
    return (
      <span className={value ? "text-[var(--success)]" : "text-[var(--fg-muted)]"}>
        {value ? "✓" : "✗"}
      </span>
    );
  }
  if (typeof value === "object") {
    return (
      <span className="font-mono text-xs text-[var(--fg-muted)]">
        {JSON.stringify(value).slice(0, 80)}
      </span>
    );
  }
  const str = String(value);
  // Числа выравниваем правее (через родительский th)
  if (colType === "Number" || typeof value === "number") {
    return <span>{str}</span>;
  }
  // Применяем подсветку anon-токенов для строковых значений
  return <>{highlightAnonTokens(str, revealedMap ?? undefined)}</>;
}

interface TableCardProps {
  payload: TableCardPayload;
  /** Callback для раскрытия anon-токенов — передаётся из CardRenderer */
  onDeanonymize?: (tokens: string[]) => Promise<Record<string, string>>;
}

export function TableCard({ payload, onDeanonymize }: TableCardProps) {
  const { columns, rows, total, meta, truncated, total_available } = payload;
  const [page, setPage] = useState(0);
  const [sortBy, setSortBy] = useState<number | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [revealedMap, setRevealedMap] = useState<Record<string, string> | null>(null);
  const [revealing, setRevealing] = useState(false);
  const [showTruncDetail, setShowTruncDetail] = useState(false);

  // Вычисляем токены в payload (memoized)
  const tokensInPayload = useMemo(
    () => extractAnonTokens({ columns, rows }),
    [columns, rows],
  );

  async function handleReveal() {
    if (!onDeanonymize || tokensInPayload.length === 0 || revealing) return;
    setRevealing(true);
    try {
      const mapping = await onDeanonymize(tokensInPayload);
      setRevealedMap(mapping);
    } catch {
      publishToast({ type: "error", message: "Не удалось раскрыть значения" });
    } finally {
      setRevealing(false);
    }
  }

  const totalPages = Math.ceil(total / PAGE_SIZE);
  const showPagination = total > PAGE_SIZE;
  const showSortWarning = total > SORT_CAP;

  function toggleSort(idx: number) {
    if (sortBy === idx) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(idx);
      setSortDir("asc");
      setPage(0);
    }
  }

  const sortedRows = useMemo(() => {
    if (sortBy === null || rows.length > SORT_CAP) return rows;
    return [...rows].sort((a, b) => compareValues(a[sortBy], b[sortBy], sortDir));
  }, [rows, sortBy, sortDir]);

  const pageRows = sortedRows.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  const queryLabel = meta?.query ? `«${meta.query.slice(0, 80)}${meta.query.length > 80 ? "…" : ""}»` : null;
  const metaLine = [
    `${total} ${total === 1 ? "строка" : "строк"}`,
    queryLabel,
    meta?.duration_ms != null ? `${meta.duration_ms} мс` : null,
  ]
    .filter(Boolean)
    .join(" · ");

  const isTruncated = Boolean(truncated && total_available && total_available > total);

  return (
    <div className="rounded-[10px] border border-[var(--bd-2)] bg-[var(--bg-1)] overflow-hidden">
      {/* Один заголовок: иконка+title+мета + (чип усечения) слева, CSV справа (§3.7) */}
      <CardHeader
        type="table"
        title="Таблица"
        meta={metaLine}
        chip={
          isTruncated ? (
            <button
              type="button"
              onClick={() => setShowTruncDetail((v) => !v)}
              data-testid="result-truncated-chip"
              className="inline-flex items-center gap-1 px-1.5 py-px rounded text-[11px] bg-[var(--warning-12)] text-[var(--warning)] border border-[var(--warning-20)] tabular-nums"
              title="Показано не всё — почему?"
            >
              {total} из {total_available}
            </button>
          ) : undefined
        }
        extra={
          <Button
            size="sm"
            variant="ghost"
            className="gap-1 text-xs h-7"
            onClick={() => downloadCsv(`table-${Date.now()}.csv`, rowsToCsv(columns, rows))}
            title="Скачать CSV"
          >
            <Download className="h-3 w-3" />
            CSV
          </Button>
        }
      />

      {/* Деталь усечения — только по клику на чип (§3.7: не полноширинный баннер) */}
      {isTruncated && showTruncDetail && (
        <div className="px-3 pt-2" data-testid="result-truncated-banner">
          <Alert
            tone="warning"
            title={`Показаны первые ${total} из ${total_available} строк`}
            description="Чтобы получить полный набор — сузьте запрос (условие WHERE / временной диапазон) или попросите модель добавить агрегацию. CSV выгрузит видимые строки."
            onClose={() => setShowTruncDetail(false)}
          />
        </div>
      )}

      {/* Предупреждение сортировки — компактная строка (§3.7), не полоса */}
      {showSortWarning && sortBy !== null && (
        <div className="px-3 py-1 text-[11px] text-[var(--warning)] flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 rounded-full bg-[var(--warning)] flex-none" aria-hidden="true" />
          Большой результат — сортировка отключена, выгрузите CSV для полного анализа.
        </div>
      )}

      {/* Таблица */}
      <Table>
        <TableHeader>
          <TableRow>
            {columns.map((col, i) => (
              <TableHead
                key={i}
                onClick={() => toggleSort(i)}
                className={cn(
                  "cursor-pointer select-none hover:bg-[var(--bg-2)] whitespace-nowrap",
                  "text-[10px] uppercase tracking-[0.08em] text-[var(--fg-3)]",
                  col.type === "Number" && "text-right",
                )}
                style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
              >
                <span className="inline-flex items-center gap-1">
                  {col.name}
                  {sortBy === i ? (
                    sortDir === "asc" ? (
                      <ChevronUp className="h-3 w-3 text-[var(--accent)]" />
                    ) : (
                      <ChevronDown className="h-3 w-3 text-[var(--accent)]" />
                    )
                  ) : (
                    <ChevronUp className="h-3 w-3 opacity-20" />
                  )}
                </span>
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {pageRows.map((row, ri) => (
            <TableRow key={ri} className="even:bg-[var(--zebra)]">
              {row.map((cell, ci) => (
                <TableCell
                  key={ci}
                  className={cn(
                    "text-[13px]",
                    columns[ci]?.type === "Number" && "text-right tabular-nums",
                  )}
                >
                  {formatCell(cell, columns[ci]?.type ?? "String", revealedMap)}
                </TableCell>
              ))}
            </TableRow>
          ))}
          {pageRows.length === 0 && (
            <TableRow>
              <TableCell
                colSpan={columns.length || 1}
                className="text-center text-[var(--fg-muted)] py-6"
              >
                Нет данных
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>

      {/* Пагинация */}
      {showPagination && (
        <div className="flex items-center justify-between px-3 py-2 border-t border-[var(--border)]">
          <span className="text-xs text-[var(--fg-muted)]">
            Стр. {page + 1} из {totalPages}
          </span>
          <div className="flex gap-1">
            <Button
              size="sm"
              variant="ghost"
              className="h-7 w-7 p-0"
              onClick={() => setPage((p) => p - 1)}
              disabled={page === 0}
              aria-label="Предыдущая страница"
            >
              <ChevronLeft className="h-3 w-3" />
            </Button>
            <Button
              size="sm"
              variant="ghost"
              className="h-7 w-7 p-0"
              onClick={() => setPage((p) => p + 1)}
              disabled={page >= totalPages - 1}
              aria-label="Следующая страница"
            >
              <ChevronRight className="h-3 w-3" />
            </Button>
          </div>
        </div>
      )}

      {/* Anon footer: кнопка Раскрыть или бейдж Реальные значения */}
      {tokensInPayload.length > 0 && (
        <div className="px-3 py-2 border-t border-[var(--border)] flex items-center gap-2">
          {revealedMap !== null ? (
            <span className="text-xs text-[var(--success)] flex items-center gap-1">
              <Eye className="h-3 w-3" />
              Реальные значения
            </span>
          ) : (
            <Button
              size="sm"
              variant="ghost"
              className="text-xs h-7 gap-1 text-[var(--warning)] hover:opacity-80"
              disabled={!onDeanonymize || revealing}
              onClick={() => { void handleReveal(); }}
            >
              <Eye className="h-3 w-3" />
              {revealing ? "Загрузка..." : `Раскрыть реальные значения (${tokensInPayload.length})`}
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
