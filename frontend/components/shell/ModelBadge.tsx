"use client";

import { useEffect, useState } from "react";
import { Sparkles } from "lucide-react";
import { fetchLLMConfig } from "@/lib/api";

interface ModelInfo {
  model: string;
  temperature: number | null;
}

export function ModelBadge() {
  const [info, setInfo] = useState<ModelInfo | null>(null);

  useEffect(() => {
    void fetchLLMConfig()
      .then((cfg) => {
        if (cfg && cfg.model) {
          setInfo({
            model: cfg.model,
            temperature: typeof cfg.temperature === "number" ? cfg.temperature : null,
          });
        }
      })
      .catch(() => {
        // Backend недоступен — бейдж не отображается
      });
  }, []);

  if (!info) return null;

  return (
    <div
      className="inline-flex items-center gap-1.5 px-2.5 h-[30px] rounded-md bg-[var(--bg-1)] border border-[var(--bd-2)] text-xs text-[var(--fg-2)] select-none"
      data-testid="model-badge"
    >
      <Sparkles className="h-3 w-3 text-[var(--accent)] flex-shrink-0" />
      <span className="font-mono truncate max-w-[120px]" title={info.model}>
        {info.model}
      </span>
      {info.temperature !== null && (
        <span className="font-mono text-[var(--fg-4)]">
          · {info.temperature.toFixed(1)}
        </span>
      )}
    </div>
  );
}
