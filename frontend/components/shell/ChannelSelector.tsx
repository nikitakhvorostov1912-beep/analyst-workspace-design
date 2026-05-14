"use client";

import { useEffect, useState } from "react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { getMCPConnections, getActiveChannelId, setActiveChannelId } from "@/lib/storage";
import type { MCPConnection } from "@/lib/types";

export function ChannelSelector() {
  const [connections, setConnections] = useState<MCPConnection[]>([]);
  const [activeId, setActiveId] = useState<string>("");

  useEffect(() => {
    const conns = getMCPConnections();
    setConnections(conns);
    const current = getActiveChannelId();
    if (current) setActiveId(current);
  }, []);

  function handleChange(value: string) {
    setActiveId(value);
    setActiveChannelId(value);
  }

  if (connections.length === 0) {
    return (
      <div className="flex items-center h-9 px-3 rounded-md border border-[var(--border)] bg-[var(--bg-elevated)] text-sm text-[var(--fg-muted)] select-none min-w-[200px]">
        Подключения не настроены
      </div>
    );
  }

  return (
    <Select value={activeId} onValueChange={handleChange}>
      <SelectTrigger className="min-w-[200px]">
        <SelectValue placeholder="Выберите подключение" />
      </SelectTrigger>
      <SelectContent>
        {connections.map((conn) => (
          <SelectItem key={conn.id} value={conn.id}>
            {conn.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
