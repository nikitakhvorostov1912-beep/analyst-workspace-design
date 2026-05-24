"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Check } from "lucide-react";
import { StatusDot } from "@/components/ui/StatusDot";
import { StencilChip } from "@/components/ui/StencilChip";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { fetchLLMConfig, updateLLMConfig } from "@/lib/api";
import { getLLMApiKey } from "@/lib/api-keys";
import { PROVIDERS, resolveProviderAndModel } from "@/lib/llm-providers";
import { publishToast } from "@/lib/toast";
import { cn } from "@/lib/utils";

interface ModelInfo {
  model: string;
  endpoint: string;
  temperature: number | null;
}

/**
 * Короткое имя для chip в шапке: «MIMO v2.5 PRO», «GPT-4.1», «CLAUDE SONNET 4.5».
 * Из preset.label убираем префикс провайдера и uppercase'им.
 */
function shortenLabel(label: string): string {
  return label
    .replace(/^Xiaomi /, "")
    .replace(/^Anthropic /, "")
    .replace(/^Google /, "")
    .replace(/^Meta /, "")
    .replace(/^Llama /, "Llama ")
    .toUpperCase();
}

/**
 * Бейдж модели в шапке + быстрый переключатель.
 *
 * До 2026-05-21 был read-only chip — чтобы сменить модель аналитик шёл в
 * Settings, выбирал из dropdown, сохранял, возвращался. Теперь клик по chip
 * открывает popover с тем же каталогом провайдеров/моделей (из lib/llm-providers).
 *
 * Switch делает PATCH /llm-config с новой парой endpoint+model. Температура и
 * API-ключ остаются. Для провайдеров, где ключ ещё не введён, popover ведёт
 * на /settings (вставлять ключ всё равно надо там).
 */
export function ModelBadge() {
  const [info, setInfo] = useState<ModelInfo | null>(null);
  const [switching, setSwitching] = useState(false);

  async function refresh() {
    try {
      const cfg = await fetchLLMConfig();
      if (cfg && cfg.model) {
        setInfo({
          model: cfg.model,
          endpoint: cfg.endpoint,
          temperature: typeof cfg.temperature === "number" ? cfg.temperature : null,
        });
      }
    } catch {
      // Backend недоступен — бейдж не отображается
    }
  }

  useEffect(() => {
    void refresh();
    // 2026-05-24: слушаем CustomEvent от LLMConfigForm + от собственного
    // handleSwitch (см. ниже). Без этого badge оставался со старой моделью
    // после сохранения в Settings — пришёл в чат, а там старая.
    function handleConfigUpdate() {
      void refresh();
    }
    if (typeof window !== "undefined") {
      window.addEventListener("llm-config-updated", handleConfigUpdate);
      return () => {
        window.removeEventListener("llm-config-updated", handleConfigUpdate);
      };
    }
    return undefined;
  }, []);

  if (!info) return null;

  const matched = resolveProviderAndModel(info.model);
  const display = matched?.model.label ?? info.model;
  const shortDisplay = shortenLabel(display);

  async function handleSwitch(modelId: string, endpoint: string) {
    if (switching) return;
    setSwitching(true);
    try {
      await updateLLMConfig({
        endpoint,
        model: modelId,
        temperature: info?.temperature ?? 0.3,
      });
      const newPreset = resolveProviderAndModel(modelId);
      const providerLabel = newPreset?.provider.label ?? "провайдер";
      const modelLabel = newPreset?.model.label ?? modelId;

      // Проверяем: есть ли ключ для нового провайдера. localStorage хранит один
      // ключ на весь app (legacy) — если он есть, считаем что подходит. Backend
      // вернёт `has_env_api_key=true` после refresh если есть env-ключ.
      // Если ничего из двух — показываем warn-toast с подсказкой ввести ключ.
      await refresh();
      // 2026-05-24: уведомляем Settings page (если открыта в фоне) и любых
      // других подписчиков что конфиг сменился.
      if (typeof window !== "undefined") {
        window.dispatchEvent(new CustomEvent("llm-config-updated"));
      }
      const cfg = await fetchLLMConfig();
      const hasEnv = Boolean(cfg?.has_env_api_key);
      const hasLocal = Boolean(getLLMApiKey());
      const hasKey = hasEnv || hasLocal;

      if (!hasKey && newPreset?.provider.embedKeyAvailable !== true) {
        publishToast({
          type: "warning",
          message: `Модель ${modelLabel} выбрана, но API ключ ${providerLabel} не введён. Откройте Настройки → API ключ.`,
        });
      } else {
        publishToast({
          type: "info",
          message: `Модель переключена: ${modelLabel}`,
        });
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Не удалось сменить модель";
      publishToast({ type: "error", message });
    } finally {
      setSwitching(false);
    }
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-label={`Модель: ${display}. Нажмите чтобы сменить.`}
          title={matched ? `${display} (${info.model})` : info.model}
          data-testid="model-badge"
          data-model={info.model}
          className="cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-20)] rounded-full"
        >
          <StencilChip tone="muted">
            <StatusDot status="online" size="sm" aria-label="модель активна" />
            <span className="truncate max-w-[160px]">{shortDisplay}</span>
            {info.temperature !== null && (
              <span className="text-[var(--fg-3)]">· {info.temperature.toFixed(1)}</span>
            )}
          </StencilChip>
        </button>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="end" className="max-h-[480px] overflow-y-auto w-[320px]">
        <DropdownMenuLabel>Сменить модель</DropdownMenuLabel>
        <DropdownMenuSeparator />

        {PROVIDERS.map((provider, idx) => (
          <div key={provider.id}>
            {idx > 0 && <DropdownMenuSeparator />}
            <DropdownMenuLabel className="text-[10px] uppercase tracking-[0.16em] text-[var(--fg-3)] font-normal">
              {provider.label}
            </DropdownMenuLabel>
            {provider.models.map((preset) => {
              const isActive = preset.id === info.model;
              return (
                // 2026-05-24 (QA finding-10, FINAL FIX): Radix DropdownMenuItem
                // имеет внутренние onPointerDown/onMouseDown handlers которые
                // блокируют synthetic onClick через event.preventDefault().
                // Решение — нативная <button> + аddEventListener-style onClick
                // через onPointerUp (Radix не perevented тут).
                // НЕ оборачиваем в DropdownMenuItem — Radix управление
                // фокусом нам не критично, popover закрывается через setOpen.
                <button
                  key={preset.id}
                  type="button"
                  role="menuitem"
                  disabled={isActive || switching}
                  className={cn(
                    "w-full text-left flex items-start gap-2 px-2 py-1.5 rounded-sm transition-colors",
                    "hover:bg-[var(--accent-08)] focus-visible:outline-none focus-visible:bg-[var(--accent-08)]",
                    "disabled:opacity-60 disabled:cursor-not-allowed",
                    !isActive && "cursor-pointer",
                  )}
                  onClick={() => {
                    void handleSwitch(preset.id, provider.endpoint);
                  }}
                >
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-[var(--fg-1)]">
                      {preset.label}
                    </div>
                    <div className="text-xs text-[var(--fg-3)] truncate">
                      {preset.description}
                    </div>
                  </div>
                  {isActive && (
                    <Check className="h-4 w-4 text-[var(--accent)] flex-none mt-0.5" />
                  )}
                </button>
              );
            })}
          </div>
        ))}

        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link
            href="/settings"
            className="text-xs text-[var(--accent)] hover:underline"
          >
            Полные настройки →
          </Link>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
