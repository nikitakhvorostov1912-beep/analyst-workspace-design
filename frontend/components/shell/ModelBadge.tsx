"use client";

import { useEffect, useState } from "react";
import { fetchLLMConfig } from "@/lib/api";

export function ModelBadge() {
  const [label, setLabel] = useState<string | null>(null);

  useEffect(() => {
    void fetchLLMConfig().then((cfg) => {
      if (cfg && cfg.model) {
        setLabel(`${cfg.model} · ${cfg.temperature}`);
      }
    }).catch(() => {
      // Backend недоступен — бейдж не отображается
    });
  }, []);

  if (!label) return null;

  return (
    <span className="font-mono text-xs text-[var(--fg-muted)] bg-[var(--bg-elevated)] border border-[var(--border)] rounded px-2 py-1 select-none">
      {label}
    </span>
  );
}
