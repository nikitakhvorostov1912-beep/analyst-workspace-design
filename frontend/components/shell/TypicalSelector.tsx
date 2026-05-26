"use client";

import { useEffect, useState } from "react";
import { BookOpen, ChevronDown, Sparkles } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  fetchTypicalConfigurations,
  type TypicalConfigurationDTO,
} from "@/lib/api";
import {
  getActiveTypicalChannelId,
  setActiveTypicalChannelId,
} from "@/lib/storage";
import { cn } from "@/lib/utils";

/**
 * M-K2.5.7 TypicalSelector — выбор типовой конфигурации для сравнения.
 *
 * Отличия от ChannelSelector (MCP base):
 * - НЕ требует ping — типовые загружены в локальную БД, всегда «готовы»
 * - Показывает счётчики «граф / карточки» вместо tool_count
 * - Опциональный — без активной типовой LLM-tools `explain_typical_object`
 *   просто требует явный channel_id от пользователя
 *
 * Хранится в `localStorage` через `setActiveTypicalChannelId` —
 * аналитик выбирает один раз, выбор переживает перезагрузку страницы.
 */

const DISPLAY_KIND_LABELS: Record<string, string> = {
  UT_115: "УТ 11.5",
  ERP_25: "ERP 2.5",
  KA_2: "КА 2",
  BP_30: "БП 3.0",
  ZUP_31: "ЗУП 3.1",
  USO_25: "УСО 2.5",
  DOCFLOW_3: "Документооборот 3",
};

function shortKindLabel(kind: string): string {
  return DISPLAY_KIND_LABELS[kind] ?? kind;
}

type Props = {
  /** Уведомляет родителя об изменении (если он хочет react на это). */
  onChange?: (channelId: string | null) => void;
};

export function TypicalSelector({ onChange }: Props) {
  const [configs, setConfigs] = useState<TypicalConfigurationDTO[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    setActiveId(getActiveTypicalChannelId());

    let cancelled = false;
    async function load() {
      try {
        const response = await fetchTypicalConfigurations();
        if (cancelled) return;
        setConfigs(response.configurations);
        setLoadError(null);
      } catch (err) {
        if (cancelled) return;
        setLoadError(
          err instanceof Error ? err.message : "Не удалось загрузить типовые",
        );
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  function handleSelect(channelId: string | null) {
    setActiveTypicalChannelId(channelId);
    setActiveId(channelId);
    setOpen(false);
    onChange?.(channelId);
  }

  // Empty state — нет загруженных типовых
  if (configs.length === 0 && loadError === null) {
    return (
      <div
        className="hidden md:flex items-center gap-2 h-9 px-3 rounded-md border border-dashed border-[var(--bd-2)] bg-[var(--bg-2)] text-[var(--fg-3)] select-none"
        title="Типовые конфигурации не загружены"
        data-testid="typical-selector-empty"
      >
        <BookOpen className="h-3.5 w-3.5 flex-none" />
        <span
          className="text-[10px] tracking-[0.16em] uppercase flex-none"
          style={{
            fontFamily: "var(--font-jb-mono), ui-monospace, monospace",
          }}
        >
          Типовая
        </span>
        <span className="text-[12px]">не загружена</span>
      </div>
    );
  }

  if (loadError !== null) {
    return (
      <div
        className="hidden md:flex items-center gap-2 h-9 px-3 rounded-md border border-[var(--error-40)] bg-[var(--error-12)] text-[var(--error)] text-[12px]"
        title={loadError}
        data-testid="typical-selector-error"
      >
        <BookOpen className="h-3.5 w-3.5 flex-none" />
        <span>Ошибка загрузки типовых</span>
      </div>
    );
  }

  const active = configs.find((c) => c.channel_id === activeId) ?? null;

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <button
          className={cn(
            "flex items-center gap-2 h-9 px-3 rounded-md transition-colors min-w-[180px] cursor-pointer focus:outline-none focus:ring-2 focus:ring-[var(--accent-20)]",
            active
              ? "border border-[var(--accent-32)] bg-[var(--accent-08)] text-[var(--fg-1)]"
              : "border border-[var(--bd-2)] bg-[var(--bg-2)] hover:bg-[var(--bg-hover)] hover:border-[var(--bd-3)] text-[var(--fg-2)]",
          )}
          aria-label="Выбор типовой конфигурации"
          title={
            active
              ? `${active.display_name} — ${active.total_nodes.toLocaleString("ru")} узлов, ${active.total_cards} карточек`
              : "Выбрать типовую"
          }
          data-testid="typical-selector-button"
        >
          <Sparkles
            className={cn(
              "h-3.5 w-3.5 flex-none",
              active ? "text-[var(--accent)]" : "text-[var(--fg-3)]",
            )}
          />
          <span
            className="text-[10px] tracking-[0.16em] uppercase flex-none"
            style={{
              fontFamily: "var(--font-jb-mono), ui-monospace, monospace",
            }}
          >
            Типовая
          </span>
          <span
            className="flex-1 text-left text-[12.5px] font-semibold truncate"
            style={{
              fontFamily:
                "var(--font-plex-mono), 'IBM Plex Mono', ui-monospace, monospace",
            }}
          >
            {active ? shortKindLabel(active.config_kind) : "—"}
          </span>
          <ChevronDown className="h-3.5 w-3.5 text-[var(--fg-3)] flex-none" />
        </button>
      </DropdownMenuTrigger>

      <DropdownMenuContent
        align="center"
        className="min-w-[320px] max-h-[420px] overflow-y-auto"
      >
        <DropdownMenuLabel>Типовые конфигурации</DropdownMenuLabel>
        <DropdownMenuSeparator />

        <DropdownMenuItem
          className={cn(
            "cursor-pointer items-start py-2 px-3",
            !active && "bg-[var(--accent-08)]",
          )}
          onSelect={() => handleSelect(null)}
        >
          <div className="flex-1">
            <div className="font-medium text-[13px] text-[var(--fg-2)]">
              Без типовой
            </div>
            <div className="text-[10px] text-[var(--fg-4)] mt-0.5">
              Бот не будет сравнивать с типовой
            </div>
          </div>
          {!active && <span className="text-[var(--accent)] text-sm">✓</span>}
        </DropdownMenuItem>

        <DropdownMenuSeparator />

        {configs.map((cfg) => {
          const isActive = cfg.channel_id === activeId;
          const ready =
            cfg.status === "graph_built" ||
            cfg.status === "ready" ||
            cfg.status === "enriched";
          return (
            <DropdownMenuItem
              key={cfg.channel_id}
              className={cn(
                "cursor-pointer items-start py-2.5 px-3 gap-3",
                isActive && "bg-[var(--accent-08)]",
              )}
              onSelect={() => handleSelect(cfg.channel_id)}
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span
                    className="font-semibold text-[13px]"
                    style={{
                      fontFamily:
                        "var(--font-plex-mono), 'IBM Plex Mono', ui-monospace, monospace",
                    }}
                  >
                    {shortKindLabel(cfg.config_kind)}
                  </span>
                  <span
                    className="text-[10px] text-[var(--fg-3)]"
                    style={{
                      fontFamily:
                        "var(--font-jb-mono), ui-monospace, monospace",
                    }}
                  >
                    {cfg.config_version}
                  </span>
                  {!ready && (
                    <span
                      className="px-1.5 py-[1px] rounded text-[9px] tracking-[0.14em] uppercase font-medium border bg-[var(--warning-12)] text-[var(--warning)] border-[var(--warning-40)]"
                      style={{
                        fontFamily:
                          "var(--font-jb-mono), ui-monospace, monospace",
                      }}
                      title={`Статус индексации: ${cfg.status}`}
                    >
                      {cfg.status}
                    </span>
                  )}
                </div>
                <div
                  className="text-[10px] tracking-[0.12em] uppercase text-[var(--fg-3)] flex items-center gap-1.5 flex-wrap"
                  style={{
                    fontFamily:
                      "var(--font-jb-mono), ui-monospace, monospace",
                  }}
                >
                  <span>{cfg.total_nodes.toLocaleString("ru")} узлов</span>
                  <span className="text-[var(--fg-4)]">·</span>
                  <span>
                    {cfg.total_cards.toLocaleString("ru")} карточек
                  </span>
                </div>
              </div>
              {isActive && (
                <span
                  className="text-[var(--accent)] text-sm flex-none mt-1"
                  aria-label="Активная типовая"
                >
                  ✓
                </span>
              )}
            </DropdownMenuItem>
          );
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
