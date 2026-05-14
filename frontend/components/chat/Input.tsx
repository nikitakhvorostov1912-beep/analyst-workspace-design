"use client";

import { useRef, useState, type KeyboardEvent } from "react";
import { Button } from "@/components/ui/button";
import { getLLMConfig } from "@/lib/storage";
import { Send } from "lucide-react";

interface ChatInputProps {
  onSubmit?: (message: string) => void;
  disabled?: boolean;
  /** Если disabled по причине MCP disconnected — показать подсказку */
  disabledReason?: "banner" | "streaming" | null;
}

export function ChatInput({ onSubmit, disabled, disabledReason }: ChatInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  function handleSubmit() {
    if (disabled) return;
    const text = value.trim();
    if (!text) return;

    const cfg = getLLMConfig();
    if (!cfg) {
      alert("Подключите MCP и LLM в настройках");
      return;
    }

    setValue("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "56px";
    }

    if (onSubmit) {
      onSubmit(text);
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      handleSubmit();
    }
  }

  function handleInput() {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "56px";
    el.style.height = `${Math.min(el.scrollHeight, 240)}px`;
  }

  return (
    <div className="flex flex-col gap-1 p-3">
      {disabledReason === "banner" && (
        <p className="text-xs text-red-400 px-1">
          Нет соединения с базой. Восстановите подключение для отправки.
        </p>
      )}
      <div className="flex items-end gap-2">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onInput={handleInput}
          placeholder="Спросите про базу 1С..."
          rows={1}
          readOnly={disabled}
          className="flex-1 resize-none rounded-md border border-[var(--border)] bg-[var(--bg-elevated)] px-3 py-3 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)] transition-colors disabled:opacity-50"
          style={{ minHeight: "56px", maxHeight: "240px", height: "56px" }}
        />
        <Button
          size="icon"
          onClick={handleSubmit}
          disabled={!value.trim() || disabled}
          aria-label="Отправить"
          className="flex-none mb-0.5"
        >
          <Send size={16} />
        </Button>
      </div>
    </div>
  );
}
