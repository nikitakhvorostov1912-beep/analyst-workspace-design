"use client";

import { useEffect, useState } from "react";
import { Sparkles, BookOpen, AlertCircle, SearchX } from "lucide-react";
import {
  fetchTypicalObject,
  TypicalObjectNotFoundError,
  type TypicalObjectCardPayload,
  type TypicalObjectResponse,
} from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * M-K2.5.7 TypicalObjectCard — карточка объекта типовой в чат-потоке.
 *
 * Появляется когда LLM вызвал `explain_typical_object` и tool_result
 * содержит ссылку на объект типовой. Загружает full payload с backend
 * по channel_id + qualified_name.
 *
 * Структура:
 * - Header: kind + name + версия типовой
 * - Summary + Purpose (1-2 параграфа, всегда видны)
 * - Свёрнуто по умолчанию: key_attributes / movements / posting_flow /
 *   typical_scenarios / preconditions / related_objects
 *
 * Отличия от ObjectCard (клиентская база):
 * - Источник — карточка LLM, не MCP get_metadata
 * - Нет deanonymize (типовые публичны)
 * - Есть warning «сгенерировано LLM» если status=generated (а не embedded)
 */

interface TypicalObjectCardProps {
  channelId: string;
  objectQualifiedName: string;
}

const KIND_LABELS: Record<string, string> = {
  Document: "Документ",
  Catalog: "Справочник",
  Enum: "Перечисление",
  AccumulationRegister: "Регистр накопления",
  InformationRegister: "Регистр сведений",
  AccountingRegister: "Регистр бухгалтерии",
  CalculationRegister: "Регистр расчёта",
  ChartOfAccounts: "План счетов",
  CommonModule: "Общий модуль",
  Report: "Отчёт",
  DataProcessor: "Обработка",
};

function kindLabel(kind: string): string {
  return KIND_LABELS[kind] ?? kind;
}

export function TypicalObjectCard({
  channelId,
  objectQualifiedName,
}: TypicalObjectCardProps) {
  const [state, setState] = useState<
    | { kind: "loading" }
    | { kind: "loaded"; data: TypicalObjectResponse }
    | { kind: "error"; message: string }
    | {
        kind: "not_found";
        hint: string;
        suggestions: Array<{ qualified_name: string; kind: string; score: string }>;
      }
  >({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    setState({ kind: "loading" });

    async function load() {
      try {
        const data = await fetchTypicalObject(channelId, objectQualifiedName);
        if (!cancelled) {
          setState({ kind: "loaded", data });
        }
      } catch (err) {
        if (cancelled) return;
        // M-K2.5.9.7: not_found state с suggestions.
        if (err instanceof TypicalObjectNotFoundError) {
          setState({
            kind: "not_found",
            hint: err.hint,
            suggestions: err.suggestions,
          });
          return;
        }
        setState({
          kind: "error",
          message: err instanceof Error ? err.message : "Ошибка загрузки",
        });
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [channelId, objectQualifiedName]);

  if (state.kind === "loading") {
    return (
      <div
        className="border border-[var(--bd-2)] bg-[var(--bg-2)] rounded-md p-3 text-[12px] text-[var(--fg-3)]"
        data-testid="typical-object-card-loading"
      >
        Загружаю карточку {objectQualifiedName}…
      </div>
    );
  }

  if (state.kind === "error") {
    return (
      <div
        className="border border-[var(--error-40)] bg-[var(--error-12)] rounded-md p-3 text-[12px] text-[var(--error)] flex items-start gap-2"
        data-testid="typical-object-card-error"
      >
        <AlertCircle className="h-3.5 w-3.5 flex-none mt-0.5" />
        <div>{state.message}</div>
      </div>
    );
  }

  if (state.kind === "not_found") {
    return (
      <div
        className="border border-[var(--bd-2)] bg-[var(--bg-2)] rounded-md overflow-hidden"
        data-testid="typical-object-card-not-found"
      >
        <div className="flex items-start gap-2 px-3 py-2 border-b border-[var(--bd-2)] bg-[var(--bg-3)]">
          <SearchX className="h-3.5 w-3.5 flex-none mt-0.5 text-[var(--fg-3)]" />
          <div className="flex-1 min-w-0">
            <div
              className="text-[10px] tracking-[0.16em] uppercase text-[var(--fg-3)]"
              style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
            >
              Объект не найден
            </div>
            <div
              className="font-semibold text-[13px] mt-0.5 truncate"
              style={{
                fontFamily: "var(--font-plex-mono), 'IBM Plex Mono', ui-monospace, monospace",
              }}
            >
              {objectQualifiedName}
            </div>
          </div>
        </div>
        <div className="px-3 py-3 space-y-2 text-[12px]">
          <p className="text-[var(--fg-2)] leading-relaxed">{state.hint}</p>
          {state.suggestions.length > 0 ? (
            <div className="space-y-1">
              <div
                className="text-[10px] tracking-[0.14em] uppercase text-[var(--fg-3)]"
                style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
              >
                Возможно вы имели в виду
              </div>
              <ul className="space-y-0.5" data-testid="typical-not-found-suggestions">
                {state.suggestions.map((s, i) => (
                  <li
                    key={i}
                    className="font-mono text-[11px] text-[var(--fg-1)] truncate"
                    style={{
                      fontFamily:
                        "var(--font-plex-mono), 'IBM Plex Mono', ui-monospace, monospace",
                    }}
                  >
                    {s.qualified_name}
                    <span className="text-[var(--fg-4)]"> ({s.kind})</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <div className="text-[11px] text-[var(--fg-3)] italic">
              Похожих объектов не нашлось. Проверь точное написание имени.
            </div>
          )}
        </div>
      </div>
    );
  }

  const { data } = state;
  const card = data.card;
  const isStub = data.card_status !== "embedded";
  // M-K2.5.9.2: бейдж + warning когда карточка mock-сгенерирована.
  // Mock-карточки приоритетней isStub warning, потому что mock — это
  // production-блокер ("данные не верифицированы экспертом"), а isStub —
  // только статус embedding pipeline.
  const isMock = data.is_mock === true;

  return (
    <div
      className="border border-[var(--bd-2)] bg-[var(--bg-2)] rounded-md overflow-hidden"
      data-testid="typical-object-card"
    >
      {/* Header */}
      <div className="flex items-start gap-2 px-3 py-2 border-b border-[var(--bd-2)] bg-[var(--bg-3)]">
        <Sparkles className="h-3.5 w-3.5 flex-none mt-0.5 text-[var(--accent)]" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span
              className="text-[10px] tracking-[0.16em] uppercase text-[var(--fg-3)]"
              style={{
                fontFamily: "var(--font-jb-mono), ui-monospace, monospace",
              }}
            >
              Типовая
            </span>
            <span
              className="px-1.5 py-[1px] rounded text-[9px] tracking-[0.14em] uppercase font-medium border bg-[var(--accent-12)] text-[var(--accent)] border-[var(--accent-32)]"
              style={{
                fontFamily: "var(--font-jb-mono), ui-monospace, monospace",
              }}
            >
              {kindLabel(data.object_kind)}
            </span>
            {isMock && (
              <span
                data-testid="typical-card-mock-badge"
                className="px-1.5 py-[1px] rounded text-[9px] tracking-[0.14em] uppercase font-medium border bg-[var(--warning-12)] text-[var(--warning)] border-[var(--warning-40)]"
                style={{
                  fontFamily: "var(--font-jb-mono), ui-monospace, monospace",
                }}
                title="Карточка сгенерирована mock-LLM, не верифицирована экспертом"
              >
                MOCK DATA
              </span>
            )}
          </div>
          <div
            className="font-semibold text-[14px] mt-1 truncate"
            style={{
              fontFamily:
                "var(--font-plex-mono), 'IBM Plex Mono', ui-monospace, monospace",
            }}
          >
            {data.name || data.object_qualified_name}
          </div>
          {data.comment && (
            <div className="text-[11px] text-[var(--fg-3)] mt-0.5 italic">
              {data.comment}
            </div>
          )}
        </div>
      </div>

      {/* Card body */}
      {card === null ? (
        <div className="px-3 py-3 text-[12px] text-[var(--fg-3)] flex items-start gap-2">
          <BookOpen className="h-3.5 w-3.5 flex-none mt-0.5" />
          <div>
            Карточка ещё не сгенерирована (статус:{" "}
            <span className="font-mono">{data.card_status}</span>). Бот покажет
            только структуру графа.
          </div>
        </div>
      ) : (
        <div className="px-3 py-3 space-y-3 text-[13px]">
          {card.summary && (
            <p className="text-[var(--fg-1)] leading-relaxed">
              {card.summary}
            </p>
          )}
          {card.purpose && (
            <p className="text-[var(--fg-2)] leading-relaxed">{card.purpose}</p>
          )}

          {isMock ? (
            <div
              data-testid="typical-card-mock-warning"
              className="flex items-start gap-2 text-[11px] text-[var(--warning)] bg-[var(--warning-12)] border border-[var(--warning-40)] rounded px-2 py-1"
            >
              <AlertCircle className="h-3 w-3 flex-none mt-0.5" />
              <span>
                <strong>Mock data — не верифицировано экспертом.</strong>{" "}
                Карточка сгенерирована детерминированным stub-LLM
                (mock-generator-v1) для smoke-режима. Текст summary / purpose —
                stub; структуру (key_attributes / movements) сверяй с графом.
              </span>
            </div>
          ) : (
            isStub && (
              <div className="flex items-start gap-2 text-[11px] text-[var(--warning)] bg-[var(--warning-12)] border border-[var(--warning-40)] rounded px-2 py-1">
                <AlertCircle className="h-3 w-3 flex-none mt-0.5" />
                <span>
                  Карточка сгенерирована LLM, не верифицирована экспертом
                  (статус: {data.card_status})
                </span>
              </div>
            )
          )}

          <TypicalCardSection title="Ключевые реквизиты" count={card.key_attributes.length}>
            {card.key_attributes.length === 0 ? (
              <EmptyText>—</EmptyText>
            ) : (
              <ul className="space-y-1">
                {card.key_attributes.map((a, i) => (
                  <li key={i} className="text-[12px]">
                    <span
                      className="font-semibold"
                      style={{
                        fontFamily:
                          "var(--font-plex-mono), 'IBM Plex Mono', ui-monospace, monospace",
                      }}
                    >
                      {a.name}
                    </span>
                    {a.role && (
                      <span className="text-[var(--fg-3)]"> — {a.role}</span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </TypicalCardSection>

          <TypicalCardSection title="Движения регистров" count={card.movements.length}>
            {card.movements.length === 0 ? (
              <EmptyText>Объект не делает движения регистров</EmptyText>
            ) : (
              <ul className="space-y-1.5">
                {card.movements.map((m, i) => (
                  <li key={i} className="text-[12px] flex items-start gap-2">
                    <span
                      className={cn(
                        "px-1.5 py-[1px] rounded text-[9px] tracking-[0.14em] uppercase font-medium flex-none",
                        m.direction === "приход"
                          ? "bg-[var(--success-12)] text-[var(--success)] border border-[var(--success-32)]"
                          : m.direction === "расход"
                            ? "bg-[var(--warning-12)] text-[var(--warning)] border border-[var(--warning-40)]"
                            : "bg-[var(--bg-3)] text-[var(--fg-2)] border border-[var(--bd-2)]",
                      )}
                      style={{
                        fontFamily:
                          "var(--font-jb-mono), ui-monospace, monospace",
                      }}
                    >
                      {m.direction || "?"}
                    </span>
                    <div className="flex-1 min-w-0">
                      <div
                        className="font-mono text-[11px] truncate"
                        style={{
                          fontFamily:
                            "var(--font-plex-mono), 'IBM Plex Mono', ui-monospace, monospace",
                        }}
                      >
                        {m.register}
                      </div>
                      {m.condition && (
                        <div className="text-[11px] text-[var(--fg-3)]">
                          {m.condition}
                        </div>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </TypicalCardSection>

          <TypicalCardSection title="Поток проведения" count={card.posting_flow.length}>
            {card.posting_flow.length === 0 ? (
              <EmptyText>—</EmptyText>
            ) : (
              <ol className="space-y-0.5 list-decimal pl-5 text-[12px]">
                {card.posting_flow.map((step, i) => (
                  <li key={i}>{step}</li>
                ))}
              </ol>
            )}
          </TypicalCardSection>

          <TypicalCardSection title="Типичные сценарии" count={card.typical_scenarios.length}>
            {card.typical_scenarios.length === 0 ? (
              <EmptyText>—</EmptyText>
            ) : (
              <ul className="list-disc pl-5 space-y-0.5 text-[12px]">
                {card.typical_scenarios.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            )}
          </TypicalCardSection>

          <TypicalCardSection title="Предусловия" count={card.preconditions.length}>
            {card.preconditions.length === 0 ? (
              <EmptyText>—</EmptyText>
            ) : (
              <ul className="list-disc pl-5 space-y-0.5 text-[12px]">
                {card.preconditions.map((p, i) => (
                  <li key={i}>{p}</li>
                ))}
              </ul>
            )}
          </TypicalCardSection>

          <TypicalCardSection title="Связанные объекты" count={card.related_objects.length}>
            {card.related_objects.length === 0 ? (
              <EmptyText>—</EmptyText>
            ) : (
              <ul className="space-y-0.5 text-[12px]">
                {card.related_objects.map((r, i) => (
                  <li
                    key={i}
                    className="font-mono text-[11px] text-[var(--fg-2)]"
                    style={{
                      fontFamily:
                        "var(--font-plex-mono), 'IBM Plex Mono', ui-monospace, monospace",
                    }}
                  >
                    {r}
                  </li>
                ))}
              </ul>
            )}
          </TypicalCardSection>
        </div>
      )}
    </div>
  );
}

function TypicalCardSection({
  title,
  count,
  children,
  defaultOpen = false,
}: {
  title: string;
  count: number;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  return (
    <details
      open={defaultOpen}
      className="group border border-[var(--bd-1)] rounded"
    >
      <summary className="flex cursor-pointer select-none items-center justify-between px-2.5 py-1.5 hover:bg-[var(--bg-hover)] list-none">
        <span
          className="text-[10px] tracking-[0.14em] uppercase font-medium text-[var(--fg-2)]"
          style={{
            fontFamily: "var(--font-jb-mono), ui-monospace, monospace",
          }}
        >
          {title}
        </span>
        <span className="text-[10px] text-[var(--fg-4)]">{count}</span>
      </summary>
      <div className="px-2.5 pb-2.5 pt-1">{children}</div>
    </details>
  );
}

function EmptyText({ children }: { children: React.ReactNode }) {
  return (
    <div className="text-[11px] text-[var(--fg-4)] italic">{children}</div>
  );
}
