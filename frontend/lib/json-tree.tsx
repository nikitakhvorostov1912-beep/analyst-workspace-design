"use client";
import { useState, type ReactNode } from "react";

type JsonTreeProps = {
  value: unknown;
  defaultExpanded?: number;
  /** Внутренний параметр рекурсии — не передавать снаружи. */
  _depth?: number;
};

function isCircular(value: unknown): boolean {
  try {
    JSON.stringify(value);
    return false;
  } catch {
    return true;
  }
}

function truncateStr(s: string, max = 200): string {
  return s.length > max ? s.slice(0, max) + "⋯" : s;
}

export function JsonTree({
  value,
  defaultExpanded = 1,
  _depth = 0,
}: JsonTreeProps): ReactNode {
  const indent = Math.min(_depth * 12, 240);

  // Primitive: string
  if (typeof value === "string") {
    return (
      <div style={{ paddingLeft: indent }} className="font-mono text-xs tabular-nums">
        <span className="text-green-300">&quot;{truncateStr(value)}&quot;</span>
      </div>
    );
  }

  // Primitive: number
  if (typeof value === "number") {
    return (
      <div style={{ paddingLeft: indent }} className="font-mono text-xs tabular-nums">
        <span className="text-orange-300">{value}</span>
      </div>
    );
  }

  // Primitive: boolean
  if (typeof value === "boolean") {
    return (
      <div style={{ paddingLeft: indent }} className="font-mono text-xs tabular-nums">
        <span className="text-purple-300">{String(value)}</span>
      </div>
    );
  }

  // Primitive: null
  if (value === null) {
    return (
      <div style={{ paddingLeft: indent }} className="font-mono text-xs tabular-nums">
        <span className="text-purple-300">null</span>
      </div>
    );
  }

  // Primitive: undefined
  if (typeof value === "undefined") {
    return (
      <div style={{ paddingLeft: indent }} className="font-mono text-xs tabular-nums">
        <span className="text-[var(--fg-muted)] italic">undefined</span>
      </div>
    );
  }

  // Circular reference detection
  if (isCircular(value)) {
    return (
      <div style={{ paddingLeft: indent }} className="font-mono text-xs tabular-nums">
        <span className="text-red-400">[Circular]</span>
      </div>
    );
  }

  // Array
  if (Array.isArray(value)) {
    if (value.length === 0) {
      return (
        <div style={{ paddingLeft: indent }} className="font-mono text-xs text-[var(--fg-muted)] tabular-nums">
          []
        </div>
      );
    }
    return (
      <CollapsibleNode
        header={`[${value.length}]`}
        defaultExpanded={defaultExpanded > _depth}
        depth={_depth}
      >
        {value.map((item, i) => (
          <div key={i} className="flex">
            <span
              style={{ paddingLeft: indent + 12 }}
              className="font-mono text-xs text-[var(--fg-muted)] select-none min-w-[2ch] mr-1 tabular-nums"
            >
              {i}:
            </span>
            <div className="flex-1">
              <JsonTree value={item} defaultExpanded={defaultExpanded} _depth={_depth + 1} />
            </div>
          </div>
        ))}
      </CollapsibleNode>
    );
  }

  // Object
  if (typeof value === "object") {
    const keys = Object.keys(value as Record<string, unknown>);
    if (keys.length === 0) {
      return (
        <div style={{ paddingLeft: indent }} className="font-mono text-xs text-[var(--fg-muted)] tabular-nums">
          &#123;&#125;
        </div>
      );
    }
    return (
      <CollapsibleNode
        header={`{${keys.length}}`}
        defaultExpanded={defaultExpanded > _depth}
        depth={_depth}
      >
        {keys.map((key) => (
          <div key={key} style={{ paddingLeft: indent + 12 }} className="font-mono text-xs tabular-nums">
            <span className="text-[var(--fg-muted)]">{key}:</span>
            <JsonTree
              value={(value as Record<string, unknown>)[key]}
              defaultExpanded={defaultExpanded}
              _depth={_depth + 1}
            />
          </div>
        ))}
      </CollapsibleNode>
    );
  }

  // Fallback
  return (
    <div style={{ paddingLeft: indent }} className="font-mono text-xs text-[var(--fg-muted)] tabular-nums">
      {String(value)}
    </div>
  );
}

type CollapsibleNodeProps = {
  header: string;
  defaultExpanded: boolean;
  depth: number;
  children: ReactNode;
};

function CollapsibleNode({ header, defaultExpanded, depth, children }: CollapsibleNodeProps): ReactNode {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const indent = Math.min(depth * 12, 240);

  return (
    <div>
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        style={{ paddingLeft: indent }}
        className="font-mono text-xs text-[var(--fg-muted)] hover:text-[var(--fg)] transition-colors cursor-pointer tabular-nums"
        aria-expanded={expanded}
      >
        {expanded ? "▾" : "▸"} {header}
      </button>
      {expanded && <div>{children}</div>}
    </div>
  );
}
