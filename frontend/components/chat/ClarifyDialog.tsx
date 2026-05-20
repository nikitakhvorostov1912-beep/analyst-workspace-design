"use client";

import { HelpCircle, X } from "lucide-react";
import { useState } from "react";
import type { ClarifyRequiredPayload } from "@/lib/types";

interface ClarifyDialogProps {
  payload: ClarifyRequiredPayload;
  onResolve: (answer: string | string[]) => void | Promise<void>;
}

/**
 * Sprint 4 (Hermes D1): диалог уточнения от LLM.
 *
 * Multi=false → radio + кнопка «Свой ответ».
 * Multi=true → checkbox-список.
 */
export function ClarifyDialog({ payload, onResolve }: ClarifyDialogProps) {
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [custom, setCustom] = useState("");
  const [showCustom, setShowCustom] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const canSubmit =
    selected.size > 0 || (showCustom && custom.trim().length > 0);

  function toggle(option: string) {
    if (payload.multi) {
      const next = new Set(selected);
      if (next.has(option)) {
        next.delete(option);
      } else {
        next.add(option);
      }
      setSelected(next);
    } else {
      setSelected(new Set([option]));
      setShowCustom(false);
    }
  }

  async function handleSubmit() {
    if (!canSubmit) return;
    setSubmitting(true);
    try {
      let answer: string | string[];
      if (showCustom && custom.trim()) {
        answer = custom.trim();
      } else if (payload.multi) {
        answer = Array.from(selected);
      } else {
        answer = Array.from(selected)[0] || "";
      }
      await onResolve(answer);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="my-3 rounded-md border border-[var(--accent-32)] bg-[var(--accent-12)] p-4 animate-fade-up">
      <div className="flex items-start gap-2 mb-3">
        <HelpCircle className="h-4 w-4 text-[var(--accent)] flex-shrink-0 mt-0.5" />
        <div className="text-[13.5px] text-[var(--fg-1)] leading-[1.55]">
          {payload.question}
        </div>
      </div>

      <div className="space-y-1.5 mb-3">
        {payload.options.map((option, idx) => {
          const isSelected = selected.has(option);
          return (
            <button
              key={`${idx}-${option}`}
              type="button"
              onClick={() => toggle(option)}
              className={`flex items-center gap-3 w-full px-3 h-9 rounded-md border text-left transition-colors text-[13px] ${
                isSelected
                  ? "border-[var(--accent)] bg-[var(--bg-1)] text-[var(--fg-1)]"
                  : "border-[var(--bd-2)] bg-[var(--bg-1)] text-[var(--fg-2)] hover:bg-[var(--bg-2)]"
              }`}
            >
              <span
                className={`flex h-4 w-4 items-center justify-center flex-shrink-0 ${
                  payload.multi ? "rounded-sm" : "rounded-full"
                } border ${
                  isSelected
                    ? "border-[var(--accent)] bg-[var(--accent)]"
                    : "border-[var(--bd-3)]"
                }`}
              >
                {isSelected && (
                  <span
                    className={`bg-[var(--brand-ink,#15161a)] ${
                      payload.multi ? "h-2 w-2 rounded-sm" : "h-1.5 w-1.5 rounded-full"
                    }`}
                  />
                )}
              </span>
              <span className="flex-1 truncate">{option}</span>
            </button>
          );
        })}

        {payload.allow_custom && (
          <button
            type="button"
            onClick={() => {
              setShowCustom((v) => !v);
              if (!showCustom) setSelected(new Set());
            }}
            className={`flex items-center gap-3 w-full px-3 h-9 rounded-md border text-left transition-colors text-[13px] ${
              showCustom
                ? "border-[var(--accent)] bg-[var(--bg-1)] text-[var(--fg-1)]"
                : "border-dashed border-[var(--bd-2)] bg-[var(--bg-1)] text-[var(--fg-3)] hover:text-[var(--fg-1)]"
            }`}
          >
            <span className="text-[11px] uppercase tracking-[0.14em]">
              Свой ответ
            </span>
          </button>
        )}

        {showCustom && (
          <input
            type="text"
            value={custom}
            onChange={(e) => setCustom(e.target.value)}
            autoFocus
            placeholder="Введите ваш ответ..."
            className="w-full px-3 h-9 rounded-md bg-[var(--bg-1)] border border-[var(--bd-2)] text-[13px] text-[var(--fg-1)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-20)] focus:border-[var(--accent-32)]"
            onKeyDown={(e) => {
              if (e.key === "Enter" && custom.trim()) {
                void handleSubmit();
              }
            }}
          />
        )}
      </div>

      <div className="flex items-center justify-end gap-2">
        <button
          type="button"
          onClick={handleSubmit}
          disabled={!canSubmit || submitting}
          className="px-4 h-8 rounded-md bg-[var(--accent)] text-[var(--brand-ink,#15161a)] text-[12.5px] font-semibold disabled:opacity-50 disabled:cursor-not-allowed hover:brightness-110 transition-all"
        >
          {submitting ? "Отправка..." : "Ответить"}
        </button>
      </div>
    </div>
  );
}
