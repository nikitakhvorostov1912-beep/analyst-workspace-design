"use client";

import type { ComponentType } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface EmptyStateAction {
  label: string;
  onClick?: () => void;
  href?: string;
}

interface EmptyStateProps {
  icon?: ComponentType<{ className?: string }>;
  title: string;
  description?: string;
  cta?: EmptyStateAction;
  className?: string;
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  cta,
  className,
}: EmptyStateProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        "flex flex-col items-center justify-center text-center max-w-md mx-auto py-12 px-6",
        className,
      )}
    >
      {Icon && (
        <div className="h-12 w-12 rounded-full bg-[var(--accent-08)] border border-[var(--accent-20)] text-[var(--accent)] inline-flex items-center justify-center mb-4">
          <Icon className="h-6 w-6" />
        </div>
      )}
      <h3 className="text-base font-medium text-[var(--fg-1)] mb-1.5">{title}</h3>
      {description && (
        <p className="text-sm text-[var(--fg-3)] leading-relaxed">{description}</p>
      )}
      {cta && (
        <div className="mt-5">
          {cta.href ? (
            <a href={cta.href}>
              <Button>{cta.label}</Button>
            </a>
          ) : (
            <Button onClick={cta.onClick}>{cta.label}</Button>
          )}
        </div>
      )}
    </div>
  );
}
