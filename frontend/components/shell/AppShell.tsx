import type { ReactNode } from "react";
import { Header } from "./Header";
import { Sidebar } from "./Sidebar";

interface AppShellProps {
  children: ReactNode;
  bottom?: ReactNode;
}

export function AppShell({ children, bottom }: AppShellProps) {
  return (
    <div className="grid h-screen" style={{ gridTemplateColumns: "260px 1fr", gridTemplateRows: "56px 1fr auto" }}>
      {/* Header — занимает обе колонки */}
      <Header />

      {/* Sidebar */}
      <Sidebar />

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
