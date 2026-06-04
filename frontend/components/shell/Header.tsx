"use client";

import { PanelLeftClose, PanelLeftOpen, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { StencilLockup } from "./StencilLockup";
import { ChannelSelector } from "./ChannelSelector";
import { TypicalSelector } from "./TypicalSelector";
import { StatusCapsule } from "./StatusCapsule";
import { OverflowMenu } from "./OverflowMenu";
import { UpdateBanner } from "./UpdateBanner";

export interface HeaderProps {
  activeChannelId: string | null;
  onChannelChange: (id: string) => void;
  onToggleSidebar?: () => void;
  /** Текущее состояние боковой панели — для иконки/подписи переключателя. */
  collapsed?: boolean;
  onOpenCmdK?: () => void;
}

/**
 * Header (shell v3 §1) — три зоны вместо «свалки справа».
 *
 *   Зона 1 (слева):  ☰  ◆ АНАЛИТИК │ <ChannelSelector + EnvBadge> <TypicalSelector>
 *   SPACER:          flex-1
 *   Зона 3 (справа): <Search ⌘K>  <StatusCapsule>  <OverflowMenu ⋯>
 *
 * Контекст базы (ChannelSelector) — главный левый якорь «куда я шлю запросы».
 * Статус (модель/база/анонимизация) собран в StatusCapsule; справка/тема/
 * настройки — в OverflowMenu. UpdateBanner — Electron-only (null в браузере).
 */
export function Header({
  activeChannelId,
  onChannelChange,
  onToggleSidebar,
  collapsed = false,
  onOpenCmdK,
}: HeaderProps) {
  return (
    <header
      className="sticky top-0 z-10 flex items-center gap-3 h-[52px] px-3.5 bg-[var(--bg-1)] border-b border-[var(--bd-1)] col-span-2"
      data-testid="app-header"
    >
      {/* ── ЗОНА 1: переключатель панели (верхний левый угол) + бренд + база ── */}
      {onToggleSidebar && (
        <Button
          variant="ghost"
          size="icon"
          onClick={onToggleSidebar}
          aria-label={collapsed ? "Развернуть боковую панель" : "Свернуть боковую панель"}
          title={collapsed ? "Развернуть панель с чатами" : "Свернуть панель"}
          className="h-7 w-7 flex-none text-[var(--fg-2)] hover:text-[var(--accent)]"
          data-testid="sidebar-toggle"
        >
          {collapsed ? (
            <PanelLeftOpen className="h-4 w-4" />
          ) : (
            <PanelLeftClose className="h-4 w-4" />
          )}
        </Button>
      )}

      {/* Лого-текст показываем только в развёрнутом режиме — при свёртке слева
          пусто. Глиф «А» (BrandMark) убран по фидбэку пользователя. */}
      {!collapsed && (
        <>
          <div className="flex items-center min-w-0 flex-none">
            <StencilLockup fontSize={15} />
          </div>
          {/* вертикальный разделитель */}
          <span aria-hidden className="h-[26px] w-px bg-[var(--bd-2)] flex-none" />
        </>
      )}

      {/* контекст базы — главный левый якорь */}
      <ChannelSelector activeId={activeChannelId} onChange={onChannelChange} />

      {/* M-K2.5.7: типовая для compare/explain (опциональна) */}
      <TypicalSelector />

      {/* ── SPACER ── */}
      <span className="flex-1" />

      {/* ── ЗОНА 3: поиск · статус · overflow ── */}
      {onOpenCmdK && (
        <button
          type="button"
          onClick={onOpenCmdK}
          aria-label="Поиск и команды"
          className="inline-flex items-center gap-2 h-[34px] px-2.5 rounded-md bg-[var(--bg-2)] border border-[var(--bd-2)] text-[var(--fg-2)] hover:text-[var(--fg-1)] hover:border-[var(--bd-3)] transition-colors flex-none"
        >
          <Search className="h-3.5 w-3.5" />
          <span className="text-[12.5px] hidden md:inline">Поиск по чатам…</span>
          <kbd
            className="text-[9px] tracking-[0.1em] px-1 py-0.5 rounded border border-[var(--bd-2)] text-[var(--fg-3)]"
            style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
          >
            ⌘K
          </kbd>
        </button>
      )}

      {/* P1.4: UpdateBanner — Electron-only, null в браузере (апдейты не теряем) */}
      <UpdateBanner />
      <StatusCapsule activeChannelId={activeChannelId} />
      <OverflowMenu />
    </header>
  );
}
