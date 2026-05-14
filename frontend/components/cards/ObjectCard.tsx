"use client";

import { Badge } from "@/components/ui/badge";
import type { ObjectCardPayload } from "@/lib/types";

interface ObjectCardProps {
  payload: ObjectCardPayload;
}

function SectionWrapper({
  title,
  count,
  children,
  defaultOpen = true,
}: {
  title: string;
  count: number;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  return (
    <details
      open={defaultOpen}
      className="group border-b border-[var(--border)] last:border-0"
    >
      <summary className="flex cursor-pointer select-none items-center justify-between px-3 py-2 hover:bg-[var(--bg-elevated)] list-none">
        <span className="text-xs font-medium text-[var(--fg)]">{title}</span>
        <span className="text-xs text-[var(--fg-muted)]">{count}</span>
      </summary>
      <div className="px-3 pb-3 pt-1">{children}</div>
    </details>
  );
}

/** Мини-таблица для rows_preview табличной части. */
function MiniTable({
  columns,
  rows,
}: {
  columns: string[];
  rows: unknown[][];
}) {
  if (columns.length === 0) return null;
  return (
    <div className="overflow-x-auto mt-1">
      <table className="w-full text-xs border-collapse">
        <thead>
          <tr className="border-b border-[var(--border)]">
            {columns.map((col, i) => (
              <th
                key={i}
                className="px-2 py-1 text-left text-[var(--fg-muted)] font-medium whitespace-nowrap"
              >
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, 5).map((row, ri) => (
            <tr key={ri} className="border-b border-[var(--border)] last:border-0">
              {(Array.isArray(row) ? row : []).map((cell, ci) => (
                <td key={ci} className="px-2 py-1 text-[var(--fg)] whitespace-nowrap">
                  {cell === null || cell === undefined
                    ? "—"
                    : typeof cell === "object"
                      ? JSON.stringify(cell).slice(0, 40)
                      : String(cell)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ObjectCard({ payload }: ObjectCardProps) {
  const { header, attributes, tabular_sections, forms, templates } = payload;

  const hasAny =
    attributes.length > 0 ||
    tabular_sections.length > 0 ||
    forms.length > 0 ||
    templates.length > 0;

  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--bg-elevated)] overflow-hidden">
      {/* Header */}
      <div className="flex flex-col gap-1 px-3 py-2 border-b border-[var(--border)]">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-[var(--fg)] break-all">
            {header.name}
          </span>
          {header.type && (
            <Badge variant="secondary" className="shrink-0">
              {header.type}
            </Badge>
          )}
        </div>
        {header.path && (
          <span className="text-xs text-[var(--fg-muted)]">{header.path}</span>
        )}
      </div>

      {!hasAny ? (
        <div className="px-3 py-4 text-xs text-[var(--fg-muted)] text-center">
          Подробности недоступны
        </div>
      ) : (
        <>
          {/* Реквизиты */}
          {attributes.length > 0 && (
            <SectionWrapper title="Реквизиты" count={attributes.length}>
              <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
                {attributes.map((attr, i) => (
                  <div key={i} className="contents">
                    <dt className="text-xs text-[var(--fg-muted)] whitespace-nowrap py-0.5">
                      {attr.name}
                    </dt>
                    <dd className="text-xs text-[var(--fg)] py-0.5">
                      <span className="text-[var(--fg-muted)] mr-1">{attr.type}</span>
                      {attr.value !== undefined && attr.value !== null && (
                        <span>{String(attr.value)}</span>
                      )}
                    </dd>
                  </div>
                ))}
              </dl>
            </SectionWrapper>
          )}

          {/* Табличные части */}
          {tabular_sections.length > 0 && (
            <SectionWrapper
              title="Табличные части"
              count={tabular_sections.length}
            >
              <div className="space-y-3">
                {tabular_sections.map((ts, i) => (
                  <div key={i}>
                    <div className="text-xs font-medium text-[var(--fg)] mb-1">
                      {ts.name}
                    </div>
                    {ts.rows_preview && ts.rows_preview.length > 0 ? (
                      <MiniTable
                        columns={ts.columns}
                        rows={ts.rows_preview as unknown[][]}
                      />
                    ) : (
                      <div className="flex flex-wrap gap-1">
                        {ts.columns.map((col: string, ci: number) => (
                          <Badge key={ci} variant="outline" className="text-xs">
                            {col}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </SectionWrapper>
          )}

          {/* Формы */}
          {forms.length > 0 && (
            <SectionWrapper title="Формы" count={forms.length}>
              <ul className="space-y-1">
                {forms.map((f, i) => (
                  <li key={i} className="flex items-center gap-2">
                    <span className="text-xs text-[var(--fg)]">{f.name}</span>
                    {f.type && (
                      <Badge variant="outline" className="text-xs shrink-0">
                        {f.type}
                      </Badge>
                    )}
                  </li>
                ))}
              </ul>
            </SectionWrapper>
          )}

          {/* Макеты */}
          {templates.length > 0 && (
            <SectionWrapper title="Макеты" count={templates.length}>
              <ul className="space-y-1">
                {templates.map((t, i) => (
                  <li key={i} className="flex items-center gap-2">
                    <span className="text-xs text-[var(--fg)]">{t.name}</span>
                    {t.type && (
                      <Badge variant="outline" className="text-xs shrink-0">
                        {t.type}
                      </Badge>
                    )}
                  </li>
                ))}
              </ul>
            </SectionWrapper>
          )}
        </>
      )}
    </div>
  );
}
