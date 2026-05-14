"use client";

import { TableCard } from "./TableCard";
import { ObjectCard } from "./ObjectCard";
import { LogCard } from "./LogCard";
import type { CardEnvelope } from "@/lib/types";

interface CardRendererProps {
  card: CardEnvelope;
}

export function CardRenderer({ card }: CardRendererProps) {
  switch (card.type) {
    case "table":
      return <TableCard payload={card.payload} />;
    case "object":
      return <ObjectCard payload={card.payload} />;
    case "log":
      return <LogCard payload={card.payload} />;
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
