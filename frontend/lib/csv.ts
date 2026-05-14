/**
 * Утилита генерации CSV + скачивание через ObjectURL.
 * BOM ﻿ в начале для корректного открытия в Excel с кириллицей.
 */

type ColumnLike = { name: string };

/** Экранирует значение ячейки для CSV. */
function csvEscape(v: unknown): string {
  if (v === null || v === undefined) return "";
  const str = typeof v === "object" ? JSON.stringify(v) : String(v);
  if (str.includes(",") || str.includes('"') || str.includes("\n")) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

/**
 * Генерирует CSV-строку из columns + rows.
 * Включает UTF-8 BOM для корректного открытия в Excel.
 */
export function rowsToCsv(
  columns: ColumnLike[],
  rows: unknown[][],
): string {
  const header = columns.map((c) => csvEscape(c.name)).join(",");
  const lines = rows.map((row) => row.map(csvEscape).join(","));
  return "﻿" + [header, ...lines].join("\r\n");
}

/**
 * Создаёт Blob и запускает скачивание CSV-файла.
 */
export function downloadCsv(filename: string, content: string): void {
  const blob = new Blob([content], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
