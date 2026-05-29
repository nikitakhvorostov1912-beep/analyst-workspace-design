/**
 * GraphCard — чистая раскладка подграфа (get_subgraph payload) в элементы
 * React Flow. Вынесена ОТДЕЛЬНО от компонента: React Flow рендер требует
 * DOM-измерений (ResizeObserver), а эту логику тестируем напрямую в vitest.
 *
 * Раскладка слоями по depth: x = depth (колонка), y = индекс в слое (строка).
 * Центр (depth 0) подсвечен accent-рамкой.
 *
 * Типы FlowNode/FlowEdge минимальны и структурно совместимы с React Flow
 * Node/Edge — компонент (GraphCard.tsx) кастует их к типам @xyflow/react.
 * Так utils остаются без runtime-зависимости от React Flow.
 */
import type { GraphCardPayload, GraphNodePayload } from "./types";

export type FlowNode = {
  id: string;
  position: { x: number; y: number };
  data: { label: string; full: string; kind: string; depth: number };
  sourcePosition: "right";
  targetPosition: "left";
  style?: Record<string, string | number>;
};

export type FlowEdge = {
  id: string;
  source: string;
  target: string;
  label: string;
  animated: boolean;
};

export const X_GAP = 230;
export const Y_GAP = 64;

/** Короткое имя узла — последний сегмент qualified_name для подписи. */
export function shortName(qname: string): string {
  const parts = qname.split(".");
  return parts[parts.length - 1] || qname;
}

export function toFlowElements(payload: GraphCardPayload): {
  nodes: FlowNode[];
  edges: FlowEdge[];
} {
  const byDepth = new Map<number, GraphNodePayload[]>();
  for (const n of payload.nodes) {
    const arr = byDepth.get(n.depth) ?? [];
    arr.push(n);
    byDepth.set(n.depth, arr);
  }

  const nodes: FlowNode[] = payload.nodes.map((n) => {
    const layer = byDepth.get(n.depth) ?? [];
    const idx = layer.indexOf(n);
    const isCenter = n.depth === 0;
    return {
      id: String(n.id),
      position: { x: n.depth * X_GAP, y: idx * Y_GAP },
      data: {
        label: shortName(n.qualified_name),
        full: n.qualified_name,
        kind: n.node_kind,
        depth: n.depth,
      },
      sourcePosition: "right",
      targetPosition: "left",
      style: isCenter
        ? { border: "2px solid var(--accent)", fontWeight: 600 }
        : undefined,
    };
  });

  const edges: FlowEdge[] = payload.edges.map((e) => ({
    id: `${e.src_id}-${e.dst_id}-${e.edge_kind}`,
    source: String(e.src_id),
    target: String(e.dst_id),
    label: e.edge_kind,
    animated: e.edge_kind === "CALLS",
  }));

  return { nodes, edges };
}
