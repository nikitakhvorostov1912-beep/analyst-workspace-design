"use client";

import type { ComponentType } from "react";
import { MoreHorizontal } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface CardActionItem {
  label: string;
  icon?: ComponentType<{ className?: string }>;
  onClick?: () => void;
  kbd?: string;
  destructive?: boolean;
}

interface CardActionMenuProps {
  items: (CardActionItem | "separator")[];
  align?: "start" | "end";
  triggerAriaLabel?: string;
}

export function CardActionMenu({
  items,
  align = "end",
  triggerAriaLabel = "Действия",
}: CardActionMenuProps) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7"
          aria-label={triggerAriaLabel}
          data-testid="card-action-trigger"
        >
          <MoreHorizontal className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align={align}
        className="min-w-[180px] animate-scale-in"
      >
        {items.map((item, i) => {
          if (item === "separator") {
            return <DropdownMenuSeparator key={`sep-${i}`} />;
          }
          const Icon = item.icon;
          return (
            <DropdownMenuItem
              key={`${item.label}-${i}`}
              onClick={item.onClick}
              className={cn(
                item.destructive &&
                  "text-[var(--error)] focus:text-[var(--error)]",
              )}
            >
              {Icon && <Icon className="h-3.5 w-3.5 mr-2" />}
              <span className="flex-1">{item.label}</span>
              {item.kbd && (
                <kbd className="ml-auto text-xs text-[var(--fg-3)] bg-[var(--bg-2)] px-1.5 py-0.5 rounded">
                  {item.kbd}
                </kbd>
              )}
            </DropdownMenuItem>
          );
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
