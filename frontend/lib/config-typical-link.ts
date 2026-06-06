import type { TypicalConfigurationDTO } from "@/lib/api";

/**
 * Связь между конфигурацией клиентской базы (детект/override, см.
 * ConfigurationBadge.OVERRIDE_OPTIONS) и видом эталонной типовой
 * (TypicalConfigurationDTO.config_kind). Используется, чтобы авто-привязать
 * активную типовую к конфе текущей базы — без отдельной плашки выбора.
 */
export const CONFIG_TO_TYPICAL_KIND: Record<string, string> = {
  "УТ 11.5": "UT_115",
  "ERP 2.5": "ERP_25",
  "КА 2.5": "KA_2",
  "БП 3.0": "BP_30",
  "ЗУП 3.1": "ZUP_31",
  "УСО 2.5": "USO_25",
  // «Самописная» — намеренно отсутствует: типовой эталон не подбирается.
};

/** Читаемые ярлыки видов типовой (для подсказок и списка «сравнить с типовой»). */
export const TYPICAL_KIND_LABELS: Record<string, string> = {
  UT_115: "УТ 11.5",
  ERP_25: "ERP 2.5",
  KA_2: "КА 2",
  BP_30: "БП 3.0",
  ZUP_31: "ЗУП 3.1",
  USO_25: "УСО 2.5",
  DOCFLOW_3: "Документооборот 3",
};

/**
 * channel_id загруженной типовой, соответствующей конфе базы, или null,
 * если вид не маппится / типовая такого вида не загружена.
 */
export function resolveTypicalChannelId(
  configuration: string | null | undefined,
  typicals: TypicalConfigurationDTO[],
): string | null {
  if (!configuration) return null;
  const kind = CONFIG_TO_TYPICAL_KIND[configuration];
  if (!kind) return null;
  const match = typicals.find((t) => t.config_kind === kind);
  return match ? match.channel_id : null;
}
