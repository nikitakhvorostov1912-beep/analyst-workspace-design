"use client";

import { useEffect, useState } from "react";
import { getLLMConfig } from "@/lib/storage";

export function ModelBadge() {
  const [label, setLabel] = useState<string>("—");

  useEffect(() => {
    const cfg = getLLMConfig();
    if (cfg && cfg.model) {
      setLabel(`${cfg.model} · ${cfg.temperature}`);
    }
  }, []);

  return (
    <span className="font-mono text-xs text-[var(--fg-muted)] bg-[var(--bg-elevated)] border border-[var(--border)] rounded px-2 py-1 select-none">
      {label}
    </span>
  );
}
