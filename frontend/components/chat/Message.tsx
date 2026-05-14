import { cn } from "@/lib/utils";
import type { ChatMessage } from "@/lib/types";

interface MessageProps {
  message: ChatMessage;
}

export function Message({ message }: MessageProps) {
  const isUser = message.role === "user";

  return (
    <div
      className={cn(
        "flex w-full",
        isUser ? "justify-end" : "justify-start",
      )}
    >
      <div
        className={cn(
          "max-w-3xl rounded-lg p-4 text-sm leading-relaxed",
          isUser
            ? "bg-[var(--bg-elevated)] text-[var(--fg)] border border-[var(--border)]"
            : "text-[var(--fg)]",
        )}
      >
        {/* Роль */}
        {!isUser && (
          <div className="text-xs text-[var(--fg-muted)] mb-1 font-medium">
            Ассистент
          </div>
        )}
        {/* Контент рендерится как plain text (T-01-11: защита от XSS) */}
        <p className="whitespace-pre-wrap break-words">{message.content}</p>
      </div>
    </div>
  );
}
