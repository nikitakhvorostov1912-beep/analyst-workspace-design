"use client";

import { ExternalLink, Sparkles } from "lucide-react";
import type { ITSSource, ITSSourcesCardPayload } from "@/lib/types";
import { CardHeader } from "./CardHeader";

interface ITSSourcesCardProps {
  payload: ITSSourcesCardPayload;
  /** Клик «Разобрать статью» → follow-up к модели (fetch_its). Нет → кнопки скрыты. */
  onAnalyze?: (source: ITSSource) => void;
}

export function ITSSourcesCard({ payload, onAnalyze }: ITSSourcesCardProps) {
  const { sources, total } = payload;
  const meta = `${total} ${total === 1 ? "статья" : total < 5 ? "статьи" : "статей"}`;

  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--bg-elevated)] overflow-hidden">
      <CardHeader type="its_sources" title="Источники ИТС" meta={meta} />
      <ul className="py-0.5">
        {sources.map((s, idx) => (
          <li
            key={idx}
            className="px-3 py-1.5 flex items-start gap-2 border-b border-[var(--border)] last:border-b-0"
          >
            <a
              href={s.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-start gap-1.5 text-xs text-[var(--fg)] hover:text-[var(--accent)] flex-1 min-w-0"
            >
              <ExternalLink className="h-3.5 w-3.5 shrink-0 mt-0.5 text-[var(--fg-muted)]" />
              <span className="break-words">{s.title}</span>
            </a>
            {onAnalyze && s.doc_id && (
              <button
                type="button"
                onClick={() => onAnalyze(s)}
                title="Дочитать статью целиком и разобрать"
                className="shrink-0 inline-flex items-center gap-1 h-6 px-2 rounded-md border border-[var(--bd-1)] text-[11px] text-[var(--fg-3)] hover:text-[var(--fg-1)] hover:border-[var(--bd-2)] transition-colors"
              >
                <Sparkles className="h-3 w-3" />
                Разобрать
              </button>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
