"use client";

import { useMemo, useState } from "react";
import { Download, ChevronUp, ChevronDown, ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table";
import { cn } from "@/lib/utils";
import { rowsToCsv, downloadCsv } from "@/lib/csv";
import type { TableCardPayload } from "@/lib/types";

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

function formatCell(value: unknown, colType: string): React.ReactNode {
  if (value === null || value === undefined) {
    return <span className="text-[var(--fg-muted)]">—</span>;
  }
  if (typeof value === "boolean") {
    return (
      <span className={value ? "text-green-400" : "text-[var(--fg-muted)]"}>
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
  return str;
}

interface TableCardProps {
  payload: TableCardPayload;
}

export function TableCard({ payload }: TableCardProps) {
  const { columns, rows, total, meta } = payload;
  const [page, setPage] = useState(0);
  const [sortBy, setSortBy] = useState<number | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>("asc");

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

  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--bg-elevated)] overflow-hidden">
      {/* Заголовок */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-[var(--border)]">
        <span className="text-xs text-[var(--fg-muted)]">
          Таблица · {total} {total === 1 ? "строка" : "строк"}
          {queryLabel && ` · ${queryLabel}`}
          {meta?.duration_ms != null && ` · ${meta.duration_ms} мс`}
        </span>
        <Button
          size="sm"
          variant="ghost"
          className="gap-1 text-xs h-7"
          onClick={() => downloadCsv(`table-${Date.now()}.csv`, rowsToCsv(columns, rows))}
          title="Скачать CSV"
        >
          <Download className="h-3 w-3" />
          Скачать CSV
        </Button>
      </div>

      {showSortWarning && sortBy !== null && (
        <div className="px-3 py-1 text-xs text-yellow-400 bg-yellow-950/30 border-b border-[var(--border)]">
          Большой результат ({total} строк) — сортировка отключена. Скачайте CSV для полного анализа.
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
                  "cursor-pointer select-none hover:bg-[var(--bg-elevated)] whitespace-nowrap",
                  col.type === "Number" && "text-right",
                )}
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
            <TableRow key={ri}>
              {row.map((cell, ci) => (
                <TableCell
                  key={ci}
                  className={cn(
                    "text-xs",
                    columns[ci]?.type === "Number" && "text-right tabular-nums",
                  )}
                >
                  {formatCell(cell, columns[ci]?.type ?? "String")}
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
    </div>
  );
}
