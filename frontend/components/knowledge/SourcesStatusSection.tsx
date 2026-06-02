"use client";

import { Database, Boxes, BookMarked } from "lucide-react";

import { useSourcesStatus, type SourceState } from "@/hooks/useSourcesStatus";

/**
 * Секция «Источники знаний» для страницы /status.
 *
 * Показывает live-статус трёх источников, из которых грунтятся ответы:
 * База (живая 1С), Типовая (граф+карточки), ИТС (живой Напарник).
 * До этого /status покрывала только подключения 1С + bsl-context — про
 * Напарника и типовую пользователь узнать не мог.
 */

const DOT: Record<SourceState, string> = {
  ready: "bg-[var(--success)]",
  down: "bg-[var(--error)]",
  unknown: "bg-[var(--warning)] animate-pulse",
  disabled: "bg-[var(--fg-4)]",
};

const WORD: Record<SourceState, string> = {
  ready: "Готов",
  down: "Недоступен",
  unknown: "Проверка",
  disabled: "Выключен",
};

export function SourcesStatusSection() {
  const { base, typical, its, loading } = useSourcesStatus();

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
    <div className="mb-6">
      <div
        className="text-[10px] tracking-[0.18em] uppercase text-[var(--fg-3)] mb-2"
        style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
      >
        Источники знаний
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {rows.map((r) => {
          const Icon = r.icon;
          const state = loading ? "unknown" : r.info.state;
          return (
            <div
              key={r.key}
              className="rounded-lg border border-[var(--bd-2)] bg-[var(--bg-1)] p-3.5"
            >
              <div className="flex items-center gap-2 mb-1.5">
                <Icon className="h-4 w-4 text-[var(--accent)]" />
                <span className="text-[13px] font-semibold text-[var(--fg-1)]">
                  {r.title}
                </span>
                <span className="ml-auto flex items-center gap-1">
                  <span className={`h-2 w-2 rounded-full ${DOT[state]}`} />
                  <span className="text-[10px] uppercase tracking-wide text-[var(--fg-3)]">
                    {WORD[state]}
                  </span>
                </span>
              </div>
              <div className="text-[11.5px] text-[var(--fg-3)] mb-1.5">
                {loading ? "проверяю…" : r.info.detail}
              </div>
              <div className="text-[11.5px] text-[var(--fg-2)] leading-snug">
                Спросить: {r.ask}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
