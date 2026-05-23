"use client";

import { ArrowLeft, BarChart3, Loader2, RefreshCw } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { fetchInsights } from "@/lib/api";
import { ThemeToggle } from "@/components/shell/ThemeToggle";
import { parseBackendDate } from "@/lib/utils";
import type { InsightsPeriod, InsightsResponse } from "@/lib/types";

const PERIODS: { key: InsightsPeriod; label: string }[] = [
  { key: "24h", label: "24ч" },
  { key: "7d", label: "7 дней" },
  { key: "30d", label: "30 дней" },
  { key: "all", label: "Всё время" },
];

/**
 * Sprint 4 (Hermes G8 lite): Insights dashboard.
 *
 * Token/cost ещё не считаются (нет учёта в LLM-клиенте) — показываем что есть:
 * sessions, messages, tool calls/errors, avg duration, top channels, top tools.
 */
export default function InsightsPage() {
  const [period, setPeriod] = useState<InsightsPeriod>("7d");
  const [data, setData] = useState<InsightsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async (p: InsightsPeriod) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchInsights(p);
      setData(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось загрузить");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload(period);
  }, [period, reload]);

  return (
    <div className="max-w-4xl mx-auto p-6 pb-24">
      <Header />

      {/* Period switcher */}
      <div className="mt-6 flex items-center gap-2">
        {PERIODS.map((p) => (
          <button
            key={p.key}
            type="button"
            onClick={() => setPeriod(p.key)}
            className={`px-3 h-8 rounded-md border text-[12px] transition-colors ${
              period === p.key
                ? "border-[var(--accent)] bg-[var(--accent-12)] text-[var(--accent)]"
                : "border-[var(--bd-2)] bg-[var(--bg-1)] text-[var(--fg-2)] hover:bg-[var(--bg-2)]"
            }`}
          >
            {p.label}
          </button>
        ))}
        <button
          type="button"
          onClick={() => reload(period)}
          disabled={loading}
          aria-label="Обновить"
          className="ml-auto p-1.5 rounded-md text-[var(--fg-3)] hover:text-[var(--fg-1)] hover:bg-[var(--bg-2)] transition-colors disabled:opacity-50"
        >
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
        </button>
      </div>

      {error && (
        <div className="mt-4 p-3 rounded-md border border-[var(--error-40)] bg-[var(--error-12)] text-[13px] text-[var(--error)]">
          {error}
        </div>
      )}

      {loading && !data ? (
        <div className="mt-6 flex items-center gap-2 text-[var(--fg-3)]">
          <Loader2 className="h-4 w-4 animate-spin" />
          Загрузка...
        </div>
      ) : data ? (
        <>
          {/* KPI cards */}
          <div className="mt-6 grid grid-cols-4 gap-3">
            <Kpi label="Сессий" value={data.sessions} />
            <Kpi label="Сообщений" value={data.messages} />
            <Kpi label="Запросов к 1С" value={data.tool_calls_total} />
            <Kpi
              label="Ошибок"
              value={data.tool_errors_total}
              accent={data.tool_errors_total > 0 ? "warning" : "default"}
            />
          </div>

          {/* Sprint 5 (I4): Token + cost KPI */}
          <div className="mt-3 grid grid-cols-2 gap-3">
            <KpiText
              label="Токенов (оценка)"
              value={
                data.estimated_tokens > 0
                  ? data.estimated_tokens.toLocaleString("ru-RU")
                  : "—"
              }
            />
            <KpiText
              label="Стоимость, USD (оценка)"
              value={
                data.estimated_cost_usd > 0
                  ? "$" + data.estimated_cost_usd.toFixed(4)
                  : "—"
              }
            />
          </div>

          {data.avg_duration_ms !== null && (
            <div className="mt-3 p-3 rounded-md border border-[var(--bd-2)] bg-[var(--bg-1)]">
              <span className="text-[12px] text-[var(--fg-3)] uppercase tracking-[0.1em]">
                Среднее время ответа 1С
              </span>{" "}
              <span
                className="text-[14px] text-[var(--fg-1)] tabular-nums"
                style={{ fontFamily: "var(--font-jb-mono), monospace" }}
              >
                {data.avg_duration_ms} мс
              </span>
            </div>
          )}

          {/* Top tools */}
          <section className="mt-8">
            <h2 className="text-[15px] font-semibold text-[var(--fg-1)] mb-3">
              Топ операций с базой 1С
            </h2>
            {data.top_tools.length === 0 ? (
              <EmptyState text="Пока нет данных по обращениям к 1С" />
            ) : (
              <div className="rounded-md border border-[var(--bd-2)] bg-[var(--bg-1)] overflow-hidden">
                <table
                  className="w-full text-[13px]"
                  style={{ fontFamily: "var(--font-jb-mono), monospace" }}
                >
                  <thead>
                    <tr className="border-b border-[var(--bd-2)] text-[var(--fg-3)]">
                      <th className="text-left p-3 font-normal text-[11px] uppercase tracking-[0.12em]">
                        Операция
                      </th>
                      <th className="text-right p-3 font-normal text-[11px] uppercase tracking-[0.12em]">
                        Вызовов
                      </th>
                      <th className="text-right p-3 font-normal text-[11px] uppercase tracking-[0.12em]">
                        Ошибок
                      </th>
                      <th className="text-right p-3 font-normal text-[11px] uppercase tracking-[0.12em]">
                        Доля ошибок
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.top_tools.map((tool) => (
                      <tr
                        key={tool.name}
                        className="border-b border-[var(--bd-2)] last:border-b-0"
                      >
                        <td className="p-3 text-[var(--fg-1)] tabular-nums">{tool.name}</td>
                        <td className="p-3 text-right text-[var(--fg-2)] tabular-nums">
                          {tool.calls}
                        </td>
                        <td
                          className={`p-3 text-right tabular-nums ${
                            tool.errors > 0
                              ? "text-[var(--warning)]"
                              : "text-[var(--fg-3)]"
                          }`}
                        >
                          {tool.errors}
                        </td>
                        <td className="p-3 text-right text-[var(--fg-3)] tabular-nums">
                          {(tool.error_rate * 100).toFixed(1)}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          {/* Top channels (база 1С) */}
          <section className="mt-8">
            <h2 className="text-[15px] font-semibold text-[var(--fg-1)] mb-3">
              Топ баз 1С
            </h2>
            {data.top_channels.length === 0 ? (
              <EmptyState text="Пока нет активных сессий" />
            ) : (
              <div className="rounded-md border border-[var(--bd-2)] bg-[var(--bg-1)] overflow-hidden">
                <table
                  className="w-full text-[13px]"
                  style={{ fontFamily: "var(--font-jb-mono), monospace" }}
                >
                  <thead>
                    <tr className="border-b border-[var(--bd-2)] text-[var(--fg-3)]">
                      <th className="text-left p-3 font-normal text-[11px] uppercase tracking-[0.12em]">
                        База
                      </th>
                      <th className="text-right p-3 font-normal text-[11px] uppercase tracking-[0.12em]">
                        Сессий
                      </th>
                      <th className="text-right p-3 font-normal text-[11px] uppercase tracking-[0.12em]">
                        Сообщений
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.top_channels.map((ch) => (
                      <tr
                        key={ch.channel_id}
                        className="border-b border-[var(--bd-2)] last:border-b-0"
                      >
                        <td className="p-3 text-[var(--fg-1)] tabular-nums truncate max-w-[400px]">
                          {ch.channel_id}
                        </td>
                        <td className="p-3 text-right text-[var(--fg-2)] tabular-nums">
                          {ch.sessions}
                        </td>
                        <td className="p-3 text-right text-[var(--fg-2)] tabular-nums">
                          {ch.messages}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          {/* Footer note */}
          <div className="mt-8 text-[11px] text-[var(--fg-4)]">
            Сгенерировано: {parseBackendDate(data.generated_at).toLocaleString("ru-RU")}
          </div>
        </>
      ) : null}
    </div>
  );
}

function Header() {
  return (
    <div className="flex items-center gap-3">
      <Link
        href="/"
        className="text-[var(--fg-3)] hover:text-[var(--fg-1)] transition-colors flex items-center gap-1 text-sm"
      >
        <ArrowLeft size={16} />
        Назад
      </Link>
      <h1
        className="flex items-center gap-2 text-lg font-semibold text-[var(--fg-1)]"
        style={{ fontFamily: "var(--font-plex-sans), system-ui" }}
      >
        <BarChart3 className="h-5 w-5 text-[var(--accent)]" />
        Аналитика
      </h1>
      <div className="ml-auto">
        <ThemeToggle />
      </div>
    </div>
  );
}

function KpiText({ label, value }: { label: string; value: string }) {
  return (
    <div className="p-4 rounded-md border border-[var(--bd-2)] bg-[var(--bg-1)]">
      <div className="text-[10.5px] uppercase tracking-[0.14em] text-[var(--fg-3)]">
        {label}
      </div>
      <div
        className="mt-2 text-[20px] font-semibold text-[var(--fg-1)] tabular-nums"
        style={{ fontFamily: "var(--font-jb-mono), monospace" }}
      >
        {value}
      </div>
    </div>
  );
}

function Kpi({
  label,
  value,
  accent = "default",
}: {
  label: string;
  value: number;
  accent?: "default" | "warning";
}) {
  return (
    <div className="p-4 rounded-md border border-[var(--bd-2)] bg-[var(--bg-1)]">
      <div className="text-[10.5px] uppercase tracking-[0.14em] text-[var(--fg-3)]">
        {label}
      </div>
      <div
        className={`mt-2 text-[28px] font-semibold tabular-nums ${
          accent === "warning" ? "text-[var(--warning)]" : "text-[var(--fg-1)]"
        }`}
        style={{ fontFamily: "var(--font-jb-mono), monospace" }}
      >
        {value}
      </div>
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return (
    <div className="p-6 rounded-md border border-[var(--bd-2)] bg-[var(--bg-1)] text-center text-[var(--fg-3)] text-[13px]">
      {text}
    </div>
  );
}
