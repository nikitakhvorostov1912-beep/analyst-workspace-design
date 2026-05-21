"use client";

import { useCallback, useRef, useState, type KeyboardEvent } from "react";
import { Button } from "@/components/ui/button";
import { SlashPopover } from "@/components/chat/SlashPopover";
import { MentionPopover } from "@/components/chat/MentionPopover";
import { getLLMApiKey } from "@/lib/api-keys";
import { expandSlashCommand, type SlashCommand } from "@/lib/slash-commands";
import {
  FILE_ACCEPT_ATTR,
  MAX_FILES_PER_MESSAGE,
  approximateSize,
  filesToAttachments,
  isImageExtension,
  isImageMime,
} from "@/lib/attachments";
import { publishToast } from "@/lib/toast";
import type { ChatAttachment, MetadataSuggestItem } from "@/lib/types";
import { File as FileIcon, Paperclip, Send, Square, X } from "lucide-react";

interface ChatInputProps {
  onSubmit?: (message: string, attachments?: ChatAttachment[]) => void;
  disabled?: boolean;
  /** Если disabled по причине MCP disconnected — показать подсказку */
  disabledReason?: "banner" | "streaming" | null;
  /** Channel ID для metadata suggest (@-mentions) */
  channelId?: string;
  /** Sprint 2 (Hermes C9): true когда идёт стрим. Меняет кнопку Send → Stop. */
  isStreaming?: boolean;
  /** Sprint 2 (Hermes C9): прерывает текущий стрим. */
  onInterrupt?: () => void;
  /**
   * True, если backend получит ключ из env (DEFAULT_LLM_API_KEY). Тогда отправка
   * разрешена даже при пустом localStorage. Если false и ключа в браузере нет —
   * показываем toast «введите ключ» вместо отправки.
   */
  hasEnvApiKey?: boolean;
}

export function ChatInput({
  onSubmit,
  disabled,
  disabledReason,
  channelId,
  isStreaming = false,
  onInterrupt,
  hasEnvApiKey = false,
}: ChatInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Slash popover state
  const [slashOpen, setSlashOpen] = useState(false);
  const [slashQuery, setSlashQuery] = useState("");

  // Mention popover state
  const [mentionOpen, setMentionOpen] = useState(false);
  const [mentionQuery, setMentionQuery] = useState("");
  const [mentionStart, setMentionStart] = useState(-1);

  // Attachments state — прикреплённые файлы перед отправкой
  const [attachments, setAttachments] = useState<ChatAttachment[]>([]);
  const [isDragOver, setIsDragOver] = useState(false);
  const [loadingFiles, setLoadingFiles] = useState(false);

  const anchorRef = useRef<HTMLDivElement>(null);

  const handleFilesAdded = useCallback(
    async (files: File[]) => {
      if (files.length === 0) return;
      const remaining = MAX_FILES_PER_MESSAGE - attachments.length;
      if (remaining <= 0) {
        publishToast({
          type: "error",
          message: `Уже ${MAX_FILES_PER_MESSAGE} файлов — больше не помещается.`,
        });
        return;
      }
      setLoadingFiles(true);
      try {
        const { attachments: newAtt, errors } = await filesToAttachments(
          files.slice(0, remaining),
        );
        errors.forEach((e) => publishToast({ type: "error", message: e }));
        if (newAtt.length > 0) {
          setAttachments((prev) => [...prev, ...newAtt].slice(0, MAX_FILES_PER_MESSAGE));
        }
      } finally {
        setLoadingFiles(false);
      }
    },
    [attachments.length],
  );

  function handleSubmit() {
    if (disabled) return;
    const text = value.trim();
    // Разрешаем отправку с пустым text если есть файлы — модель сама поймёт
    if (!text && attachments.length === 0) return;

    // Проверяем наличие api_key. Если в localStorage пусто И backend не сообщил
    // о env-ключе (DEFAULT_LLM_API_KEY) — отправлять нечего, показываем toast.
    // Раньше тут был window.alert() — заменён на toast для нормального UX.
    const apiKey = getLLMApiKey();
    if (!apiKey && !hasEnvApiKey) {
      publishToast({
        type: "warning",
        message: "Введите API ключ в разделе Настройки или пропишите DEFAULT_LLM_API_KEY в backend/.env",
      });
      return;
    }

    const att = attachments;
    setValue("");
    setAttachments([]);
    setSlashOpen(false);
    setMentionOpen(false);
    if (textareaRef.current) {
      textareaRef.current.style.height = "56px";
    }
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }

    if (onSubmit) {
      // Если текст пустой — отправляем дефолтную фразу, чтобы LLM знал что делать
      const finalText = text || "Изучи прикреплённые файлы и сделай краткое резюме.";
      onSubmit(finalText, att.length > 0 ? att : undefined);
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

    // Enter без модификаторов → отправка (chat-app паттерн как у ChatGPT/Claude).
    // Shift+Enter → перенос строки. Ctrl/Cmd+Enter тоже отправляет (для пользователей
    // привыкших к старому поведению). До 2026-05-21 без модификаторов был newline,
    // что противоречило гайду «Enter (или Ctrl+Enter)».
    if (e.key === "Enter" && !e.shiftKey && !e.altKey && !e.nativeEvent.isComposing) {
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



  // Drag-and-drop handlers
  function handleDragOver(e: React.DragEvent) {
    if (disabled) return;
    e.preventDefault();
    if (e.dataTransfer.types.includes("Files") && !isDragOver) {
      setIsDragOver(true);
    }
  }

  function handleDragLeave(e: React.DragEvent) {
    e.preventDefault();
    // Игнорируем dragLeave от дочерних элементов — закрываем только когда покинули контейнер
    if (e.currentTarget === e.target) {
      setIsDragOver(false);
    }
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setIsDragOver(false);
    if (disabled) return;
    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) {
      void handleFilesAdded(files);
    }
  }

  function handleFilePickerChange(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? []);
    if (files.length > 0) {
      void handleFilesAdded(files);
    }
  }

  function handleRemoveAttachment(idx: number) {
    setAttachments((prev) => prev.filter((_, i) => i !== idx));
  }

  const hasValue = value.trim().length > 0 || attachments.length > 0;
  const canSubmit = hasValue && !disabled && !loadingFiles;
  // Грубая оценка токенов: 1 токен ≈ 4 символа. Для UI хватает.
  const tokenEstimate = Math.ceil(value.length / 4);

  return (
    <div
      className={`relative flex flex-col gap-1.5 p-3 ${isDragOver ? "ring-2 ring-[var(--accent)] ring-inset rounded-md bg-[var(--accent-08)]" : ""}`}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      {/* Brand-tick: оранжевая черта сверху-слева, brand-detail из лого-листа */}
      <span
        aria-hidden="true"
        className="pointer-events-none absolute top-0 left-6 h-[2px] w-[22px]"
        style={{ background: "var(--accent)" }}
      />
      {isDragOver && (
        <div
          className="pointer-events-none absolute inset-0 flex items-center justify-center text-sm text-[var(--accent)] font-medium z-10"
          data-testid="drag-overlay"
        >
          Отпустите файл — прикрепится к сообщению
        </div>
      )}

      {/* Прикреплённые файлы — чипы над textarea (с thumbnail для картинок) */}
      {attachments.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-1" data-testid="attachments-list">
          {attachments.map((att, i) => {
            const isImage = isImageMime(att.mime) || isImageExtension(att.name);
            return (
              <div
                key={i}
                className="inline-flex items-center gap-1.5 px-2 py-1 bg-[var(--bg-2)] border border-[var(--bd-2)] rounded text-xs"
                data-testid="attachment-chip"
                data-is-image={isImage ? "true" : "false"}
              >
                {isImage ? (
                  <img
                    src={`data:${att.mime || "image/png"};base64,${att.content_base64}`}
                    alt={att.name}
                    className="h-6 w-6 object-cover rounded border border-[var(--bd-2)]"
                  />
                ) : (
                  <FileIcon className="h-3 w-3 text-[var(--accent)]" />
                )}
                <span
                  className="font-medium text-[var(--fg-1)] max-w-[180px] truncate"
                  title={att.name}
                >
                  {att.name}
                </span>
                <span className="font-mono text-[10.5px] text-[var(--fg-3)]">
                  {approximateSize(att.content_base64)}
                </span>
                <button
                  type="button"
                  onClick={() => handleRemoveAttachment(i)}
                  className="p-0.5 hover:bg-[var(--bg-3)] rounded text-[var(--fg-3)] hover:text-[var(--fg-1)]"
                  aria-label={`Убрать ${att.name}`}
                >
                  <X className="h-3 w-3" />
                </button>
              </div>
            );
          })}
        </div>
      )}

      {disabledReason === "banner" && (
        <p className="text-xs text-[var(--error)] px-1">
          Нет соединения с базой. Восстановите подключение для отправки.
        </p>
      )}

      {/* Hidden file input для picker */}
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept={FILE_ACCEPT_ATTR}
        className="hidden"
        onChange={handleFilePickerChange}
        data-testid="file-input"
      />

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
          onPaste={(e) => {
            // Ctrl/Cmd+V — если в буфере есть картинка (скрин), прикрепляем её.
            // Текст вставится обычным образом, картинка попадает в attachments.
            const items = Array.from(e.clipboardData?.items ?? []);
            const imageFiles: File[] = [];
            for (const item of items) {
              if (item.kind === "file" && item.type.startsWith("image/")) {
                const f = item.getAsFile();
                if (f) imageFiles.push(f);
              }
            }
            if (imageFiles.length > 0) {
              e.preventDefault();
              void handleFilesAdded(imageFiles);
            }
          }}
          placeholder="Спросите про базу 1С или прикрепите документ / скрин..."
          rows={1}
          readOnly={disabled}
          autoComplete="off"
          className="flex-1 resize-none rounded-md border border-[var(--border)] bg-[var(--bg-elevated)] px-3 py-3 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)] transition-colors disabled:opacity-50"
          style={{ minHeight: "56px", maxHeight: "240px", height: "56px" }}
        />
        <Button
          variant="ghost"
          size="icon"
          onClick={() => fileInputRef.current?.click()}
          disabled={disabled || loadingFiles || attachments.length >= MAX_FILES_PER_MESSAGE}
          aria-label="Прикрепить файл"
          title={
            attachments.length >= MAX_FILES_PER_MESSAGE
              ? `Максимум ${MAX_FILES_PER_MESSAGE} файлов`
              : "Прикрепить файл (PDF / DOCX / XLSX / TXT / CSV)"
          }
          className="flex-none mb-0.5"
          data-testid="attach-button"
        >
          <Paperclip size={16} className={loadingFiles ? "animate-pulse" : ""} />
        </Button>
        {isStreaming && onInterrupt ? (
          <button
            type="button"
            onClick={onInterrupt}
            aria-label="Остановить"
            title="Остановить генерацию (частичный ответ сохранится)"
            className="flex-none mb-0.5 inline-flex items-center justify-center h-9 w-9 rounded-md border border-[var(--bd-2)] bg-[var(--bg-3)] text-[var(--fg-1)] hover:bg-[var(--bg-4)] transition-colors"
            data-testid="interrupt-button"
          >
            <Square size={13} fill="currentColor" />
          </button>
        ) : (
          <button
            type="button"
            onClick={handleSubmit}
            disabled={!canSubmit}
            aria-label="Отправить"
            className={`flex-none mb-0.5 inline-flex items-center justify-center h-9 w-9 rounded-md border transition-colors ${
              canSubmit
                ? "bg-[var(--accent)] border-[var(--accent)] text-[var(--brand-ink,#15161a)] hover:brightness-110"
                : "bg-[var(--bg-3)] border-[var(--bd-2)] text-[var(--fg-3)] cursor-not-allowed"
            }`}
            data-testid="send-button"
          >
            <Send size={15} />
          </button>
        )}
      </div>

      {/* Hint-row под composer: brand mono uppercase + token counter */}
      <div
        className="flex items-center gap-3 px-1 text-[10px] tracking-[0.14em] uppercase text-[var(--fg-4)]"
        style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
      >
        <span>
          {disabledReason === "banner"
            ? "Нет соединения — восстановите подключение"
            : "Естественный язык · модель сама выберет инструменты"}
        </span>
        <span className="ml-auto tabular-nums">
          {tokenEstimate.toLocaleString("ru-RU")} / 4 000 ТОКЕНОВ
        </span>
      </div>
    </div>
  );
}
