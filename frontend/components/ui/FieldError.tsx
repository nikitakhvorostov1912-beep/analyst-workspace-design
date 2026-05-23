"use client";

import { AlertCircle } from "lucide-react";

interface FieldErrorProps {
  message?: string | null;
  /** Связать с input id через aria-describedby */
  id?: string;
}

/**
 * FieldError — единая компонента валидации форм.
 *
 * Sprint 02 (handoff 2026-05-23, C): заменяет 17+ inline
 * `<p className="text-xs text-red-400 mt-1">` по всей кодовой базе.
 *
 * - `role="alert"` — скринридер озвучивает ошибку при появлении
 * - `AlertCircle` icon — визуальный сигнал перед текстом
 * - Цвет через семантический токен `--error` — работает в обеих темах
 *
 * Использование с input:
 * ```tsx
 * <Input aria-invalid={!!errors.x} aria-describedby="x-error" />
 * <FieldError id="x-error" message={errors.x} />
 * ```
 */
export function FieldError({ message, id }: FieldErrorProps) {
  if (!message) return null;
  return (
    <p
      id={id}
      role="alert"
      className="flex items-start gap-1.5 text-xs text-[var(--error)] mt-1 leading-tight"
    >
      <AlertCircle className="h-3 w-3 flex-none mt-[2px]" aria-hidden="true" />
      <span>{message}</span>
    </p>
  );
}
