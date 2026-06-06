import { describe, it, expect } from "vitest";
import {
  CONFIG_TO_TYPICAL_KIND,
  TYPICAL_KIND_LABELS,
  resolveTypicalChannelId,
} from "@/lib/config-typical-link";
import type { TypicalConfigurationDTO } from "@/lib/api";

function typ(channel_id: string, config_kind: string): TypicalConfigurationDTO {
  return {
    channel_id,
    config_kind,
    config_version: "x",
    display_name: channel_id,
    status: "graph_built",
    indexed_at: null,
    source_path: null,
    node_counts: {},
    card_counts: {},
    total_nodes: 0,
    total_cards: 0,
  };
}

describe("config-typical-link", () => {
  const loaded = [typ("_ka2_25", "KA_2"), typ("_ut115", "UT_115")];

  it("маппинг покрывает все override-опции кроме Самописной", () => {
    expect(CONFIG_TO_TYPICAL_KIND["КА 2.5"]).toBe("KA_2");
    expect(CONFIG_TO_TYPICAL_KIND["УТ 11.5"]).toBe("UT_115");
    expect(CONFIG_TO_TYPICAL_KIND["ERP 2.5"]).toBe("ERP_25");
    expect(CONFIG_TO_TYPICAL_KIND["БП 3.0"]).toBe("BP_30");
    expect(CONFIG_TO_TYPICAL_KIND["ЗУП 3.1"]).toBe("ZUP_31");
    expect(CONFIG_TO_TYPICAL_KIND["УСО 2.5"]).toBe("USO_25");
    expect(CONFIG_TO_TYPICAL_KIND["Самописная"]).toBeUndefined();
  });

  it("находит channel_id типовой того же вида", () => {
    expect(resolveTypicalChannelId("КА 2.5", loaded)).toBe("_ka2_25");
    expect(resolveTypicalChannelId("УТ 11.5", loaded)).toBe("_ut115");
  });

  it("kind известен, но типовая не загружена → null", () => {
    expect(resolveTypicalChannelId("ERP 2.5", loaded)).toBeNull();
  });

  it("Самописная / null / неизвестная строка → null", () => {
    expect(resolveTypicalChannelId("Самописная", loaded)).toBeNull();
    expect(resolveTypicalChannelId(null, loaded)).toBeNull();
    expect(resolveTypicalChannelId("Нечто", loaded)).toBeNull();
  });

  it("ярлыки видов читаемы", () => {
    expect(TYPICAL_KIND_LABELS["KA_2"]).toBe("КА 2");
    expect(TYPICAL_KIND_LABELS["UT_115"]).toBe("УТ 11.5");
  });
});
