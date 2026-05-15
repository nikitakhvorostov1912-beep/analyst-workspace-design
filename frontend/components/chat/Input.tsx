"use client";

import { useRef, useState, type KeyboardEvent } from "react";
import { Button } from "@/components/ui/button";
import { QuickPrompts } from "@/components/chat/QuickPrompts";
import { SlashPopover } from "@/components/chat/SlashPopover";
import { MentionPopover } from "@/components/chat/MentionPopover";
import { getLLMConfig } from "@/lib/storage";
import { expandSlashCommand, type SlashCommand } from "@/lib/slash-commands";
import type { MetadataSuggestItem } from "@/lib/types";
import { Send } from "lucide-react";

interface ChatInputProps {
  onSubmit?: (message: string) => void;
  disabled?: boolean;
  /** Если disabled по причине MCP disconnected — показать подсказку */
  disabledReason?: "banner" | "streaming" | null;
  /** Channel ID для metadata suggest (@-mentions) */
  channelId?: string;
}

export function ChatInput({ onSubmit, disabled, disabledReason, channelId }: ChatInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Slash popover state
  const [slashOpen, setSlashOpen] = useState(false);
  const [slashQuery, setSlashQuery] = useState("");

  // Mention popover state
  const [mentionOpen, setMentionOpen] = useState(false);
  const [mentionQuery, setMentionQuery] = useState("");
  const [mentionStart, setMentionStart] = useState(-1);

  const anchorRef = useRef<HTMLDivElement>(null);

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
    setSlashOpen(false);
    setMentionOpen(false);
    if (textareaRef.current) {
      textareaRef.current.style.height = "56px";
    }

    if (onSubmit) {
      onSubmit(text);
    }
  }

  function handleChange(newValue: string) {
    setValue(newValue);

    const el = textareaRef.current;
    const cursor = el?.selectionStart ?? newValue.length;

    // Определяем контекст курсора — ищем / или @ до курсора
    const textBeforeCursor = newValue.slice(0, cursor);

    // Slash detection: / в начале слова (пробел перед / или начало строки)
    const slashMatch = textBeforeCursor.match(/(?:^|\s)\/(\S*)$/);
    if (slashMatch) {
      setSlashOpen(true);
      setSlashQuery("/" + slashMatch[1]);
      setMentionOpen(false);
    } else {
      setSlashOpen(false);
    }

    // Mention detection: @ после пробела или в начале
    const mentionMatch = textBeforeCursor.match(/(?:^|\s)@(\S*)$/);
    if (mentionMatch) {
      const atPos = textBeforeCursor.lastIndexOf("@");
      setMentionOpen(true);
      setMentionQuery(mentionMatch[1] ?? "");
      setMentionStart(atPos);
      setSlashOpen(false);
    } else if (!slashMatch) {
      setMentionOpen(false);
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    // Если popover открыт — ArrowUp/Down/Enter перехватываются SlashPopover/MentionPopover
    if (slashOpen || mentionOpen) {
      if (["ArrowUp", "ArrowDown", "Enter"].includes(e.key)) {
        return; // Обрабатываются внутри поповеров через document listeners
      }
      if (e.key === "Escape") {
        e.preventDefault();
        setSlashOpen(false);
        setMentionOpen(false);
        return;
      }
    }

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

  function handleSlashSelect(cmd: SlashCommand) {
    setSlashOpen(false);
    const result = expandSlashCommand(`/${cmd.key}`);
    if (!result) return;

    if ("isClientAction" in result && result.isClientAction === "clear") {
      setValue("");
      return;
    }

    if ("prompt" in result) {
      setValue(result.prompt);
      setTimeout(() => textareaRef.current?.focus(), 0);
    }
  }

  function handleMentionSelect(item: MetadataSuggestItem) {
    setMentionOpen(false);
    if (mentionStart === -1) return;

    const el = textareaRef.current;
    const cursor = el?.selectionStart ?? value.length;
    const before = value.slice(0, mentionStart);
    const after = value.slice(cursor);
    const newValue = `${before}@${item.full_path}${after}`;
    setValue(newValue);

    // Восстанавливаем позицию курсора после mention
    setTimeout(() => {
      const newCursor = mentionStart + 1 + item.full_path.length;
      el?.setSelectionRange(newCursor, newCursor);
      el?.focus();
    }, 0);
  }

  function handleQuickPromptSelect(prompt: string) {
    setValue(prompt);
    setTimeout(() => textareaRef.current?.focus(), 0);
  }


  return (
    <div className="flex flex-col gap-1 p-3">
      {/* Quick prompts: показываются только если textarea пустая */}
      <QuickPrompts
        onSelect={handleQuickPromptSelect}
        hidden={value.trim().length > 0}
      />

      {disabledReason === "banner" && (
        <p className="text-xs text-red-400 px-1">
          Нет соединения с базой. Восстановите подключение для отправки.
        </p>
      )}

      {/* Relative container для поповеров */}
      <div className="relative flex items-end gap-2" ref={anchorRef}>
        {/* Slash/Mention popover над textarea */}
        {slashOpen && (
          <SlashPopover
            open={slashOpen}
            query={slashQuery}
            onSelect={handleSlashSelect}
            anchor={anchorRef}
          />
        )}
        {mentionOpen && channelId && (
          <MentionPopover
            open={mentionOpen}
            query={mentionQuery}
            channelId={channelId}
            onSelect={handleMentionSelect}
            anchor={anchorRef}
          />
        )}

        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => handleChange(e.target.value)}
          onKeyDown={handleKeyDown}
          onInput={handleInput}
          placeholder="Спросите про базу 1С..."
          rows={1}
          readOnly={disabled}
          autoComplete="off"
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
