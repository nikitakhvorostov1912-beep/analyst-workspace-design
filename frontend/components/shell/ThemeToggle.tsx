"use client";

import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";

type Theme = "dark" | "light";

const STORAGE_KEY = "analyst-theme";

function readStoredTheme(): Theme {
  if (typeof window === "undefined") return "dark";
  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (stored === "light" || stored === "dark") return stored;
  return "dark"; // Stencil brand — dark by default
}

function applyTheme(theme: Theme): void {
  const root = document.documentElement;
  if (theme === "light") {
    root.setAttribute("data-theme", "light");
  } else {
    root.removeAttribute("data-theme");
  }
}

/**
 * Stencil brand support — переключалка тем (dark ↔ light Sand).
 *
 * Brand guide содержит две темы:
 *   - Dark (Ink #15161A) — default для чата и работы
 *   - Light (Sand #F3F1EC) — про-форс, splash, about, печатные формы
 *
 * Сохраняет выбор в localStorage. Без backend-state — это персональная
 * настройка устройства, не аккаунта.
 */
export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>("dark");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const initial = readStoredTheme();
    setTheme(initial);
    applyTheme(initial);
    setMounted(true);
  }, []);

  function toggle() {
    const next: Theme = theme === "dark" ? "light" : "dark";
    setTheme(next);
    applyTheme(next);
    window.localStorage.setItem(STORAGE_KEY, next);
  }

  // SSR-safe: до hydration рендерим в нейтральном состоянии (dark icon)
  // чтобы не мигало при смене темы из localStorage.
  if (!mounted) {
    return (
      <Button
        variant="ghost"
        size="icon"
        className="h-[30px] w-[30px] text-[var(--fg-3)]"
        aria-label="Тема"
        disabled
      >
        <Moon className="h-[15px] w-[15px]" />
      </Button>
    );
  }

  const isDark = theme === "dark";
  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={toggle}
      className="h-[30px] w-[30px] text-[var(--fg-3)] hover:text-[var(--fg-1)]"
      aria-label={isDark ? "Светлая тема" : "Тёмная тема"}
      title={isDark ? "Светлая тема (Sand)" : "Тёмная тема (Ink)"}
      data-testid="theme-toggle"
    >
      {isDark ? <Sun className="h-[15px] w-[15px]" /> : <Moon className="h-[15px] w-[15px]" />}
    </Button>
  );
}
