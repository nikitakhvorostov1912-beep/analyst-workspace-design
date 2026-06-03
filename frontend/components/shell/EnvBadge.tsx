import { cn } from "@/lib/utils";
import type { Environment } from "@/lib/types";

/** Подписи окружений для UI. */
export const ENV_LABEL: Record<Environment, string> = {
  prod: "ПРОД",
  test: "ТЕСТ",
  demo: "ДЕМО",
};

/**
 * Бейдж окружения базы 1С (shell v3 §4).
 *
 * prod — янтарь (`--warning`): критичный контекст «бьём в боевую».
 * test/demo — нейтрально. Нет данных (`null`/`undefined`) — бейдж не рендерится
 * (никогда не подставляем «prod» по умолчанию — ложная тревога хуже отсутствия).
 *
 * Строго `flex-none` инлайн-элемент: в чипе ChannelSelector переноса быть не
 * должно ни при каком имени.
 */
export function EnvBadge({ env }: { env?: Environment | null }) {
  if (!env) return null;
  const isProd = env === "prod";
  return (
    <span
      data-testid="env-badge"
      data-env={env}
      aria-label={isProd ? "боевая база — осторожно" : `окружение: ${ENV_LABEL[env]}`}
      className={cn(
        "px-1.5 py-[2px] rounded text-[8.5px] leading-none tracking-[0.16em] font-semibold uppercase border flex-none",
        isProd
          ? "text-[var(--warning)] border-[var(--warning-40)] bg-[var(--warning-12)]"
          : "text-[var(--fg-3)] border-[var(--bd-2)] bg-transparent",
      )}
      style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
    >
      {ENV_LABEL[env]}
    </span>
  );
}
