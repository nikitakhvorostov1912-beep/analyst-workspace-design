/**
 * Экспорт сессии в markdown для передачи аналитику/в Claude для диагностики.
 *
 * Включает ВСЁ: текст сообщений, tool_calls с аргументами/результатами,
 * cards (тип + сводка), reasoning_content в спойлере, длительности.
 * Pure-функция — никаких side-эффектов.
 */
import type { CardEnvelope, ChatMessage, SessionDetail, ToolCallRecord } from "./types";

/** Максимальная длина превью результата tool_call в markdown (символов). */
const TOOL_RESULT_PREVIEW_CAP = 1500;
/** Максимальная длина превью cards.payload в markdown. */
const CARD_PAYLOAD_PREVIEW_CAP = 1200;

interface ExportableMessage {
  id?: string;
  role: "user" | "assistant" | "tool";
  content: string | null;
  tool_calls?: ToolCallRecord[] | null;
  cards?: CardEnvelope[] | null;
  duration_ms?: number | null;
  created_at?: string;
  /** MiMo thinking — может присутствовать в БД-row, в ChatMessage его нет. */
  reasoning_content?: string | null;
}

/**
 * Возвращает markdown-документ сессии.
 *
 * @param detail   метаданные сессии (title, channel_id, created_at)
 * @param messages список сообщений в хронологическом порядке
 */
export function sessionToMarkdown(
  detail: SessionDetail | null,
  messages: readonly (ChatMessage | ExportableMessage)[],
): string {
  const lines: string[] = [];

  // --- Header ---
  const title = detail?.title?.trim() || "Без названия";
  lines.push(`# Сессия: ${title}`);
  lines.push("");
  const meta: string[] = [];
  if (detail?.id) meta.push(`id: \`${detail.id}\``);
  if (detail?.channel_id) meta.push(`канал: \`${detail.channel_id}\``);
  if (detail?.created_at) meta.push(`создана: ${formatDate(detail.created_at)}`);
  meta.push(`сообщений: ${messages.length}`);
  if (meta.length) {
    lines.push(meta.join(" · "));
    lines.push("");
  }
  lines.push("---");
  lines.push("");

  // --- Messages ---
  for (let i = 0; i < messages.length; i++) {
    const msg = messages[i] as ExportableMessage;
    const heading = roleHeading(msg.role);
    const ts = msg.created_at ? ` _(${formatDate(msg.created_at)})_` : "";
    const dur = msg.duration_ms ? ` _· ${msg.duration_ms} мс_` : "";
    lines.push(`## ${heading}${ts}${dur}`);
    lines.push("");

    // Тело сообщения
    const content = (msg.content ?? "").trim();
    if (content) {
      lines.push(content);
      lines.push("");
    } else if (msg.role !== "tool") {
      lines.push("_(пустое сообщение)_");
      lines.push("");
    }

    // Reasoning (MiMo thinking) — в details-спойлере чтобы не загромождать
    if (msg.reasoning_content && msg.reasoning_content.trim()) {
      lines.push("<details><summary>🧠 reasoning (thinking)</summary>");
      lines.push("");
      lines.push("```");
      lines.push(msg.reasoning_content.trim());
      lines.push("```");
      lines.push("");
      lines.push("</details>");
      lines.push("");
    }

    // Tool calls — самое важное для диагностики
    const toolCalls = (msg.tool_calls ?? []) as ToolCallRecord[];
    if (toolCalls.length > 0) {
      lines.push(`**Вызвано инструментов: ${toolCalls.length}**`);
      lines.push("");
      for (const tc of toolCalls) {
        lines.push(...formatToolCall(tc));
      }
    }

    // Cards
    const cards = (msg.cards ?? []) as CardEnvelope[];
    if (cards.length > 0) {
      lines.push(`**Карточки: ${cards.length}**`);
      lines.push("");
      for (const card of cards) {
        lines.push(...formatCard(card));
      }
    }

    lines.push("---");
    lines.push("");
  }

  // Хвост — версия / источник
  lines.push("");
  lines.push(`_Экспорт из «1С Аналитик» · ${formatDate(new Date().toISOString())}_`);

  return lines.join("\n");
}

function roleHeading(role: "user" | "assistant" | "tool"): string {
  switch (role) {
    case "user":
      return "🟢 Вы";
    case "assistant":
      return "🤖 Ассистент";
    case "tool":
      return "🔧 Результат инструмента";
  }
}

function formatToolCall(tc: ToolCallRecord): string[] {
  const out: string[] = [];
  const status = tc.ok === true ? "✓" : tc.ok === false ? "✗" : "·";
  const dur = tc.duration_ms !== undefined ? ` · ${tc.duration_ms} мс` : "";
  out.push(`- ${status} \`${tc.name}\`${dur}`);

  // Аргументы — компактный JSON
  if (tc.args && Object.keys(tc.args).length > 0) {
    out.push("");
    out.push("  Аргументы:");
    out.push("");
    out.push("  ```json");
    const argsJson = safeStringify(tc.args, 2);
    for (const ln of argsJson.split("\n")) out.push("  " + ln);
    out.push("  ```");
  }

  // Результат — может быть object/string/null. Превью с cap.
  if (tc.result !== undefined && tc.result !== null) {
    out.push("");
    out.push("  Результат:");
    out.push("");
    out.push("  ```");
    const resStr = typeof tc.result === "string" ? tc.result : safeStringify(tc.result, 2);
    const capped =
      resStr.length > TOOL_RESULT_PREVIEW_CAP
        ? resStr.slice(0, TOOL_RESULT_PREVIEW_CAP) +
          `\n…(обрезано, всего ${resStr.length} символов)`
        : resStr;
    for (const ln of capped.split("\n")) out.push("  " + ln);
    out.push("  ```");
  }

  if (tc.error) {
    out.push("");
    out.push(`  **Ошибка:** ${tc.error}`);
  }
  out.push("");
  return out;
}

function formatCard(card: CardEnvelope): string[] {
  const out: string[] = [];
  out.push(`- 🃏 \`${card.type}\``);
  out.push("");
  out.push("  ```json");
  const json = safeStringify(card.payload, 2);
  const capped =
    json.length > CARD_PAYLOAD_PREVIEW_CAP
      ? json.slice(0, CARD_PAYLOAD_PREVIEW_CAP) +
        `\n…(обрезано, всего ${json.length} символов)`
      : json;
  for (const ln of capped.split("\n")) out.push("  " + ln);
  out.push("  ```");
  out.push("");
  return out;
}

function safeStringify(v: unknown, indent: number): string {
  try {
    return JSON.stringify(v, null, indent);
  } catch {
    return String(v);
  }
}

function formatDate(iso: string): string {
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleString("ru-RU");
  } catch {
    return iso;
  }
}

/**
 * Возвращает безопасное имя файла для сохранения экспорта.
 *   "Анализ выручки и контрагенты" → "session-analiz-vyruchki-i-kontragenty.md"
 *   null/пусто                      → "session-<id-prefix>.md"
 */
export function sessionExportFilename(detail: SessionDetail | null): string {
  const titleRaw = detail?.title?.trim() ?? "";
  const slug = titleRaw
    ? slugify(titleRaw).slice(0, 60) || "untitled"
    : detail?.id
      ? detail.id.slice(0, 8)
      : "untitled";
  return `session-${slug}.md`;
}

function slugify(s: string): string {
  // Простой транслит для распространённых русских букв + удаление спецсимволов.
  const map: Record<string, string> = {
    а: "a", б: "b", в: "v", г: "g", д: "d", е: "e", ё: "yo", ж: "zh",
    з: "z", и: "i", й: "y", к: "k", л: "l", м: "m", н: "n", о: "o",
    п: "p", р: "r", с: "s", т: "t", у: "u", ф: "f", х: "h", ц: "c",
    ч: "ch", ш: "sh", щ: "sch", ъ: "", ы: "y", ь: "", э: "e", ю: "yu",
    я: "ya",
  };
  return s
    .toLowerCase()
    .split("")
    .map((ch) => map[ch] ?? ch)
    .join("")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}
