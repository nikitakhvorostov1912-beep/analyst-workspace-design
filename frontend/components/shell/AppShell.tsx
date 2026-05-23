import type { ReactNode } from "react";
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
  headerProps?: HeaderProps;
}

const DEFAULT_HEADER_PROPS: HeaderProps = {
  activeChannelId: null,
  onChannelChange: () => undefined,
};

export function AppShell({
  children,
  bottom,
  grouped,
  activeId,
  onCreateNew,
  onDeleteSession,
  headerProps = DEFAULT_HEADER_PROPS,
}: AppShellProps) {
  // UX-12 fix (2026-05-24): без `overflow-hidden` + `minmax(0, 1fr)` дочерние
  // элементы с h-full + длинным контентом (Sidebar с 30 сессиями) растягивают
  // grid row 1fr до своей высоты — body становится выше 100vh, input field
  // уходит за viewport. CSS grid имеет дефолтный min-height: auto для cells,
  // что и ломает overflow. minmax(0, 1fr) фиксирует row на доступную высоту.
  return (
    <div
      className="grid h-screen overflow-hidden"
      style={{ gridTemplateColumns: "260px 1fr", gridTemplateRows: "56px minmax(0, 1fr) auto" }}
    >
      {/* Header — занимает обе колонки */}
      <Header {...headerProps} />

      {/* Sidebar — собственный h-full работает корректно с minmax(0, 1fr) row */}
      <Sidebar
        grouped={grouped}
        activeId={activeId}
        onCreateNew={onCreateNew}
        onDelete={onDeleteSession}
      />

      {/* Main content area */}
      <main className="overflow-y-auto bg-[var(--bg)] min-h-0">
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
