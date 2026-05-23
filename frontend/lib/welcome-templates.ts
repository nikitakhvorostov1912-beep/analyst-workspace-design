import type { ComponentType } from "react";
import {
  BarChart3,
  Box,
  FileText,
  RotateCcw,
  ScrollText,
  Search,
  Users,
} from "lucide-react";

/**
 * Sprint 03 (handoff 06 · Welcome → ComposerHub): шаблоны быстрых вопросов
 * для welcome screen.
 *
 * Аналитик жмёт чип → text вставляется в композер (но не отправляется), курсор
 * остаётся на конце — он может дописать конкретику и нажать Enter.
 *
 * «↺ Повторить последний» — динамический: title подменяется на «↺ Повторить
 * "{first 30 chars of last user msg}…"», text = это сообщение. Берётся из
 * `lastUserMessage` prop (если есть).
 */
export interface WelcomeTemplate {
  id: string;
  /** Что показывается на чипе */
  title: string;
  /** Что вставляется в composer (обычно с пробелом в конце для удобства ввода) */
  text: string;
  /** Иконка слева. Опционально. */
  icon?: ComponentType<{ className?: string }>;
}

export const WELCOME_TEMPLATES: WelcomeTemplate[] = [
  {
    id: "find-counterparty",
    title: "Найти контрагента по ИНН",
    text: "Найди контрагента с ИНН ",
    icon: Search,
  },
  {
    id: "sales-period",
    title: "Продажи за период",
    text: "Покажи продажи за апрель 2026 с разбивкой по складам",
    icon: BarChart3,
  },
  {
    id: "doc-by-number",
    title: "Документ по номеру",
    text: "Покажи документ № ",
    icon: FileText,
  },
  {
    id: "user-actions",
    title: "Действия пользователя",
    text: "Что делал пользователь ",
    icon: Users,
  },
  {
    id: "stock-balance",
    title: "Остатки на складе",
    text: "Остатки на складе ",
    icon: Box,
  },
  {
    id: "event-log-errors",
    title: "Ошибки в журнале",
    text: "Покажи ошибки в журнале регистрации за сегодня",
    icon: ScrollText,
  },
];

/**
 * Возвращает динамический «↺ Повторить последний» — title с превью первого
 * сообщения. Если нет последнего сообщения — возвращает null (не показываем).
 */
export function buildRepeatTemplate(
  lastUserMessage: string | null,
): WelcomeTemplate | null {
  if (!lastUserMessage || lastUserMessage.trim().length === 0) return null;
  const trimmed = lastUserMessage.trim();
  const preview =
    trimmed.length > 30 ? `${trimmed.slice(0, 30)}…` : trimmed;
  return {
    id: "repeat-last",
    title: `↺ Повторить «${preview}»`,
    text: trimmed,
    icon: RotateCcw,
  };
}
