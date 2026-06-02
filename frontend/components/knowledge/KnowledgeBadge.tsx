"use client";

import { useState } from "react";
import Link from "next/link";
import { Database, Boxes, BookMarked } from "lucide-react";

import { useSourcesStatus, type SourceState } from "@/hooks/useSourcesStatus";

/**
 * Бейдж «Источники знаний» в шапке.
 *
 * Заменил прежний «ИТС N · БСП N» (он показывал только статический RAG и врал
 * «ИТС 0» при живом Напарнике). Теперь — три источника, из которых продукт
 * грунтит ответы, с честным live-статусом:
 *   • База     — активное подключение к живой 1С
 *   • Типовая  — граф + карточки типовых конфигураций
 *   • ИТС       — живой 1С:Напарник (или локальный RAG как fallback)
 *
 * Hover/click → попап с пояснением каждого источника, статусом и тем,
 * что через него можно спрашивать. Ссылка на /status и /guide.
 */

const DOT_CLASS: Record<SourceState, string> = {
  ready: "bg-[var(--success)]",
  down: "bg-[var(--error)]",
  unknown: "bg-[var(--warning)] animate-pulse",
  disabled: "bg-[var(--fg-4)]",
};

const STATE_WORD: Record<SourceState, string> = {
  ready: "готов",
  down: "недоступен",
  unknown: "проверка",
  disabled: "выключен",
};

export function KnowledgeBadge() {
  const { base, typical, its, itsStatic, bspStatic, loading } = useSourcesStatus();
  const [open, setOpen] = useState(false);

  const rows = [
    {
      key: "base",
      icon: Database,
      title: "Ваша база 1С",
      ask: "конкретные данные, структура, журнал регистрации",
      info: base,
    },
    {
      key: "typical",
      icon: Boxes,
      title: "Типовая конфигурация",
      ask: "как устроена УТ / ERP / КА / БП — движения, цепочки, реквизиты",
      info: typical,
    },
    {
      key: "its",
      icon: BookMarked,
      title: "ИТС · Напарник",
      ask: "методики, стандарты, инструкции 1С (живая документация)",
      info: its,
    },
  ];

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        className="flex items-center gap-2 rounded-md border border-[var(--bd-2)] bg-[var(--bg-2)] px-2.5 py-1.5 text-[11px] font-mono text-[var(--fg-2)] transition-colors hover:border-[var(--bd-3)] hover:text-[var(--fg-1)]"
        style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
        aria-label="Статус источников знаний"
        data-testid="knowledge-badge"
      >
        <span className="flex items-center gap-1" aria-hidden>
          {rows.map((r) => (
            <span
              key={r.key}
              className={`h-2 w-2 rounded-full ${loading ? "bg-[var(--fg-4)] animate-pulse" : DOT_CLASS[r.info.state]}`}
            />
          ))}
        </span>
        <span className="tracking-[0.08em] uppercase">Источники</span>
      </button>

      {open && (
        <div
          className="absolute right-0 top-full z-50 mt-2 w-[340px] rounded-lg border border-[var(--bd-2)] bg-[var(--bg-1)] p-4 text-xs shadow-2xl"
          role="tooltip"
          data-testid="knowledge-badge-popover"
        >
          <div
            className="mb-3 font-mono uppercase tracking-[0.14em] text-[var(--fg-3)] text-[10px]"
            style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
          >
            Источники знаний · откуда берутся ответы
          </div>

          <div className="space-y-3">
            {rows.map((r) => {
              const Icon = r.icon;
              return (
                <div key={r.key} className="flex gap-2.5">
                  <Icon className="h-4 w-4 flex-shrink-0 mt-0.5 text-[var(--accent)]" />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-[13px] text-[var(--fg-1)]">
                        {r.title}
                      </span>
                      <span className="flex items-center gap-1 ml-auto">
                        <span className={`h-1.5 w-1.5 rounded-full ${DOT_CLASS[r.info.state]}`} />
                        <span className="text-[10px] uppercase tracking-wide text-[var(--fg-3)]">
                          {STATE_WORD[r.info.state]}
                        </span>
                      </span>
                    </div>
                    <div className="text-[11px] text-[var(--fg-3)] mt-0.5">{r.info.detail}</div>
                    <div className="text-[11.5px] text-[var(--fg-2)] mt-1 leading-snug">
                      Спросить: {r.ask}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Детали статического RAG (для технического пользователя) */}
          {(itsStatic || bspStatic) && (
            <div className="mt-3 border-t border-[var(--bd-1)] pt-2.5 text-[10.5px] text-[var(--fg-3)] leading-relaxed">
              Локальный RAG: ИТС {itsStatic?.chunks ?? 0} фрагм. · БСП{" "}
              {bspStatic?.methods ?? 0} методов. Текст запроса при поиске уходит в{" "}
              <span className="text-[var(--fg-2)]">{itsStatic?.provider ?? "OpenAI"}</span>{" "}
              для embedding-вектора.
            </div>
          )}

          <div className="mt-3 flex items-center justify-between border-t border-[var(--bd-1)] pt-2.5">
            <Link
              href="/status"
              className="text-[11px] text-[var(--accent)] hover:underline"
            >
              Диагностика →
            </Link>
            <Link
              href="/guide"
              className="text-[11px] text-[var(--accent)] hover:underline"
            >
              Как это работает →
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
