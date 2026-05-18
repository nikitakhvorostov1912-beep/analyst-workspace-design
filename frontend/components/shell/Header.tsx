"use client";

import Link from "next/link";
import { Activity, HelpCircle, PanelLeft, Search, Settings } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ChannelSelector } from "./ChannelSelector";
import { ModelBadge } from "./ModelBadge";
import { AnonymizationToggle } from "./AnonymizationToggle";

export interface HeaderProps {
  activeChannelId: string | null;
  onChannelChange: (id: string) => void;
  onToggleSidebar?: () => void;
  onOpenCmdK?: () => void;
}

export function Header({
  activeChannelId,
  onChannelChange,
  onToggleSidebar,
  onOpenCmdK,
}: HeaderProps) {
  return (
    <header
      className="sticky top-0 z-10 grid grid-cols-[260px_1fr_auto] items-center gap-[18px] h-[52px] px-3.5 bg-[var(--bg-1)] border-b border-[var(--bd-1)] col-span-2"
      data-testid="app-header"
    >
      {/* Left: sidebar toggle + brand */}
      <div className="flex items-center gap-2.5">
        {onToggleSidebar && (
          <Button
            variant="ghost"
            size="icon"
            onClick={onToggleSidebar}
            aria-label="Свернуть/развернуть боковую панель"
            className="h-7 w-7"
          >
            <PanelLeft className="h-4 w-4" />
          </Button>
        )}
        <div className="flex items-center gap-2.5 min-w-0">
          <div
            className="h-7 w-7 rounded-md bg-[var(--accent-08)] text-[var(--accent)] border border-[var(--accent-20)] inline-flex items-center justify-center font-mono text-[11.5px] font-semibold flex-shrink-0"
            aria-hidden="true"
          >
            1С
          </div>
          <div className="min-w-0">
            <div className="font-semibold text-sm leading-tight text-[var(--fg-1)] truncate">
              Аналитик
            </div>
            <div className="font-mono text-[10.5px] text-[var(--fg-3)]">
              v1.2.1
            </div>
          </div>
        </div>
      </div>

      {/* Center: channel selector */}
      <div className="flex justify-center">
        <ChannelSelector
          activeId={activeChannelId}
          onChange={onChannelChange}
        />
      </div>

      {/* Right: anon + model + cmd-K + status icons */}
      <div className="flex items-center gap-1.5">
        <AnonymizationToggle />
        <ModelBadge />
        {onOpenCmdK && (
          <Button
            variant="ghost"
            size="sm"
            onClick={onOpenCmdK}
            className="h-[30px] px-2 gap-1.5 bg-[var(--bg-1)] border border-[var(--bd-2)]"
            aria-label="Командное меню"
          >
            <Search className="h-3.5 w-3.5" />
            <kbd className="text-[10px] text-[var(--fg-3)] font-mono">⌘K</kbd>
          </Button>
        )}
        <Button
          variant="ghost"
          size="icon"
          asChild
          className="h-[30px] w-[30px] text-[var(--fg-3)] hover:text-[var(--fg-1)]"
        >
          <Link
            href="/status"
            aria-label="Диагностика"
            title="Диагностика — проверить что всё работает"
          >
            <Activity className="h-[15px] w-[15px]" />
          </Link>
        </Button>
        <Button
          variant="ghost"
          size="icon"
          asChild
          className="h-[30px] w-[30px] text-[var(--fg-3)] hover:text-[var(--fg-1)]"
        >
          <Link
            href="/about"
            aria-label="О приложении"
            title="О приложении — что это и как пользоваться"
          >
            <HelpCircle className="h-[15px] w-[15px]" />
          </Link>
        </Button>
        <Button
          variant="ghost"
          size="icon"
          asChild
          className="h-[30px] w-[30px] text-[var(--fg-3)] hover:text-[var(--fg-1)]"
        >
          <Link
            href="/settings"
            aria-label="Настройки"
            title="Настройки — MCP подключения и LLM"
          >
            <Settings className="h-[15px] w-[15px]" />
          </Link>
        </Button>
      </div>
    </header>
  );
}
