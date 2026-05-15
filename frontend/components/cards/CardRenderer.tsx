"use client";

import { TableCard } from "./TableCard";
import { ObjectCard } from "./ObjectCard";
import { LogCard } from "./LogCard";
import { deanonymizeCard, loadMoreLogEntries } from "@/lib/api";
import type { CardEnvelope, CardContext } from "@/lib/types";

interface CardRendererProps {
  card: CardEnvelope;
  /** Контекст для load-more, deanonymize и curl-copy (Plan 03-04, 04-01) */
  context?: CardContext;
}

export function CardRenderer({ card, context }: CardRendererProps) {
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
        <TableCard
          payload={card.payload}
          onDeanonymize={makeOnDeanonymize(card.payload.card_id)}
        />
      );
    case "object":
      return (
        <ObjectCard
          payload={card.payload}
          onDeanonymize={makeOnDeanonymize(card.payload.card_id)}
        />
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
        <LogCard
          payload={logPayload}
          onLoadMore={onLoadMore}
          onDeanonymize={makeOnDeanonymize(cardId)}
        />
      );
    }
    default: {
      // TypeScript narrowing исчерпан — runtime защита для неизвестных типов
      const unknown = card as { type: string; payload: unknown };
      return (
        <div className="rounded-lg border border-[var(--border)] bg-[var(--bg-elevated)] p-3">
          <p className="text-xs text-[var(--fg-muted)] mb-2">
            Неизвестный тип карточки: {unknown.type}
          </p>
          <pre className="text-xs font-mono text-[var(--fg)] overflow-x-auto">
            {JSON.stringify(unknown.payload, null, 2).slice(0, 500)}
          </pre>
        </div>
      );
    }
  }
}
