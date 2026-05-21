import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

/**
 * Парсит datetime-строку из backend как UTC.
 *
 * Backend использует `datetime.utcnow()` и Pydantic сериализует БЕЗ суффикса
 * `Z` или `+00:00` (например, `"2026-05-21T12:25:50"`). По ISO 8601 такая
 * строка считается ЛОКАЛЬНОЙ — и `new Date()` так и парсит. Для пользователя
 * в Москве (+3) свежесозданная запись отображалась как «3 часа назад».
 *
 * Если в строке нет маркера TZ — форсируем UTC. Если есть (`Z` / `+HH:MM`) —
 * парсим как есть. Это обратно совместимо с будущим переходом backend на
 * timezone-aware datetimes.
 */
export function parseBackendDate(isoString: string): Date {
  const hasTimezone = /Z$|[+-]\d{2}:?\d{2}$/.test(isoString);
  return new Date(hasTimezone ? isoString : isoString + "Z");
}
