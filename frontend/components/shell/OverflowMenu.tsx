"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  MoreHorizontal,
  Sun,
  Moon,
  Activity,
  BookOpen,
  Sliders,
  Brain,
  Info,
  Settings,
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

type Theme = "dark" | "light";
const THEME_KEY = "analyst-theme";

function applyTheme(t: Theme) {
  const root = document.documentElement;
  if (t === "light") root.setAttribute("data-theme", "light");
  else root.removeAttribute("data-theme");
}

/**
 * OverflowMenu «⋯» (shell v3 §3) — меню оболочки в Зоне 3 хедера.
 *
 * Поглощает безымянные иконки: тема (ThemeToggle), справка (HelpMenu),
 * Настройки. Все пункты — с текстовыми подписями. Тема хранится в
 * localStorage `analyst-theme` + `data-theme` на <html> (как в ThemeToggle).
 */
export function OverflowMenu() {
  const [theme, setTheme] = useState<Theme>("dark");
  useEffect(() => {
    const stored = (localStorage.getItem(THEME_KEY) as Theme) ?? "dark";
    setTheme(stored === "light" ? "light" : "dark");
  }, []);

  function toggleTheme() {
    const next: Theme = theme === "dark" ? "light" : "dark";
    setTheme(next);
    applyTheme(next);
    localStorage.setItem(THEME_KEY, next);
  }

  const link = (href: string, Icon: typeof Info, label: string) => (
    <DropdownMenuItem asChild className="cursor-pointer gap-2.5 py-2">
      <Link href={href}>
        <Icon className="h-4 w-4 text-[var(--accent)] flex-none" />
        <span className="text-[13px] text-[var(--fg-1)]">{label}</span>
      </Link>
    </DropdownMenuItem>
  );

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-label="Меню"
          title="Меню"
          data-testid="overflow-menu"
          className="inline-flex items-center justify-center h-[34px] w-[34px] rounded-md text-[var(--fg-3)] hover:text-[var(--fg-1)] hover:bg-[var(--bg-2)] border border-transparent hover:border-[var(--bd-2)] transition-colors flex-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
        >
          <MoreHorizontal className="h-[18px] w-[18px]" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-[224px]">
        <DropdownMenuItem
          onClick={toggleTheme}
          className="cursor-pointer gap-2.5 py-2"
          data-testid="theme-toggle"
        >
          {theme === "dark" ? (
            <Sun className="h-4 w-4 text-[var(--accent)]" />
          ) : (
            <Moon className="h-4 w-4 text-[var(--accent)]" />
          )}
          <span className="text-[13px] text-[var(--fg-1)]">
            {theme === "dark" ? "Светлая тема" : "Тёмная тема"}
          </span>
        </DropdownMenuItem>
        {link("/status", Activity, "Диагностика")}
        {link("/guide", BookOpen, "Гайд аналитика")}
        {link("/settings/skills", Sliders, "Навыки")}
        {link("/settings/memory", Brain, "Память")}
        {link("/about", Info, "О приложении")}
        <DropdownMenuSeparator />
        {link("/settings", Settings, "Настройки")}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
