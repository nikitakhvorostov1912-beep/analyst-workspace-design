"use client";

import { useState } from "react";

import { useKnowledgeStatus } from "@/hooks/useKnowledgeStatus";

/**
 * M-K2.11 «Local Knowledge» badge — компактный индикатор статуса ИТС + БСП
 * индексов в Shell header.
 *
 * Поведение:
 * - При hover/click — popover с подробностями (counts, model, провайдер).
 * - Цвет точки: зелёная если оба индекса ready, жёлтая если один, серая
 *   если оба пустые/disabled.
 * - При loading — pulse animation.
 * - В подсказке честная privacy-нотификация: индексы локальные, но
 *   query-text для embedding'а отправляется в OpenAI (provider name).
 */
export function KnowledgeBadge() {
  const { its, bsp, anyReady, bothReady, totalEntries, loading } =
    useKnowledgeStatus();
  const [open, setOpen] = useState(false);

  // Цвет статус-точки
  const dotClass = loading
    ? "bg-zinc-400 animate-pulse"
    : bothReady
      ? "bg-emerald-500"
      : anyReady
        ? "bg-amber-500"
        : "bg-zinc-500";

  // Текстовая компактная сводка: «ИТС 2543 · БСП 1820»
  const itsCount = its?.chunks ?? 0;
  const bspCount = bsp?.methods ?? 0;
  const labelParts: string[] = [];
  if (its?.enabled) labelParts.push(`ИТС ${itsCount}`);
  if (bsp?.enabled) labelParts.push(`БСП ${bspCount}`);
  const label = labelParts.length ? labelParts.join(" · ") : "База знаний";

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        className="flex items-center gap-2 rounded-md border border-zinc-800 bg-zinc-900/60 px-3 py-1.5 text-xs font-mono text-zinc-300 transition-colors hover:border-zinc-700 hover:text-zinc-100"
        aria-label="Статус локальной базы знаний"
        data-testid="knowledge-badge"
      >
        <span className={`h-2 w-2 rounded-full ${dotClass}`} aria-hidden />
        <span>{label}</span>
      </button>

      {open && (
        <div
          className="absolute right-0 top-full z-50 mt-2 w-80 rounded-lg border border-zinc-800 bg-zinc-950 p-4 text-xs shadow-2xl"
          role="tooltip"
          data-testid="knowledge-badge-popover"
        >
          <div className="mb-3 font-mono uppercase tracking-wider text-zinc-400">
            Локальная база знаний
          </div>

          {/* ИТС */}
          {its && (
            <div className="mb-3 border-l-2 border-emerald-500/60 pl-3">
              <div className="font-semibold text-zinc-100">ИТС-стандарты</div>
              <div className="mt-1 text-zinc-400">
                {its.enabled ? (
                  <>
                    {its.chunks} фрагментов из {its.documents} документов
                    <br />
                    {its.ready
                      ? "✓ готов к поиску"
                      : "⚠ embedding-провайдер не настроен"}
                  </>
                ) : (
                  <>отключён через настройки</>
                )}
              </div>
            </div>
          )}

          {/* БСП */}
          {bsp && (
            <div className="mb-3 border-l-2 border-amber-500/60 pl-3">
              <div className="font-semibold text-zinc-100">
                БСП Pattern Index
              </div>
              <div className="mt-1 text-zinc-400">
                {bsp.enabled ? (
                  <>
                    {bsp.methods} методов из {bsp.modules} модулей
                    {Object.keys(bsp.by_version).length > 0 && (
                      <>
                        <br />
                        Версии:{" "}
                        {Object.entries(bsp.by_version)
                          .map(([v, n]) => `${v} (${n})`)
                          .join(", ")}
                      </>
                    )}
                    <br />
                    {bsp.ready
                      ? "✓ готов к поиску"
                      : "⚠ embedding-провайдер не настроен"}
                  </>
                ) : (
                  <>отключён через настройки</>
                )}
              </div>
            </div>
          )}

          {totalEntries === 0 && (
            <div className="mb-3 text-zinc-500">
              Индексы пусты. Запустите{" "}
              <code className="rounded bg-zinc-800 px-1 text-zinc-300">
                POST /knowledge/its/reload
              </code>{" "}
              или{" "}
              <code className="rounded bg-zinc-800 px-1 text-zinc-300">
                POST /knowledge/bsp/reload
              </code>{" "}
              для индексации.
            </div>
          )}

          <div className="mt-3 border-t border-zinc-800 pt-3 text-zinc-500">
            <div className="mb-1 font-mono uppercase tracking-wider text-zinc-600">
              Privacy
            </div>
            Данные индексов хранятся локально в SQLite. Текст запроса при
            поиске отправляется в{" "}
            <span className="text-zinc-300">{its?.provider ?? "OpenAI"}</span>{" "}
            для генерации embedding-вектора.
          </div>
        </div>
      )}
    </div>
  );
}
