/**
 * Sprint 03 (handoff 06 · Channel selector enrichment): относительное время
 * на русском («5 минут назад», «вчера», «2 дня назад»).
 *
 * Использует `Intl.RelativeTimeFormat` с `numeric: 'auto'` — он сам подбирает
 * «сегодня / вчера / завтра» вместо «0 days ago» и формирует правильную форму
 * множественного числа по русским правилам (одна / две / пять минут).
 */
const RTF = new Intl.RelativeTimeFormat("ru", { numeric: "auto" });

export function formatRelativeTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "—";

  const now = Date.now();
  const diff = (then - now) / 1000; // в секундах, отрицательное = в прошлом

  if (Math.abs(diff) < 60) return RTF.format(Math.round(diff), "second");
  if (Math.abs(diff) < 3600) return RTF.format(Math.round(diff / 60), "minute");
  if (Math.abs(diff) < 86400) return RTF.format(Math.round(diff / 3600), "hour");
  return RTF.format(Math.round(diff / 86400), "day");
}

/** Plural-форма для «объект» / «объекта» / «объектов» */
export function pluralObject(n: number): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod100 >= 11 && mod100 <= 14) return "объектов";
  if (mod10 === 1) return "объект";
  if (mod10 >= 2 && mod10 <= 4) return "объекта";
  return "объектов";
}

/** Plural-форма для «инструмент» / «инструмента» / «инструментов» */
export function pluralTool(n: number): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod100 >= 11 && mod100 <= 14) return "инструментов";
  if (mod10 === 1) return "инструмент";
  if (mod10 >= 2 && mod10 <= 4) return "инструмента";
  return "инструментов";
}
