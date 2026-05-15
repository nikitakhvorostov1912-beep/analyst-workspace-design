/**
 * Slash-команды: /sql /journal /find /audit /clear
 * expandSlashCommand — pure функция, не зависит от React.
 */

export type SlashCommandKey = "sql" | "journal" | "find" | "audit" | "clear";

export type SlashCommand = {
  key: SlashCommandKey;
  label: string;
  description: string;
  argsPlaceholder: string;
  /** /clear — только клиентское действие (не отправляется в LLM) */
  isClient: boolean;
};

export const SLASH_COMMANDS: SlashCommand[] = [
  {
    key: "sql",
    label: "/sql",
    description: "Выполнить SQL-запрос",
    argsPlaceholder: "<query>",
    isClient: false,
  },
  {
    key: "journal",
    label: "/journal",
    description: "Журнал регистрации с фильтрами",
    argsPlaceholder: "[фильтры]",
    isClient: false,
  },
  {
    key: "find",
    label: "/find",
    description: "Найти где используется объект",
    argsPlaceholder: "<имя>",
    isClient: false,
  },
  {
    key: "audit",
    label: "/audit",
    description: "Полный аудит объекта",
    argsPlaceholder: "<объект>",
    isClient: false,
  },
  {
    key: "clear",
    label: "/clear",
    description: "Очистить ввод",
    argsPlaceholder: "",
    isClient: true,
  },
];

export type ExpandResult =
  | { isClientAction: "clear" }
  | { prompt: string }
  | null;

/**
 * Разворачивает slash-команду в полный промпт.
 *
 * "/sql SELECT 1" → { prompt: "Выполни запрос:\n```sql\nSELECT 1\n```" }
 * "/clear ..." → { isClientAction: "clear" }
 * "/journal Период=Час" → { prompt: "Покажи журнал регистрации с фильтрами: Период=Час" }
 * "/find Контрагент" → { prompt: "Найди где используется Контрагент" }
 * "/audit Документ.ОПП" → { prompt: "Проведи полный аудит Документ.ОПП: ..." }
 * Возвращает null если префикс не является slash-командой.
 */
export function expandSlashCommand(input: string): ExpandResult {
  if (!input.startsWith("/")) return null;

  const trimmed = input.slice(1); // убираем ведущий /
  const spaceIdx = trimmed.indexOf(" ");
  const key = spaceIdx === -1 ? trimmed : trimmed.slice(0, spaceIdx);
  const args = spaceIdx === -1 ? "" : trimmed.slice(spaceIdx + 1).trim();

  const command = SLASH_COMMANDS.find((c) => c.key === key);
  if (!command) return null;

  if (command.isClient) {
    return { isClientAction: "clear" };
  }

  switch (key) {
    case "sql": {
      const body = args ? `\`\`\`sql\n${args}\n\`\`\`` : "```sql\n\n```";
      return { prompt: `Выполни запрос:\n${body}` };
    }
    case "journal": {
      const filter = args ? `: ${args}` : "";
      return { prompt: `Покажи журнал регистрации с фильтрами${filter}` };
    }
    case "find": {
      const name = args || "";
      return { prompt: `Найди где используется ${name}`.trim() };
    }
    case "audit": {
      const obj = args || "";
      return {
        prompt: `Проведи полный аудит ${obj}: реквизиты, ТЧ, формы, права, использование`.trim(),
      };
    }
    default:
      return null;
  }
}
