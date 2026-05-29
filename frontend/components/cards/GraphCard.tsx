"use client";

import { useMemo } from "react";
import {
  Background,
  Controls,
  type Edge,
  type Node,
  ReactFlow,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { CardHeader } from "./CardHeader";
import { toFlowElements } from "@/lib/graph-card";
import type { GraphCardPayload } from "@/lib/types";

/**
 * M-K3.17.7: GraphCard — визуализация L2-подграфа (граф вызовов / связей) через
 * React Flow. Данные приходят из get_subgraph (узлы с глубиной + индуцированные
 * рёбра). Раскладка — в lib/graph-card.toFlowElements (тестируется отдельно).
 */
export function GraphCard({ payload }: { payload: GraphCardPayload }) {
  const { nodes, edges } = useMemo(() => toFlowElements(payload), [payload]);

  const centerName = payload.center?.qualified_name ?? "Граф";
  const meta =
    `${payload.nodes.length} узлов · ${payload.edges.length} связей` +
    (payload.truncated
      ? ` · показаны первые ${payload.nodes.length} из ${payload.total_reached}`
      : "");

  return (
    <div className="rounded-lg border border-[var(--bd-1)] bg-[var(--bg-1)] overflow-hidden">
      <CardHeader
        type="graph"
        title={centerName}
        meta={meta}
        toolName={payload.tool_name}
      />
      {payload.nodes.length === 0 ? (
        <div className="p-4 text-xs text-[var(--fg-3)]">
          Подграф пуст — нет связей для отображения.
        </div>
      ) : (
        <div className="h-[360px] w-full" data-testid="graph-card-flow">
          <ReactFlow
            nodes={nodes as unknown as Node[]}
            edges={edges as unknown as Edge[]}
            colorMode="dark"
            fitView
            nodesDraggable={false}
            nodesConnectable={false}
            proOptions={{ hideAttribution: true }}
          >
            <Background />
            <Controls showInteractive={false} />
          </ReactFlow>
        </div>
      )}
    </div>
  );
}
