"use client";

import Link from "next/link";
import { Activity, BookOpen, HelpCircle, Info } from "lucide-react";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

/**
 * Меню справки (redesign 2.0 §3.6, F-03). Заменяет три неразличимые иконки
 * (Activity / BookOpen / HelpCircle) в шапке одним меню «?» с ТЕКСТОВЫМИ
 * подписями — пользователь сразу понимает, куда ведёт каждый пункт.
 */

const ITEMS = [
  { href: "/status", icon: Activity, label: "Диагностика", hint: "что работает или нет" },
  { href: "/guide", icon: BookOpen, label: "Гайд аналитика", hint: "как пользоваться" },
  { href: "/about", icon: Info, label: "О приложении", hint: "что это" },
];

export function HelpMenu() {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-label="Справка"
          title="Справка"
          className="inline-flex items-center justify-center h-8 w-8 rounded-md text-[var(--fg-3)] hover:text-[var(--fg-1)] hover:bg-[var(--bg-2)] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
        >
          <HelpCircle className="h-[15px] w-[15px]" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-[220px]">
        {ITEMS.map((it) => {
          const Icon = it.icon;
          return (
            <DropdownMenuItem key={it.href} asChild className="cursor-pointer gap-2.5 py-2">
              <Link href={it.href}>
                <Icon className="h-4 w-4 text-[var(--accent)] flex-none" />
                <span className="flex flex-col">
                  <span className="text-[13px] text-[var(--fg-1)]">{it.label}</span>
                  <span className="text-[11px] text-[var(--fg-3)]">{it.hint}</span>
                </span>
              </Link>
            </DropdownMenuItem>
          );
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
