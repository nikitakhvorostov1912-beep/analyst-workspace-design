import { describe, expect, it } from "vitest";

import { type FlowNode, shortName, toFlowElements, X_GAP, Y_GAP } from "../graph-card";
import type { GraphCardPayload } from "../types";

// A(0) → B(1) → C(2), A(0) → D(1).  CALLS + USES.
const PAYLOAD: GraphCardPayload = {
  center: { qualified_name: "Module.A", node_kind: "Method" },
  nodes: [
    { id: 1, node_kind: "Method", qualified_name: "Module.A", depth: 0 },
    { id: 2, node_kind: "Method", qualified_name: "Module.B", depth: 1 },
    { id: 4, node_kind: "Method", qualified_name: "Module.D", depth: 1 },
    { id: 3, node_kind: "Method", qualified_name: "Module.C", depth: 2 },
  ],
  edges: [
    { src_id: 1, dst_id: 2, edge_kind: "CALLS" },
    { src_id: 2, dst_id: 3, edge_kind: "CALLS" },
    { src_id: 1, dst_id: 4, edge_kind: "USES" },
  ],
  total_reached: 4,
  truncated: false,
};

function nodeGetter(nodes: FlowNode[]) {
  return (id: string): FlowNode => {
    const n = nodes.find((x) => x.id === id);
    if (!n) throw new Error(`node ${id} not found`);
    return n;
  };
}

describe("toFlowElements", () => {
  it("раскладывает узлы слоями по depth (x=depth, y=индекс в слое)", () => {
    const { nodes } = toFlowElements(PAYLOAD);
    expect(nodes).toHaveLength(4);
    const get = nodeGetter(nodes);
    expect(get("1").position).toEqual({ x: 0, y: 0 }); // A depth 0
    expect(get("2").position).toEqual({ x: X_GAP, y: 0 }); // B depth1 idx0
    expect(get("4").position).toEqual({ x: X_GAP, y: Y_GAP }); // D depth1 idx1
    expect(get("3").position).toEqual({ x: 2 * X_GAP, y: 0 }); // C depth2
    expect(get("1").data.label).toBe("A"); // короткое имя
    expect(get("1").data.full).toBe("Module.A");
  });

  it("подсвечивает только центральный узел (depth 0)", () => {
    const { nodes } = toFlowElements(PAYLOAD);
    const get = nodeGetter(nodes);
    expect(get("1").style).toBeDefined();
    expect(String(get("1").style?.border)).toContain("var(--accent)");
    expect(get("2").style).toBeUndefined();
    expect(get("3").style).toBeUndefined();
  });

  it("маппит рёбра: source/target строкой, animated только для CALLS", () => {
    const { edges } = toFlowElements(PAYLOAD);
    expect(edges).toHaveLength(3);
    const calls = edges.find((e) => e.id === "1-2-CALLS");
    expect(calls).toMatchObject({ source: "1", target: "2", label: "CALLS", animated: true });
    const uses = edges.find((e) => e.id === "1-4-USES");
    expect(uses).toMatchObject({ source: "1", target: "4", label: "USES", animated: false });
  });

  it("пустой подграф → пустые наборы", () => {
    const empty = toFlowElements({
      center: null, nodes: [], edges: [], total_reached: 0, truncated: false,
    });
    expect(empty.nodes).toHaveLength(0);
    expect(empty.edges).toHaveLength(0);
  });
});

describe("shortName", () => {
  it("берёт последний сегмент qualified_name", () => {
    expect(shortName("AccumulationRegister.Выручка.RecordSetModule.ПередЗаписью")).toBe(
      "ПередЗаписью",
    );
    expect(shortName("Одно")).toBe("Одно");
  });
});
