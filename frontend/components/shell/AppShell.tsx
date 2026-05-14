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
  return (
    <div className="grid h-screen" style={{ gridTemplateColumns: "260px 1fr", gridTemplateRows: "56px 1fr auto" }}>
      {/* Header — занимает обе колонки */}
      <Header {...headerProps} />

      {/* Sidebar */}
      <Sidebar
        grouped={grouped}
        activeId={activeId}
        onCreateNew={onCreateNew}
        onDelete={onDeleteSession}
      />

      {/* Main content area */}
      <main className="overflow-y-auto bg-[var(--bg)]">
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
