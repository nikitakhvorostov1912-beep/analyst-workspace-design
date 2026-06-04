"use client";

import type { ReactNode } from "react";
import dynamic from "next/dynamic";
import { TableCard } from "./TableCard";
import { ObjectCard } from "./ObjectCard";
import { LogCard } from "./LogCard";
import { MetricCard } from "./MetricCard";
import { ReferencesCard } from "./ReferencesCard";
import { CodeCard } from "./CodeCard";
import { deanonymizeCard, loadMoreLogEntries } from "@/lib/api";

// H-06 (Web Vitals): GraphCard тянет @xyflow/react (~150 KB gzip) + CSS. Карточки
// типа "graph" появляются редко (граф = backend grounding), поэтому грузим
// компонент лениво — он не попадает в initial bundle для всех остальных сессий.
const GraphCard = dynamic(() => import("./GraphCard").then((m) => m.GraphCard), {
  ssr: false,
  loading: () => (
    <div className="rounded-lg border border-[var(--bd-1)] bg-[var(--bg-1)] p-3 text-xs text-[var(--fg-3)]">
      Загрузка графа…
    </div>
  ),
});
import type { CardEnvelope, CardContext, ReferenceItem } from "@/lib/types";

interface CardRendererProps {
  card: CardEnvelope;
  /** Контекст для load-more, deanonymize и curl-copy (Plan 03-04, 04-01) */
  context?: CardContext;
  /** Callback для отправки нового сообщения (для ReferencesCard click) */
  sendMessage?: (text: string) => void;
}

/**
 * Phase 11.5 / emil-design-eng: карточка «раскрывается» сверху вниз через
 * clip-path (wipe без искажения контента) на mount после streaming partial →
 * final. См. .card-reveal в design-tokens.css.
 */
function CardMountWrapper({ children }: { children: ReactNode }) {
  return <div className="card-reveal">{children}</div>;
}

export function CardRenderer({ card, context, sendMessage }: CardRendererProps) {
  // Формируем onDeanonymize если есть card_id и context (Plan 04-01)
  function makeOnDeanonymize(cardId: string | null | undefined) {
    if (!cardId || !context?.sessionId || !context?.messageId) return undefined;
    const sid = context.sessionId;
    const mid = context.messageId;
    return (tokens: string[]) => deanonymizeCard(sid, mid, cardId, tokens);
  }

  switch (card.type) {
    case "table":
      return (
        <CardMountWrapper>
          <TableCard
            payload={card.payload}
            onDeanonymize={makeOnDeanonymize(card.payload.card_id)}
          />
        </CardMountWrapper>
      );
    case "object":
      return (
        <CardMountWrapper>
          <ObjectCard
            payload={card.payload}
            onDeanonymize={makeOnDeanonymize(card.payload.card_id)}
          />
        </CardMountWrapper>
      );
    case "log": {
      // Формируем onLoadMore только если есть card_id и context
      const logPayload = card.payload;
      const cardId = logPayload.card_id;
      let onLoadMore: ((cursor: string) => Promise<{ entries: import("@/lib/types").LogEntry[]; next_cursor: string | null }>) | undefined;

      if (cardId && context?.sessionId && context?.messageId) {
        const sid = context.sessionId;
        const mid = context.messageId;
        onLoadMore = (cursor: string) => loadMoreLogEntries(sid, mid, cardId, cursor);
      }

      return (
        <CardMountWrapper>
          <LogCard
            payload={logPayload}
            onLoadMore={onLoadMore}
            onDeanonymize={makeOnDeanonymize(cardId)}
          />
        </CardMountWrapper>
      );
    }
    case "metric":
      return (
        <CardMountWrapper>
          <MetricCard
            payload={card.payload}
            onDeanonymize={makeOnDeanonymize(card.payload.card_id)}
          />
        </CardMountWrapper>
      );
    case "references": {
      const onLinkClick = sendMessage
        ? (item: ReferenceItem) => sendMessage(`Покажи ${item.name}`)
        : undefined;
      return (
        <CardMountWrapper>
          <ReferencesCard
            payload={card.payload}
            onLinkClick={onLinkClick}
          />
        </CardMountWrapper>
      );
    }
    case "code":
      return (
        <CardMountWrapper>
          <CodeCard payload={card.payload} />
        </CardMountWrapper>
      );
    case "graph":
      return (
        <CardMountWrapper>
          <GraphCard payload={card.payload} />
        </CardMountWrapper>
      );
    default: {
      // TypeScript narrowing исчерпан — runtime защита для неизвестных типов
      const unknown = card as { type: string; payload: unknown };
      return (
        <CardMountWrapper>
          <div className="rounded-lg border border-[var(--bd-1)] bg-[var(--bg-1)] p-3">
            <p className="text-xs text-[var(--fg-3)] mb-2">
              Неизвестный тип карточки: {unknown.type}
            </p>
            <pre className="text-xs font-mono text-[var(--fg-1)] overflow-x-auto">
              {JSON.stringify(unknown.payload, null, 2).slice(0, 500)}
            </pre>
          </div>
        </CardMountWrapper>
      );
    }
  }
}
