"use client";

import { useEffect, useState } from "react";
import { StatusDot } from "@/components/ui/StatusDot";
import { StencilChip } from "@/components/ui/StencilChip";
import { fetchLLMConfig } from "@/lib/api";

interface ModelInfo {
  model: string;
  temperature: number | null;
}

/**
 * Маппинг технических ID моделей к человекочитаемым именам.
 * Аналитик видит «Xiaomi MiMo v2 Pro», а не «mimo-v2-pro».
 * Tech ID остаётся в title для разработчиков и в data-model для тестов.
 */
const MODEL_DISPLAY_NAMES: Record<string, string> = {
  // Xiaomi MiMo — v2.5 семейство (новее)
  "mimo-v2.5-pro": "Xiaomi MiMo v2.5 Pro",
  "mimo-v2.5": "Xiaomi MiMo v2.5",
  "mimo-v2.5-tts": "Xiaomi MiMo v2.5 TTS",
  "mimo-v2.5-tts-voiceclone": "Xiaomi MiMo v2.5 Voice Clone",
  "mimo-v2.5-tts-voicedesign": "Xiaomi MiMo v2.5 Voice Design",
  // Xiaomi MiMo — v2 семейство
  "mimo-v2-pro": "Xiaomi MiMo v2 Pro",
  "mimo-v2-flash": "Xiaomi MiMo v2 Flash",
  "mimo-v2-omni": "Xiaomi MiMo v2 Omni",
  "mimo-v2-tts": "Xiaomi MiMo v2 TTS",
  // OpenAI
  "gpt-4o": "GPT-4o",
  "gpt-4o-mini": "GPT-4o mini",
  "gpt-4-turbo": "GPT-4 Turbo",
  "gpt-3.5-turbo": "GPT-3.5 Turbo",
  // Anthropic
  "claude-sonnet-4-6": "Claude Sonnet 4.6",
  "claude-opus-4-5": "Claude Opus 4.5",
  "claude-haiku-4-5": "Claude Haiku 4.5",
  // xAI
  "grok-4-0709": "Grok 4",
};

function displayModelName(model: string): string {
  return MODEL_DISPLAY_NAMES[model] ?? model;
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

  const display = displayModelName(info.model);
  const isMapped = display !== info.model;

  // Stencil/Mono redesign: модель показывается как muted-chip с success-dot
  // (живая модель → зелёный pulse). Brand-стиль: всё mono uppercase ls .16em.
  // Краткое имя модели в верхнем регистре: «MIMO-V2.5-PRO», «GPT-4O», «CLAUDE-SONNET-4.6».
  const shortDisplay = display
    .replace(/^Xiaomi /, "")
    .replace(/^Claude /, "")
    .toUpperCase();

  return (
    <span data-testid="model-badge" data-model={info.model}>
      <StencilChip
        tone="muted"
        title={isMapped ? `Модель: ${display} (${info.model})` : info.model}
      >
        <StatusDot status="online" size="sm" aria-label="модель активна" />
        <span className="truncate max-w-[140px]">{shortDisplay}</span>
        {info.temperature !== null && (
          <span className="text-[var(--fg-4)]">· {info.temperature.toFixed(1)}</span>
        )}
      </StencilChip>
    </span>
  );
}
