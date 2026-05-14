import { ScrollArea } from "@/components/ui/scroll-area";
import { Message } from "./Message";
import type { ChatMessage } from "@/lib/types";

interface ThreadProps {
  messages: ChatMessage[];
}

export function Thread({ messages }: ThreadProps) {
  return (
    <ScrollArea className="h-full">
      <div className="flex flex-col gap-4 p-4 max-w-4xl mx-auto">
        {messages.map((msg) => (
          <Message key={msg.id} message={msg} />
        ))}
      </div>
    </ScrollArea>
  );
}
