"use client";

import { useEffect } from "react";
import { hasNotSeen, markHintSeen } from "@/lib/onboarding-hints";
import { publishToast } from "@/lib/toast";

interface MemoryHintProps {
  /** Сколько у пользователя сессий уже накоплено (включая текущую). */
  sessionCount: number;
  /** Триггер. По умолчанию 3 — после 3-й сессии. */
  threshold?: number;
}

/**
 * One-time contextual hint про постоянную память.
 *
 * При sessionCount >= threshold показывает toast с приглашением заполнить
 * USER.md/MEMORY.md. После показа — `markHintSeen`, второй раз не появится.
 *
 * Sprint 1 (Hermes) onboarding pattern.
 */
export function MemoryHint({ sessionCount, threshold = 3 }: MemoryHintProps) {
  useEffect(() => {
    if (sessionCount < threshold) return;
    if (!hasNotSeen("memory_first_use")) return;
    publishToast({
      type: "info",
      message:
        "У вас уже несколько сессий. Хотите, чтобы я запомнил ваши предпочтения между сессиями? Откройте Настройки → Постоянная память.",
      duration_ms: 10_000,
    });
    markHintSeen("memory_first_use");
  }, [sessionCount, threshold]);

  return null;
}
