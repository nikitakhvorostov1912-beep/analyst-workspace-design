"use client";

import {
  ArrowLeft,
  Archive,
  Bot,
  CheckCircle2,
  Clock,
  Loader2,
  Pin,
  RotateCcw,
  Sparkles,
  Trash2,
  TrendingUp,
  User,
} from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  archiveSkill,
  createSkill,
  deleteSkill,
  fetchSkills,
  runCurator,
  unarchiveSkill,
} from "@/lib/api";
import { getActiveChannelId } from "@/lib/storage";
import { ThemeToggle } from "@/components/shell/ThemeToggle";
import type { CuratorReport, SkillDTO } from "@/lib/types";

/**
 * Группа навыков по дате создания: сегодня / неделя / месяц / раньше.
 * Возвращает 4 списка плюс краткую сводку для каждой группы.
 */
function groupSkillsByPeriod(skills: SkillDTO[]): {
  today: SkillDTO[];
  week: SkillDTO[];
  month: SkillDTO[];
  older: SkillDTO[];
} {
  const now = Date.now();
  const day = 24 * 60 * 60 * 1000;
  const today: SkillDTO[] = [];
  const week: SkillDTO[] = [];
  const month: SkillDTO[] = [];
  const older: SkillDTO[] = [];
  for (const skill of skills) {
    const created = new Date(skill.created_at).getTime();
    if (Number.isNaN(created)) {
      older.push(skill);
      continue;
    }
    const ageDays = (now - created) / day;
    if (ageDays < 1) today.push(skill);
    else if (ageDays < 7) week.push(skill);
    else if (ageDays < 30) month.push(skill);
    else older.push(skill);
  }
  return { today, week, month, older };
}

/**
 * Период активности — от самого старого до самого нового активного навыка.
 * Формат: «12 дней» / «3 месяца» / «—» если skills пуст.
 */
function formatTrainingPeriod(skills: SkillDTO[]): string {
  if (skills.length === 0) return "—";
  const dates = skills
    .map((s) => new Date(s.created_at).getTime())
    .filter((t) => !Number.isNaN(t));
  if (dates.length === 0) return "—";
  const oldest = Math.min(...dates);
  const newest = Math.max(...dates);
  const days = Math.max(1, Math.round((newest - oldest) / (24 * 60 * 60 * 1000)));
  if (days < 1) return "сегодня";
  if (days === 1) return "1 день";
  if (days < 30) return `${days} дн.`;
  const months = Math.round(days / 30);
  if (months === 1) return "1 месяц";
  if (months < 12) return `${months} мес.`;
  const years = Math.round(months / 12);
  return years === 1 ? "1 год" : `${years} лет`;
}

function formatRelativeDate(iso: string): string {
  const ts = new Date(iso).getTime();
  if (Number.isNaN(ts)) return iso;
  const now = Date.now();
  const diffMs = now - ts;
  const diffMin = Math.round(diffMs / 60_000);
  const diffH = Math.round(diffMs / 3_600_000);
  const diffD = Math.round(diffMs / 86_400_000);
  if (diffMin < 1) return "только что";
  if (diffMin < 60) return `${diffMin} мин назад`;
  if (diffH < 24) return `${diffH} ч назад`;
  if (diffD < 7) return `${diffD} дн назад`;
  return new Date(iso).toLocaleDateString("ru-RU");
}

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
    if (!confirm(`Удалить подсказку ${skillId}? Это действие необратимо.`)) return;
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
          Не выбрана база 1С. Откройте главный экран и выберите подключение.
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
              Подсказки — короткие инструкции «когда X — делай Y». Ассистент
              сам накапливает их по ходу диалогов; вы тоже можете добавлять
              вручную. Автоочистка (она же «Чистильщик» ниже) удаляет устаревшие
              подсказки, чтобы они не сбивали модель.
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
          Добавить подсказку
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
            className="inline-flex items-center gap-2 px-4 h-9 rounded-md bg-[var(--accent)] text-[var(--brand-ink,#15161a)] text-[13px] font-semibold disabled:opacity-50 disabled:cursor-not-allowed hover:brightness-110 transition-[filter,transform] duration-150 ease-out active:scale-[0.97]"
          >
            {creating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
            Добавить
          </button>
        </div>
      </section>

      {/* Curator block */}
      <section className="mb-8 p-4 rounded-md border border-[var(--bd-2)] bg-[var(--bg-1)]">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-[15px] font-semibold text-[var(--fg-1)]">
            Автоочистка устаревших
          </h2>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => handleRunCurator(true)}
              disabled={curatorRunning}
              className="px-3 h-8 rounded-md border border-[var(--bd-2)] bg-[var(--bg-2)] text-[12px] text-[var(--fg-2)] hover:bg-[var(--bg-3)] transition-colors disabled:opacity-50"
              title="Показать что будет удалено, но ничего не менять"
            >
              Только посмотреть
            </button>
            <button
              type="button"
              onClick={() => handleRunCurator(false)}
              disabled={curatorRunning}
              className="px-3 h-8 rounded-md border border-[var(--accent-32)] bg-[var(--accent-12)] text-[12px] text-[var(--accent)] hover:bg-[var(--accent-20)] transition-colors disabled:opacity-50"
            >
              {curatorRunning ? "Чистим..." : "Очистить"}
            </button>
          </div>
        </div>
        {curatorReport && (
          <div
            className="text-[12.5px] text-[var(--fg-2)] leading-[1.7] font-mono"
            style={{ fontFamily: "var(--font-jb-mono), monospace" }}
          >
            проверено: {curatorReport.inspected} · убрано в архив:{" "}
            {curatorReport.archived.length} · закреплённые оставлены:{" "}
            {curatorReport.skipped_pinned.length} · ваши оставлены:{" "}
            {curatorReport.skipped_user.length} · свежие оставлены:{" "}
            {curatorReport.skipped_recent.length}
            {curatorReport.backup_label && (
              <div className="mt-1 text-[var(--fg-3)]">
                резервная копия: {curatorReport.backup_label}
              </div>
            )}
          </div>
        )}
      </section>

      {/* Training summary — что система выучила и за какой период */}
      <TrainingSummary active={active} archived={archived} loading={loading} />

      {/* Active skills grouped by period */}
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
            Пока нет подсказок. Поговорите с ассистентом — он сам начнёт
            сохранять полезные шаблоны решений.
          </div>
        ) : (
          <GroupedSkills
            active={active}
            onArchive={handleArchive}
            onDelete={handleDelete}
          />
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
        Подсказки агента
      </h1>
      <div className="ml-auto">
        <ThemeToggle />
      </div>
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
      <div className="mt-2 flex items-center gap-3 text-[11px] text-[var(--fg-4)] tabular-nums flex-wrap">
        <span title={new Date(skill.created_at).toLocaleString("ru-RU")}>
          выучен: {formatRelativeDate(skill.created_at)}
        </span>
        <span>·</span>
        <span>применён: {skill.usage_count} раз</span>
        {skill.usage_count > 0 && skill.last_used_iso && (
          <>
            <span>·</span>
            <span title={new Date(skill.last_used_iso).toLocaleString("ru-RU")}>
              последний: {formatRelativeDate(skill.last_used_iso)}
            </span>
          </>
        )}
        <span>·</span>
        <span>{skill.chars} симв.</span>
        {skill.usage_count > 0 && (
          <CheckCircle2 className="h-3 w-3 text-[var(--success)] ml-auto" />
        )}
      </div>
    </div>
  );
}

/**
 * Сводный блок «Что система выучила» — показывает общую статистику обучения:
 * сколько навыков, за какой период, как разделены по источнику и активности.
 */
function TrainingSummary({
  active,
  archived,
  loading,
}: {
  active: SkillDTO[];
  archived: SkillDTO[];
  loading: boolean;
}) {
  const stats = useMemo(() => {
    const all = [...active, ...archived];
    const agentSkills = active.filter((s) => s.provenance === "agent");
    const userSkills = active.filter((s) => s.provenance === "user");
    const usedSkills = active.filter((s) => s.usage_count > 0);
    const totalUsages = active.reduce((sum, s) => sum + s.usage_count, 0);
    const topUsed = [...active]
      .filter((s) => s.usage_count > 0)
      .sort((a, b) => b.usage_count - a.usage_count)
      .slice(0, 3);

    // Самый свежий навык (для UX «когда последний раз чему-то научилась»)
    const newest = active.reduce<SkillDTO | null>((acc, s) => {
      if (!acc) return s;
      return new Date(s.created_at) > new Date(acc.created_at) ? s : acc;
    }, null);

    return {
      total: all.length,
      activeCount: active.length,
      archivedCount: archived.length,
      agentCount: agentSkills.length,
      userCount: userSkills.length,
      usedCount: usedSkills.length,
      totalUsages,
      topUsed,
      trainingPeriod: formatTrainingPeriod(active),
      newest,
    };
  }, [active, archived]);

  if (loading && active.length === 0 && archived.length === 0) {
    return null;
  }

  if (stats.total === 0) {
    return (
      <section className="mb-6 p-4 rounded-md border border-[var(--bd-2)] bg-[var(--bg-1)]">
        <h2 className="text-[14px] font-semibold text-[var(--fg-1)] mb-2 flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-[var(--accent)]" />
          Что система выучила
        </h2>
        <p className="text-[13px] text-[var(--fg-3)]">
          Ассистент пока ничему не научился — поговорите с ним. После каждого
          ответа фоновая задача анализирует диалог и сохраняет полезные шаблоны.
        </p>
      </section>
    );
  }

  return (
    <section className="mb-6 p-4 rounded-md border border-[var(--bd-2)] bg-[var(--bg-1)]">
      <h2 className="text-[14px] font-semibold text-[var(--fg-1)] mb-3 flex items-center gap-2">
        <Sparkles className="h-4 w-4 text-[var(--accent)]" />
        Что система выучила
      </h2>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
        <Metric
          label="Навыков активно"
          value={stats.activeCount}
          sub={stats.archivedCount > 0 ? `+${stats.archivedCount} в архиве` : ""}
        />
        <Metric
          label="Период обучения"
          value={stats.trainingPeriod}
          sub={
            stats.newest
              ? `последний: ${formatRelativeDate(stats.newest.created_at)}`
              : ""
          }
          icon={<Clock className="h-3 w-3" />}
        />
        <Metric
          label="От агента / от вас"
          value={`${stats.agentCount} / ${stats.userCount}`}
          sub={`автоматически / вручную`}
        />
        <Metric
          label="Применений всего"
          value={stats.totalUsages}
          sub={
            stats.usedCount > 0
              ? `${stats.usedCount} из ${stats.activeCount} в работе`
              : "пока не применялись"
          }
          icon={<TrendingUp className="h-3 w-3" />}
        />
      </div>

      {stats.topUsed.length > 0 && (
        <div className="pt-3 border-t border-[var(--bd-2)]">
          <div className="text-[11px] uppercase tracking-[0.12em] text-[var(--fg-4)] mb-2">
            Топ применяемые
          </div>
          <div className="space-y-1.5">
            {stats.topUsed.map((skill) => (
              <div
                key={skill.id}
                className="flex items-baseline gap-2 text-[12.5px]"
              >
                <span
                  className="font-mono text-[var(--fg-2)] tabular-nums w-12"
                  style={{ fontFamily: "var(--font-jb-mono), monospace" }}
                >
                  ×{skill.usage_count}
                </span>
                <code
                  className="text-[var(--fg-1)] truncate flex-1"
                  style={{ fontFamily: "var(--font-jb-mono), monospace" }}
                  title={skill.body.slice(0, 200)}
                >
                  {skill.id}
                </code>
                {skill.tags.length > 0 && (
                  <span className="text-[10.5px] text-[var(--fg-4)] uppercase tracking-wide">
                    {skill.tags.slice(0, 2).join(" · ")}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

function Metric({
  label,
  value,
  sub,
  icon,
}: {
  label: string;
  value: string | number;
  sub?: string;
  icon?: React.ReactNode;
}) {
  return (
    <div className="rounded-md bg-[var(--bg-2)] p-2.5 border border-[var(--bd-2)]">
      <div className="text-[10.5px] uppercase tracking-[0.12em] text-[var(--fg-4)] mb-1 flex items-center gap-1">
        {icon}
        {label}
      </div>
      <div
        className="text-[18px] font-semibold text-[var(--fg-1)] tabular-nums leading-tight"
        style={{ fontFamily: "var(--font-plex-sans), system-ui" }}
      >
        {value}
      </div>
      {sub && (
        <div className="text-[10.5px] text-[var(--fg-3)] mt-0.5">{sub}</div>
      )}
    </div>
  );
}

/**
 * Группирует активные навыки по дате создания и рендерит секции.
 */
function GroupedSkills({
  active,
  onArchive,
  onDelete,
}: {
  active: SkillDTO[];
  onArchive: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  const groups = useMemo(() => groupSkillsByPeriod(active), [active]);

  // Если все в одной группе (типично для свежей установки) — без подзаголовков
  const groupCount = [
    groups.today.length,
    groups.week.length,
    groups.month.length,
    groups.older.length,
  ].filter((n) => n > 0).length;

  if (groupCount <= 1) {
    return (
      <div className="space-y-3">
        {active.map((skill) => (
          <SkillCard
            key={skill.id}
            skill={skill}
            onArchive={() => onArchive(skill.id)}
            onDelete={() => onDelete(skill.id)}
          />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <PeriodGroup
        title="Сегодня"
        skills={groups.today}
        onArchive={onArchive}
        onDelete={onDelete}
      />
      <PeriodGroup
        title="За неделю"
        skills={groups.week}
        onArchive={onArchive}
        onDelete={onDelete}
      />
      <PeriodGroup
        title="За месяц"
        skills={groups.month}
        onArchive={onArchive}
        onDelete={onDelete}
      />
      <PeriodGroup
        title="Раньше"
        skills={groups.older}
        onArchive={onArchive}
        onDelete={onDelete}
      />
    </div>
  );
}

function PeriodGroup({
  title,
  skills,
  onArchive,
  onDelete,
}: {
  title: string;
  skills: SkillDTO[];
  onArchive: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  if (skills.length === 0) return null;
  return (
    <div>
      <div className="text-[11px] uppercase tracking-[0.14em] text-[var(--fg-4)] mb-2 px-1">
        {title} · {skills.length}
      </div>
      <div className="space-y-2.5">
        {skills.map((skill) => (
          <SkillCard
            key={skill.id}
            skill={skill}
            onArchive={() => onArchive(skill.id)}
            onDelete={() => onDelete(skill.id)}
          />
        ))}
      </div>
    </div>
  );
}
