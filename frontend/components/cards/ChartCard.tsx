"use client";

/**
 * ChartCard — графики в ответах модели через Recharts.
 *
 * Модель встраивает в markdown fence ```chart\n{<spec>}\n``` с JSON-spec.
 * Markdown.tsx перехватывает блок с language=chart и рендерит ChartCard.
 *
 * Поддерживаются: bar, line, pie. Spec — строго типизирован, лишние поля
 * игнорируются. Безопасно — никакого dangerouslySetInnerHTML.
 */

import { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { AlertTriangle, BarChart3, ChevronDown, ChevronUp } from "lucide-react";

export type ChartType = "bar" | "line" | "pie";

export interface ChartSpec {
  /** Тип графика */
  type: ChartType;
  /** Заголовок (опционально) */
  title?: string;
  /** Подзаголовок (опционально) */
  description?: string;
  /** Имя оси категорий (для bar/line) — какой ключ data использовать как X */
  xKey?: string;
  /** Имена числовых полей которые рендерим (для bar/line). По умолчанию — все числовые кроме xKey. */
  yKeys?: string[];
  /** Имя поля метки сегмента (для pie) */
  nameKey?: string;
  /** Имя числового поля (для pie) */
  valueKey?: string;
  /** Данные — массив объектов */
  data: Array<Record<string, string | number>>;
}

// Палитра — синяя гамма accent + поддерживающие тона.
const PALETTE = [
  "#3b82f6", // blue-500 (наш accent)
  "#10b981", // emerald-500
  "#f59e0b", // amber-500
  "#ef4444", // red-500
  "#8b5cf6", // violet-500
  "#06b6d4", // cyan-500
  "#ec4899", // pink-500
  "#14b8a6", // teal-500
];

interface ChartCardProps {
  spec: ChartSpec;
}

/**
 * Парсит JSON-spec из текста ```chart```-блока.
 * Возвращает ChartSpec или null при ошибке.
 */
export function parseChartSpec(raw: string): ChartSpec | null {
  try {
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return null;
    const type = parsed.type;
    if (type !== "bar" && type !== "line" && type !== "pie") return null;
    if (!Array.isArray(parsed.data) || parsed.data.length === 0) return null;
    return parsed as ChartSpec;
  } catch {
    return null;
  }
}

function inferYKeys(spec: ChartSpec): string[] {
  if (spec.yKeys && spec.yKeys.length > 0) return spec.yKeys;
  if (spec.data.length === 0) return [];
  const first = spec.data[0];
  if (!first) return [];
  const x = spec.xKey;
  return Object.keys(first).filter(
    (k) => k !== x && typeof first[k] === "number",
  );
}

export function ChartCard({ spec }: ChartCardProps) {
  const [isOpen, setIsOpen] = useState(true);

  const yKeys = useMemo(() => inferYKeys(spec), [spec]);
  const xKey = spec.xKey ?? Object.keys(spec.data[0] ?? {})[0] ?? "name";

  // Защита от слишком большого payload — DoS guard.
  const safeData = spec.data.slice(0, 500);
  const isTruncated = spec.data.length > 500;

  function renderChart() {
    if (spec.type === "bar") {
      return (
        <BarChart data={safeData}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--bd-2)" />
          <XAxis dataKey={xKey} stroke="var(--fg-3)" fontSize={11} />
          <YAxis stroke="var(--fg-3)" fontSize={11} />
          <Tooltip
            contentStyle={{
              backgroundColor: "var(--bg-2)",
              border: "1px solid var(--bd-2)",
              borderRadius: 6,
              fontSize: 12,
            }}
          />
          {yKeys.length > 1 && <Legend wrapperStyle={{ fontSize: 11 }} />}
          {yKeys.map((key, i) => (
            <Bar
              key={key}
              dataKey={key}
              fill={PALETTE[i % PALETTE.length]}
              radius={[2, 2, 0, 0]}
            />
          ))}
        </BarChart>
      );
    }

    if (spec.type === "line") {
      return (
        <LineChart data={safeData}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--bd-2)" />
          <XAxis dataKey={xKey} stroke="var(--fg-3)" fontSize={11} />
          <YAxis stroke="var(--fg-3)" fontSize={11} />
          <Tooltip
            contentStyle={{
              backgroundColor: "var(--bg-2)",
              border: "1px solid var(--bd-2)",
              borderRadius: 6,
              fontSize: 12,
            }}
          />
          {yKeys.length > 1 && <Legend wrapperStyle={{ fontSize: 11 }} />}
          {yKeys.map((key, i) => (
            <Line
              key={key}
              type="monotone"
              dataKey={key}
              stroke={PALETTE[i % PALETTE.length]}
              strokeWidth={2}
              dot={{ r: 3 }}
            />
          ))}
        </LineChart>
      );
    }

    // pie
    const nameKey = spec.nameKey ?? xKey;
    const valueKey = spec.valueKey ?? yKeys[0] ?? "value";
    return (
      <PieChart>
        <Pie
          data={safeData}
          dataKey={valueKey}
          nameKey={nameKey}
          cx="50%"
          cy="50%"
          outerRadius={90}
          // recharts v4 типизирует PieLabelRenderProps через Required<...> без index-signature,
          // поэтому строгий Record<string, unknown> не подходит. Безопасно достаём поле по
          // динамическому ключу через unknown-каст — runtime-форма та же.
          label={(props) => {
            const entry = props as unknown as Record<string, unknown>;
            return String(entry[nameKey] ?? "");
          }}
          labelLine={false}
          fontSize={11}
        >
          {safeData.map((_, i) => (
            <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{
            backgroundColor: "var(--bg-2)",
            border: "1px solid var(--bd-2)",
            borderRadius: 6,
            fontSize: 12,
          }}
        />
      </PieChart>
    );
  }

  return (
    <div
      className="border border-[var(--bd-2)] rounded-md bg-[var(--bg-1)] my-2 animate-fade-up"
      data-testid="chart-card"
      data-chart-type={spec.type}
    >
      <button
        type="button"
        onClick={() => setIsOpen((v) => !v)}
        className="w-full flex items-start gap-2.5 px-3 py-3 border-b border-[var(--bd-1)] text-left hover:bg-[var(--bg-2)] transition-colors"
        aria-expanded={isOpen}
      >
        <div
          className="h-7 w-7 rounded-md inline-flex items-center justify-center bg-[var(--bg-2)] border border-[var(--bd-2)] flex-shrink-0 text-[var(--accent)]"
          aria-hidden="true"
        >
          <BarChart3 className="h-3.5 w-3.5" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="font-medium text-[var(--fg-1)] text-[13.5px] leading-tight">
            {spec.title ?? `График (${spec.type})`}
          </div>
          {spec.description && (
            <div className="text-xs text-[var(--fg-3)] mt-1">
              {spec.description}
            </div>
          )}
        </div>
        <span className="text-[var(--fg-3)] flex-shrink-0">
          {isOpen ? (
            <ChevronUp className="h-4 w-4" />
          ) : (
            <ChevronDown className="h-4 w-4" />
          )}
        </span>
      </button>
      {isOpen && (
        <div className="p-3 space-y-2">
          <div style={{ width: "100%", height: 280 }}>
            <ResponsiveContainer width="100%" height="100%">
              {renderChart()}
            </ResponsiveContainer>
          </div>
          {isTruncated && (
            <div className="flex items-center gap-1.5 text-xs text-[var(--fg-3)] pt-1">
              <AlertTriangle className="h-3 w-3 flex-shrink-0" />
              <span>Показаны первые 500 строк из {spec.data.length}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * Fallback при невалидном spec — показываем код блока с подсказкой.
 */
export function ChartCardError({ raw, error }: { raw: string; error: string }) {
  return (
    <div
      className="border border-[var(--bd-2)] rounded-md bg-[var(--bg-1)] my-2 p-3"
      data-testid="chart-card-error"
    >
      <div className="flex items-center gap-2 text-sm text-[var(--warning, #f59e0b)] mb-2">
        <AlertTriangle className="h-4 w-4" />
        <span>Не удалось распознать график: {error}</span>
      </div>
      <pre className="text-xs font-mono text-[var(--fg-3)] overflow-x-auto bg-[var(--bg-2)] p-2 rounded">
        {raw.slice(0, 500)}
      </pre>
    </div>
  );
}
