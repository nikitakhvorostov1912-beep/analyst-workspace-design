import type { ComponentType } from "react";
import {
  BarChart3,
  BookMarked,
  Box,
  Boxes,
  FileText,
  GitBranch,
  RotateCcw,
  ScrollText,
  Search,
} from "lucide-react";

/**
 * Шаблоны быстрых вопросов для welcome screen.
 *
 * Аналитик жмёт чип → text вставляется в композер (не отправляется), курсор
 * в конце — он дописывает конкретику и жмёт Enter.
 *
 * P1 (user-facing): шаблоны сгруппированы по ТРЁМ источникам знаний, чтобы
 * пользователь с первого экрана понял, что можно спрашивать не только про
 * свою базу, но и про устройство типовой и про методики ИТС.
 */
export type TemplateGroup = "база" | "типовая" | "итс";

export interface WelcomeTemplate {
  id: string;
  /** Что показывается на чипе */
  title: string;
  /** Что вставляется в composer (обычно с пробелом в конце для удобства ввода) */
  text: string;
  /** Иконка слева. Опционально. */
  icon?: ComponentType<{ className?: string }>;
  /** Источник знаний, к которому относится пример. */
  group: TemplateGroup;
}

/** Метаданные групп для рендера (порядок + подпись). */
export const TEMPLATE_GROUPS: { id: TemplateGroup; label: string }[] = [
  { id: "база", label: "По вашей базе" },
  { id: "типовая", label: "По типовой конфигурации" },
  { id: "итс", label: "По ИТС · Напарнику" },
];

/**
 * Единый набор примеров-подсказок (F-12) — один источник для пустого экрана
 * на главной (ComposerHub группирует) и в пустом чате (Thread показывает списком).
 * Нейтральная «вы»-формулировка без повелительного «покажи/найди».
 */
export const EXAMPLE_PROMPTS: readonly string[] = [
  "Список метаданных базы",
  "Документы реализации за май 2026",
  "Контрагент с ИНН 7707083893",
  "10 последних ошибок из журнала регистрации",
];

export const WELCOME_TEMPLATES: WelcomeTemplate[] = [
  // --- Ваша живая база 1С ---
  {
    id: "find-counterparty",
    title: "Найти контрагента по ИНН",
    text: "Найди контрагента с ИНН ",
    icon: Search,
    group: "база",
  },
  {
    id: "stock-balance",
    title: "Остатки на складе",
    text: "Остатки на складе ",
    icon: Box,
    group: "база",
  },
  {
    id: "event-log-errors",
    title: "Ошибки в журнале",
    text: "Покажи ошибки в журнале регистрации за сегодня",
    icon: ScrollText,
    group: "база",
  },
  {
    id: "sales-period",
    title: "Продажи за период",
    text: "Покажи продажи за апрель 2026 с разбивкой по складам",
    icon: BarChart3,
    group: "база",
  },
  // --- Устройство типовой конфигурации (граф + карточки) ---
  {
    id: "typical-object",
    title: "Как устроена Реализация в УТ",
    text: "Как устроен типовой документ Реализация товаров и услуг в УТ 11.5: назначение, ключевые реквизиты, движения",
    icon: Boxes,
    group: "типовая",
  },
  {
    id: "typical-movements",
    title: "Куда пишет движения документ",
    text: "По каким регистрам делает движения Приходный кассовый ордер в БП 3.0",
    icon: GitBranch,
    group: "типовая",
  },
  // --- ИТС / Напарник (живая методология) ---
  {
    id: "its-month-close",
    title: "Как закрыть месяц (ИТС)",
    text: "Как по методике ИТС правильно закрыть месяц в УТ 11.5? Дай ссылки на статьи ИТС",
    icon: BookMarked,
    group: "итс",
  },
  {
    id: "its-method",
    title: "Методика по ИТС",
    text: "Что рекомендует ИТС по ",
    icon: FileText,
    group: "итс",
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
    group: "база",
  };
}
