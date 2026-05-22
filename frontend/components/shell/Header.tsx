"use client";

import Link from "next/link";
import { Activity, BookOpen, HelpCircle, PanelLeft, Search, Settings } from "lucide-react";
import { Button } from "@/components/ui/button";
import { BrandMark } from "./BrandMark";
import { StencilLockup } from "./StencilLockup";
import { ChannelSelector } from "./ChannelSelector";
import { ModelBadge } from "./ModelBadge";
import { AnonymizationToggle } from "./AnonymizationToggle";
import { ThemeToggle } from "./ThemeToggle";

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
          <BrandMark size={36} />
          <StencilLockup subtitle="Production · Stable" fontSize={16} />
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
          <button
            type="button"
            onClick={onOpenCmdK}
            aria-label="Командное меню"
            className="inline-flex items-center gap-2 h-[30px] px-2.5 rounded-md bg-[var(--bg-2)] border border-[var(--bd-2)] text-[var(--fg-2)] hover:text-[var(--fg-1)] hover:border-[var(--bd-3)] transition-colors"
            style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
          >
            <Search className="h-3 w-3" />
            <span className="text-[10px] tracking-[0.16em] uppercase">Search</span>
            <kbd className="text-[9px] tracking-[0.1em] px-1 py-0.5 rounded border border-[var(--bd-2)] text-[var(--fg-3)]">
              ⌘K
            </kbd>
          </button>
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
            href="/guide"
            aria-label="Гайд аналитика"
            title="Гайд аналитика — как работать с приложением"
          >
            <BookOpen className="h-[15px] w-[15px]" />
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
        <ThemeToggle />
        <Button
          variant="ghost"
          size="icon"
          asChild
          className="h-[30px] w-[30px] text-[var(--fg-3)] hover:text-[var(--fg-1)]"
        >
          <Link
            href="/settings"
            aria-label="Настройки"
            title="Настройки — базы 1С и модель ИИ"
          >
            <Settings className="h-[15px] w-[15px]" />
          </Link>
        </Button>
      </div>
    </header>
  );
}
