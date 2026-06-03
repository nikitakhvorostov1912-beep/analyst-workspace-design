"use client";

import type { ReactNode } from "react";
import { useCallback, useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { Header } from "./Header";
import type { HeaderProps } from "./Header";
import { Sidebar } from "./Sidebar";
import type { SessionsGrouped } from "@/lib/types";

interface AppShellProps {
  children: ReactNode;
  bottom?: ReactNode;
  grouped?: SessionsGrouped;
  activeId?: string | null;
  onCreateNew?: () => void;
  onDeleteSession?: (id: string) => void;
  onRenameSession?: (id: string, title: string) => void;
  onPinSession?: (id: string, pinned: boolean) => void;
  headerProps?: HeaderProps;
}

const DEFAULT_HEADER_PROPS: HeaderProps = {
  activeChannelId: null,
  onChannelChange: () => undefined,
};

const SIDEBAR_STORAGE_KEY = "analyst.sidebar-collapsed";

export function AppShell({
  children,
  bottom,
  grouped,
  activeId,
  onCreateNew,
  onDeleteSession,
  onRenameSession,
  onPinSession,
  headerProps = DEFAULT_HEADER_PROPS,
}: AppShellProps) {
  // Sprint 04 (M08 · Page enter): main контент проигрывает fade-up при смене
  // маршрута. key={pathname} перемонтирует main → animate-fade-up отыграет
  // заново. Sidebar и Header не перемонтируются.
  const pathname = usePathname();

  // Sprint 04 (M07 · Sidebar collapse): persistance в localStorage. Дефолт —
  // развёрнут. Hydration-safe: при SSR collapsed=false, эффект после mount
  // читает реальное значение.
  const [collapsed, setCollapsed] = useState(false);
  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      const stored = localStorage.getItem(SIDEBAR_STORAGE_KEY);
      if (stored === "true") setCollapsed(true);
    } catch {
      // localStorage может быть отключён — оставляем дефолт
    }
  }, []);

  const toggleSidebar = useCallback(() => {
    setCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(SIDEBAR_STORAGE_KEY, String(next));
      } catch {
        // ignore
      }
      return next;
    });
  }, []);

  // UX-12 fix (2026-05-24): без `overflow-hidden` + `minmax(0, 1fr)` дочерние
  // элементы с h-full + длинным контентом (Sidebar с 30 сессиями) растягивают
  // grid row 1fr до своей высоты — body становится выше 100vh, input field
  // уходит за viewport. CSS grid имеет дефолтный min-height: auto для cells,
  // что и ломает overflow. minmax(0, 1fr) фиксирует row на доступную высоту.
  return (
    <div
      className="grid h-screen overflow-hidden transition-[grid-template-columns] duration-300 ease-out"
      data-sidebar={collapsed ? "collapsed" : "expanded"}
      // HIGH-10 (2026-05-24): header row 56→52px чтобы совпасть с реальной
      // высотой Header (h-[52px] в Header.tsx). Раньше резерв 56px → визуальный
      // gap 4px между Header и Sidebar.
      style={{
        gridTemplateColumns: collapsed ? "56px 1fr" : "260px 1fr",
        gridTemplateRows: "52px minmax(0, 1fr) auto",
      }}
    >
      {/* Header — занимает обе колонки */}
      <Header {...headerProps} />

      {/* Sidebar — собственный h-full работает корректно с minmax(0, 1fr) row */}
      <Sidebar
        grouped={grouped}
        activeId={activeId}
        onCreateNew={onCreateNew}
        onDelete={onDeleteSession}
        onRename={onRenameSession}
        onPin={onPinSession}
        collapsed={collapsed}
        onToggleCollapse={toggleSidebar}
      />

      {/* Main content area — animate-fade-up при смене pathname (M08) */}
      <main
        key={pathname}
        className="overflow-y-auto bg-[var(--bg)] min-h-0 animate-fade-up"
      >
        {children}
      </main>

      {/* Bottom input — под sidebar и main, только в колонке main */}
      {bottom && (
        <>
          {/* Пустая ячейка под sidebar */}
          <div className="border-t border-[var(--border)] bg-[var(--bg)]" />
          {/* Input область */}
          <div className="border-t border-[var(--border)] bg-[var(--bg)]">
            {bottom}
          </div>
        </>
      )}
    </div>
  );
}
