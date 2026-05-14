"use client";

import { useEffect, useRef } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Message } from "./Message";
import type { ChatMessage } from "@/lib/types";

interface ThreadProps {
  messages: ChatMessage[];
}

export function Thread({ messages }: ThreadProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll вниз при появлении новых сообщений (стриминг и загрузка истории)
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // tool-сообщения не рендерятся в Thread — только в Trace panel (Plan 2.5)
  const visibleMessages = messages.filter((m) => m.role !== "tool");

  return (
    <ScrollArea className="h-full">
      <div className="flex flex-col gap-4 p-4 max-w-4xl mx-auto">
        {visibleMessages.map((msg) => (
          <Message key={msg.id} message={msg} />
        ))}
        <div ref={bottomRef} />
      </div>
    </ScrollArea>
  );
}
