"use client";

import {
  ArrowLeft,
  Archive,
  Bot,
  CheckCircle2,
  Loader2,
  Pin,
  RotateCcw,
  Sparkles,
  Trash2,
  User,
} from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  archiveSkill,
  createSkill,
  deleteSkill,
  fetchSkills,
  runCurator,
  unarchiveSkill,
} from "@/lib/api";
import { getActiveChannelId } from "@/lib/storage";
import type { CuratorReport, SkillDTO } from "@/lib/types";

/**
 * Sprint 3 (Hermes A8/A9/A6): Skills + Curator UI.
 *
 * Скиллы — короткие markdown-инструкции которые накапливает агент через
 * background_review (provenance=agent) или редактирует пользователь (provenance=user).
 * Curator архивирует устаревшие agent-skill автоматически.
 */
export default function SkillsSettingsPage() {
  const [channelId, setChannelId] = useState<string | null>(null);
  const [active, setActive] = useState<SkillDTO[]>([]);
  const [archived, setArchived] = useState<SkillDTO[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [newBody, setNewBody] = useState("");
  const [newTags, setNewTags] = useState("");
  const [showArchive, setShowArchive] = useState(false);
  const [curatorReport, setCuratorReport] = useState<CuratorReport | null>(null);
  const [curatorRunning, setCuratorRunning] = useState(false);

  useEffect(() => {
    setChannelId(getActiveChannelId());
  }, []);

  const reload = useCallback(async (cid: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchSkills(cid);
      setActive(data.active);
      setArchived(data.archived);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось загрузить skills");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (channelId) void reload(channelId);
  }, [channelId, reload]);

  async function handleCreate() {
    if (!channelId || !newBody.trim()) return;
    setCreating(true);
    setError(null);
    try {
      const tags = newTags
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean);
      await createSkill(channelId, { body: newBody, tags });
      setNewBody("");
      setNewTags("");
      await reload(channelId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка создания");
    } finally {
      setCreating(false);
    }
  }

  async function handleArchive(skillId: string) {
    if (!channelId) return;
    try {
      await archiveSkill(channelId, skillId);
      await reload(channelId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка архивации");
    }
  }

  async function handleUnarchive(skillId: string) {
    if (!channelId) return;
    try {
      await unarchiveSkill(channelId, skillId);
      await reload(channelId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка восстановления");
    }
  }

  async function handleDelete(skillId: string) {
    if (!channelId) return;
    if (!confirm(`Удалить skill ${skillId}? Это действие необратимо.`)) return;
    try {
      await deleteSkill(channelId, skillId);
      await reload(channelId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка удаления");
    }
  }

  async function handleRunCurator(dryRun: boolean) {
    if (!channelId) return;
    setCuratorRunning(true);
    setError(null);
    try {
      const report = await runCurator(channelId, dryRun);
      setCuratorReport(report);
      if (!dryRun) await reload(channelId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка запуска Curator");
    } finally {
      setCuratorRunning(false);
    }
  }

  if (!channelId) {
    return (
      <div className="max-w-4xl mx-auto p-6">
        <Header />
        <div className="mt-8 rounded-md border border-[var(--bd-2)] bg-[var(--bg-1)] p-6 text-center text-[var(--fg-2)]">
          Не выбран канал. Откройте главный экран и выберите базу 1С.
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto p-6 pb-24">
      <Header />

      <div className="mt-6 mb-6 p-4 rounded-md border border-[var(--bd-2)] bg-[var(--bg-1)]">
        <div className="flex items-start gap-3">
          <Sparkles className="h-5 w-5 text-[var(--accent)] flex-shrink-0 mt-0.5" />
          <div className="text-[13.5px] text-[var(--fg-2)] leading-[1.6]">
            <p>
              Skills — короткие инструкции «когда X — делай Y». Агент сам сохраняет
              их через background review (provenance{" "}
              <code className="px-1 py-0.5 rounded bg-[var(--bg-2)] text-[12px]">
                agent
              </code>
              ), вы можете добавлять вручную (
              <code className="px-1 py-0.5 rounded bg-[var(--bg-2)] text-[12px]">
                user
              </code>
              ). Curator архивирует устаревшие agent-skills.
            </p>
          </div>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 rounded-md border border-[var(--error-40)] bg-[var(--error-12)] text-[13px] text-[var(--error)]">
          {error}
        </div>
      )}

      {/* Create form */}
      <section className="mb-8 p-4 rounded-md border border-[var(--bd-2)] bg-[var(--bg-1)]">
        <h2 className="text-[15px] font-semibold text-[var(--fg-1)] mb-3">
          Добавить skill
        </h2>
        <textarea
          value={newBody}
          onChange={(e) => setNewBody(e.target.value)}
          rows={4}
          placeholder="Описание паттерна... Например: 'Когда юзер просит остатки ТМЦ — execute_query с виртуальной таблицей Регистр.Остатки.'"
          className="w-full p-3 rounded-md bg-[var(--bg-2)] border border-[var(--bd-2)] text-[13px] text-[var(--fg-1)] font-mono leading-relaxed resize-y focus:outline-none focus:ring-2 focus:ring-[var(--accent-20)]"
          style={{ fontFamily: "var(--font-jb-mono), monospace", minHeight: "120px" }}
          maxLength={8000}
        />
        <div className="mt-2 flex items-center gap-3">
          <input
            type="text"
            value={newTags}
            onChange={(e) => setNewTags(e.target.value)}
            placeholder="теги через запятую (query, opp, регистры)"
            className="flex-1 px-3 h-9 rounded-md bg-[var(--bg-2)] border border-[var(--bd-2)] text-[13px] text-[var(--fg-1)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-20)]"
          />
          <button
            type="button"
            onClick={handleCreate}
            disabled={creating || !newBody.trim()}
            className="inline-flex items-center gap-2 px-4 h-9 rounded-md bg-[var(--accent)] text-[var(--brand-ink,#15161a)] text-[13px] font-semibold disabled:opacity-50 disabled:cursor-not-allowed hover:brightness-110 transition-all"
          >
            {creating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
            Добавить
          </button>
        </div>
      </section>

      {/* Curator block */}
      <section className="mb-8 p-4 rounded-md border border-[var(--bd-2)] bg-[var(--bg-1)]">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-[15px] font-semibold text-[var(--fg-1)]">Curator</h2>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => handleRunCurator(true)}
              disabled={curatorRunning}
              className="px-3 h-8 rounded-md border border-[var(--bd-2)] bg-[var(--bg-2)] text-[12px] text-[var(--fg-2)] hover:bg-[var(--bg-3)] transition-colors disabled:opacity-50"
            >
              Dry run
            </button>
            <button
              type="button"
              onClick={() => handleRunCurator(false)}
              disabled={curatorRunning}
              className="px-3 h-8 rounded-md border border-[var(--accent-32)] bg-[var(--accent-12)] text-[12px] text-[var(--accent)] hover:bg-[var(--accent-20)] transition-colors disabled:opacity-50"
            >
              {curatorRunning ? "Запускаю..." : "Запустить"}
            </button>
          </div>
        </div>
        {curatorReport && (
          <div
            className="text-[12.5px] text-[var(--fg-2)] leading-[1.7] font-mono"
            style={{ fontFamily: "var(--font-jb-mono), monospace" }}
          >
            проверено: {curatorReport.inspected} · архивировано:{" "}
            {curatorReport.archived.length} · pinned пропущено:{" "}
            {curatorReport.skipped_pinned.length} · user пропущено:{" "}
            {curatorReport.skipped_user.length} · свежие пропущены:{" "}
            {curatorReport.skipped_recent.length}
            {curatorReport.backup_label && (
              <div className="mt-1 text-[var(--fg-3)]">
                backup: {curatorReport.backup_label}
              </div>
            )}
          </div>
        )}
      </section>

      {/* Active skills */}
      <section className="mb-6">
        <h2 className="text-[15px] font-semibold text-[var(--fg-1)] mb-3">
          Активные ({active.length})
        </h2>
        {loading && active.length === 0 ? (
          <div className="flex items-center gap-2 text-[var(--fg-3)]">
            <Loader2 className="h-4 w-4 animate-spin" />
            Загрузка...
          </div>
        ) : active.length === 0 ? (
          <div className="p-6 rounded-md border border-[var(--bd-2)] bg-[var(--bg-1)] text-center text-[var(--fg-3)] text-[13px]">
            Пока нет skills. Поговорите с агентом — он сам начнёт сохранять
            полезные паттерны.
          </div>
        ) : (
          <div className="space-y-3">
            {active.map((skill) => (
              <SkillCard
                key={skill.id}
                skill={skill}
                onArchive={() => handleArchive(skill.id)}
                onDelete={() => handleDelete(skill.id)}
              />
            ))}
          </div>
        )}
      </section>

      {/* Archived block toggle */}
      <section>
        <button
          type="button"
          onClick={() => setShowArchive((v) => !v)}
          className="text-[13px] text-[var(--fg-3)] hover:text-[var(--fg-1)] transition-colors"
        >
          {showArchive ? "Скрыть" : "Показать"} архив ({archived.length})
        </button>
        {showArchive && archived.length > 0 && (
          <div className="mt-3 space-y-3">
            {archived.map((skill) => (
              <SkillCard
                key={skill.id}
                skill={skill}
                onUnarchive={() => handleUnarchive(skill.id)}
                onDelete={() => handleDelete(skill.id)}
              />
            ))}
          </div>
        )}
      </section>
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
        Skills
      </h1>
    </div>
  );
}

interface SkillCardProps {
  skill: SkillDTO;
  onArchive?: () => void;
  onUnarchive?: () => void;
  onDelete?: () => void;
}

function SkillCard({ skill, onArchive, onUnarchive, onDelete }: SkillCardProps) {
  const ProvenanceIcon = skill.provenance === "agent" ? Bot : User;
  return (
    <div
      className={`p-4 rounded-md border ${
        skill.archived
          ? "border-[var(--bd-2)] bg-[var(--bg-1)] opacity-70"
          : "border-[var(--bd-2)] bg-[var(--bg-1)]"
      }`}
    >
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex items-center gap-2 min-w-0">
          {skill.pinned && (
            <Pin className="h-3.5 w-3.5 text-[var(--accent)] flex-shrink-0" />
          )}
          <code
            className="text-[12.5px] text-[var(--fg-1)] truncate"
            style={{ fontFamily: "var(--font-jb-mono), monospace" }}
          >
            {skill.id}
          </code>
          <ProvenanceIcon className="h-3 w-3 text-[var(--fg-3)] flex-shrink-0" />
          <span className="text-[10.5px] uppercase tracking-[0.14em] text-[var(--fg-4)]">
            {skill.provenance}
          </span>
        </div>
        <div className="flex items-center gap-1">
          {onArchive && (
            <button
              type="button"
              onClick={onArchive}
              title="Архивировать"
              className="p-1 rounded text-[var(--fg-3)] hover:text-[var(--fg-1)] hover:bg-[var(--bg-2)] transition-colors"
            >
              <Archive size={14} />
            </button>
          )}
          {onUnarchive && (
            <button
              type="button"
              onClick={onUnarchive}
              title="Восстановить"
              className="p-1 rounded text-[var(--fg-3)] hover:text-[var(--fg-1)] hover:bg-[var(--bg-2)] transition-colors"
            >
              <RotateCcw size={14} />
            </button>
          )}
          {onDelete && !skill.pinned && (
            <button
              type="button"
              onClick={onDelete}
              title="Удалить"
              className="p-1 rounded text-[var(--fg-3)] hover:text-[var(--error)] hover:bg-[var(--bg-2)] transition-colors"
            >
              <Trash2 size={14} />
            </button>
          )}
        </div>
      </div>
      {skill.tags.length > 0 && (
        <div className="mb-2 flex flex-wrap gap-1">
          {skill.tags.map((tag) => (
            <span
              key={tag}
              className="px-1.5 py-0.5 rounded text-[10.5px] bg-[var(--bg-2)] text-[var(--fg-2)] tracking-wide"
            >
              {tag}
            </span>
          ))}
        </div>
      )}
      <div
        className="text-[13px] text-[var(--fg-2)] leading-[1.55] whitespace-pre-wrap"
        style={{ fontFamily: "var(--font-jb-mono), monospace" }}
      >
        {skill.body.length > 600 ? skill.body.slice(0, 600) + "…" : skill.body}
      </div>
      <div className="mt-2 flex items-center gap-3 text-[11px] text-[var(--fg-4)] tabular-nums">
        <span>chars: {skill.chars}</span>
        <span>·</span>
        <span>used: {skill.usage_count}</span>
        {skill.usage_count > 0 && skill.last_used_iso && (
          <>
            <span>·</span>
            <span>last: {new Date(skill.last_used_iso).toLocaleString("ru-RU")}</span>
          </>
        )}
        {skill.usage_count > 0 && (
          <CheckCircle2 className="h-3 w-3 text-[var(--success)] ml-auto" />
        )}
      </div>
    </div>
  );
}
