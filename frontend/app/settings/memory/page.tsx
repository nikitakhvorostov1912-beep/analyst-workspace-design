"use client";

import { ArrowLeft, Brain, AlertTriangle, CheckCircle2, Loader2 } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { fetchMemory, updateMemory } from "@/lib/api";
import { getActiveChannelId } from "@/lib/storage";
import type { MemoryDocument } from "@/lib/types";

/**
 * Постоянная память — редактор MEMORY.md / USER.md per channel.
 *
 * Sprint 1 (Hermes): эти файлы инжектятся в SYSTEM_PROMPT каждой сессии.
 * Аналитик может редактировать руками для контроля.
 */
export default function MemorySettingsPage() {
  const [channelId, setChannelId] = useState<string | null>(null);
  const [doc, setDoc] = useState<MemoryDocument | null>(null);
  const [agentDraft, setAgentDraft] = useState("");
  const [userDraft, setUserDraft] = useState("");
  const [savingNamespace, setSavingNamespace] = useState<"agent" | "user" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [savedFor, setSavedFor] = useState<"agent" | "user" | null>(null);

  // Hydrate channel id from storage on mount
  useEffect(() => {
    setChannelId(getActiveChannelId());
  }, []);

  const reload = useCallback(async (cid: string) => {
    try {
      const fresh = await fetchMemory(cid);
      setDoc(fresh);
      setAgentDraft(fresh.agent.content);
      setUserDraft(fresh.user.content);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось загрузить память");
    }
  }, []);

  useEffect(() => {
    if (channelId) void reload(channelId);
  }, [channelId, reload]);

  async function save(namespace: "agent" | "user") {
    if (!channelId) return;
    setSavingNamespace(namespace);
    setError(null);
    try {
      const content = namespace === "agent" ? agentDraft : userDraft;
      const result = await updateMemory(channelId, { namespace, content });
      // refetch чтобы получить актуальные chars и safety scan
      await reload(channelId);
      setSavedFor(namespace);
      setTimeout(() => setSavedFor(null), 2500);
      if (result.threats_found.length > 0) {
        setError(
          `Внимание: обнаружены подозрительные паттерны: ${result.threats_found.join(", ")}. Содержимое сохранено, но рекомендуем проверить.`,
        );
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка сохранения");
    } finally {
      setSavingNamespace(null);
    }
  }

  if (!channelId) {
    return (
      <div className="max-w-3xl mx-auto p-6">
        <Header />
        <div className="mt-8 rounded-md border border-[var(--bd-2)] bg-[var(--bg-1)] p-6 text-center text-[var(--fg-2)]">
          Не выбран канал. Откройте главный экран и выберите базу 1С.
        </div>
      </div>
    );
  }

  if (!doc) {
    return (
      <div className="max-w-3xl mx-auto p-6">
        <Header />
        <div className="mt-8 flex items-center gap-2 text-[var(--fg-3)]">
          <Loader2 className="h-4 w-4 animate-spin" />
          Загрузка...
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto p-6 pb-24">
      <Header />

      <div className="mt-6 mb-6 p-4 rounded-md border border-[var(--bd-2)] bg-[var(--bg-1)]">
        <div className="flex items-start gap-3">
          <Brain className="h-5 w-5 text-[var(--accent)] flex-shrink-0 mt-0.5" />
          <div className="text-[13.5px] text-[var(--fg-2)] leading-[1.6]">
            <p>
              Эти заметки сохраняются между сессиями и инжектятся в системный
              промпт ассистента при каждом запросе. Канал:{" "}
              <code
                className="px-1.5 py-0.5 rounded bg-[var(--bg-2)] text-[var(--fg-1)] text-[12px]"
                style={{ fontFamily: "var(--font-jb-mono), monospace" }}
              >
                {doc.channel_id}
              </code>
            </p>
            <p className="mt-2">
              <strong className="text-[var(--fg-1)]">MEMORY.md</strong> — что ассистент знает
              про вашу базу (конвенции, переименования, паттерны).{" "}
              <strong className="text-[var(--fg-1)]">USER.md</strong> — что он знает о вас
              (предпочтения, домен, стиль ответов).
            </p>
          </div>
        </div>
        {!doc.safe && (
          <div className="mt-3 flex items-start gap-2 text-[12.5px] text-[var(--warning)]">
            <AlertTriangle className="h-4 w-4 flex-shrink-0 mt-0.5" />
            <span>
              В содержимом обнаружены потенциально опасные паттерны (prompt injection).
              Проверьте текст перед использованием в production.
            </span>
          </div>
        )}
      </div>

      {error && (
        <div className="mb-4 p-3 rounded-md border border-[var(--error-40)] bg-[var(--error-12)] text-[13px] text-[var(--error)]">
          {error}
        </div>
      )}

      <Editor
        title="MEMORY.md — заметки агента"
        subtitle="Среда, конвенции базы, типовые паттерны решений"
        value={agentDraft}
        onChange={setAgentDraft}
        chars={agentDraft.length}
        maxChars={16_000}
        onSave={() => save("agent")}
        saving={savingNamespace === "agent"}
        saved={savedFor === "agent"}
        unchanged={agentDraft === doc.agent.content}
      />

      <Editor
        title="USER.md — что ассистент знает о вас"
        subtitle="Предпочтения, домен, стиль ответов, конкретные интересы"
        value={userDraft}
        onChange={setUserDraft}
        chars={userDraft.length}
        maxChars={8_000}
        onSave={() => save("user")}
        saving={savingNamespace === "user"}
        saved={savedFor === "user"}
        unchanged={userDraft === doc.user.content}
      />
    </div>
  );
}

function Header() {
  return (
    <div className="flex items-center gap-3">
      <Link
        href="/settings"
        className="text-[var(--fg-3)] hover:text-[var(--fg-1)] transition-colors flex items-center gap-1 text-sm"
      >
        <ArrowLeft size={16} />
        Настройки
      </Link>
      <h1
        className="text-lg font-semibold text-[var(--fg-1)]"
        style={{ fontFamily: "var(--font-plex-sans), system-ui" }}
      >
        Постоянная память
      </h1>
    </div>
  );
}

interface EditorProps {
  title: string;
  subtitle: string;
  value: string;
  onChange: (v: string) => void;
  chars: number;
  maxChars: number;
  onSave: () => void;
  saving: boolean;
  saved: boolean;
  unchanged: boolean;
}

function Editor({
  title,
  subtitle,
  value,
  onChange,
  chars,
  maxChars,
  onSave,
  saving,
  saved,
  unchanged,
}: EditorProps) {
  const pct = Math.min(100, Math.round((chars / maxChars) * 100));
  const colorClass =
    pct > 90 ? "text-[var(--error)]" : pct > 70 ? "text-[var(--warning)]" : "text-[var(--fg-3)]";

  return (
    <section className="mt-6">
      <div className="flex items-baseline justify-between mb-2">
        <div>
          <h2
            className="text-[15px] font-semibold text-[var(--fg-1)]"
            style={{ fontFamily: "var(--font-plex-sans), system-ui" }}
          >
            {title}
          </h2>
          <p className="text-[12px] text-[var(--fg-3)]">{subtitle}</p>
        </div>
        <span
          className={`text-[10.5px] tracking-[0.14em] uppercase tabular-nums ${colorClass}`}
          style={{ fontFamily: "var(--font-jb-mono), monospace" }}
        >
          {chars} / {maxChars} симв.
        </span>
      </div>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={10}
        className="w-full p-3 rounded-md bg-[var(--bg-2)] border border-[var(--bd-2)] text-[13px] text-[var(--fg-1)] font-mono leading-relaxed resize-y focus:outline-none focus:ring-2 focus:ring-[var(--accent-20)] focus:border-[var(--accent-32)]"
        style={{
          fontFamily: "var(--font-jb-mono), ui-monospace, monospace",
          minHeight: "180px",
          maxHeight: "480px",
        }}
        placeholder={"### Дата\n— Факт 1\n— Факт 2"}
        maxLength={maxChars}
        spellCheck={false}
      />
      <div className="mt-2 flex items-center gap-3">
        <button
          type="button"
          onClick={onSave}
          disabled={saving || unchanged}
          className="inline-flex items-center gap-2 px-4 h-9 rounded-md bg-[var(--accent)] text-[var(--brand-ink,#15161a)] text-[13px] font-semibold disabled:opacity-50 disabled:cursor-not-allowed hover:brightness-110 transition-all"
        >
          {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
          Сохранить
        </button>
        {saved && (
          <span className="inline-flex items-center gap-1 text-[12.5px] text-[var(--success)]">
            <CheckCircle2 className="h-3.5 w-3.5" />
            Сохранено
          </span>
        )}
        {unchanged && !saved && (
          <span className="text-[12px] text-[var(--fg-4)]">Нет изменений</span>
        )}
      </div>
    </section>
  );
}
