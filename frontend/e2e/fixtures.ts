/**
 * Вспомогательные функции для E2E тестов.
 * Используем Playwright route() вместо MSW для упрощения архитектуры.
 */
import type { Page } from "@playwright/test";

const BACKEND = "http://localhost:8010";

/** Данные для mock подключений. */
export const MOCK_CONNECTIONS = [
  {
    id: "db-a",
    name: "База А",
    endpoint: "http://localhost:6010/mcp",
    channel: "db-a",
    anon_enabled: false,
    last_seen_at: null,
    created_at: new Date().toISOString(),
  },
  {
    id: "db-b",
    name: "База Б",
    endpoint: "http://localhost:6003/mcp",
    channel: "db-b",
    anon_enabled: false,
    last_seen_at: null,
    created_at: new Date().toISOString(),
  },
];

/** Данные для mock сессий с разными датами. */
export function makeMockSessions() {
  const now = new Date();
  const yesterday = new Date(now.getTime() - 24 * 60 * 60 * 1000);
  const lastWeek = new Date(now.getTime() - 5 * 24 * 60 * 60 * 1000);
  const earlier = new Date(now.getTime() - 20 * 24 * 60 * 60 * 1000);

  return {
    today: [
      {
        id: "s-today-1",
        title: "Сессия сегодня 1",
        channel_id: "db-a",
        updated_at: now.toISOString(),
        message_count: 2,
      },
      {
        id: "s-today-2",
        title: "Сессия сегодня 2",
        channel_id: "db-a",
        updated_at: new Date(now.getTime() - 3600000).toISOString(),
        message_count: 1,
      },
    ],
    yesterday: [
      {
        id: "s-yesterday-1",
        title: "Сессия вчера",
        channel_id: "db-a",
        updated_at: yesterday.toISOString(),
        message_count: 3,
      },
    ],
    this_week: [
      {
        id: "s-week-1",
        title: "Сессия на этой неделе",
        channel_id: "db-a",
        updated_at: lastWeek.toISOString(),
        message_count: 5,
      },
    ],
    earlier: [
      {
        id: "s-earlier-1",
        title: "Сессия раньше",
        channel_id: "db-a",
        updated_at: earlier.toISOString(),
        message_count: 10,
      },
    ],
  };
}

/** Mock сообщения для сессии. */
export const MOCK_MESSAGES = [
  {
    id: "m-1",
    role: "user" as const,
    content: "Расскажи про базу",
    tool_calls: null,
    cards: null,
    duration_ms: null,
    created_at: new Date().toISOString(),
  },
  {
    id: "m-2",
    role: "assistant" as const,
    content: "Привет, я ассистент",
    tool_calls: [],
    cards: [],
    duration_ms: 500,
    created_at: new Date().toISOString(),
  },
];

/** SSE mock-поток для /chat. */
function makeSseBody(): string {
  const events = [
    `event: status\ndata: {"stage":"thinking"}\n\n`,
    `event: delta\ndata: {"content":"Привет, я ассистент"}\n\n`,
    `event: done\ndata: {"message_id":"m-mock","total_duration_ms":42}\n\n`,
  ];
  return events.join("");
}

/**
 * Регистрирует все route() mock'и для backend API.
 * Вызывать в beforeEach перед goto().
 */
export async function setupRoutes(page: Page): Promise<void> {
  // Health check
  await page.route(`${BACKEND}/health`, (route) =>
    route.fulfill({ json: { status: "ok", version: "0.1.0", db: "ok" } }),
  );

  // Connections list
  await page.route(`${BACKEND}/connections`, (route) => {
    if (route.request().method() === "GET") {
      return route.fulfill({ json: { connections: MOCK_CONNECTIONS } });
    }
    if (route.request().method() === "POST") {
      const body = route.request().postDataJSON() as Record<string, string>;
      return route.fulfill({
        status: 201,
        json: {
          id: "conn-new",
          name: body["name"] ?? "New",
          endpoint: body["endpoint"] ?? "",
          channel: body["channel"] ?? null,
          anon_enabled: false,
          last_seen_at: null,
          created_at: new Date().toISOString(),
        },
      });
    }
    return route.continue();
  });

  // Connection ping
  await page.route(`${BACKEND}/connections/*/ping`, (route) =>
    route.fulfill({
      json: {
        mcp_version: "2025-03-26",
        tool_count: 10,
        session_id: "mock-sid",
        duration_ms: 50,
        last_seen_at: new Date().toISOString(),
      },
    }),
  );

  // Sessions list
  await page.route(`${BACKEND}/sessions`, (route) => {
    if (route.request().method() === "GET") {
      return route.fulfill({ json: makeMockSessions() });
    }
    if (route.request().method() === "POST") {
      const body = route.request().postDataJSON() as Record<string, string>;
      return route.fulfill({
        json: {
          id: "s-new",
          title: null,
          channel_id: body["channel_id"] ?? "db-a",
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      });
    }
    return route.continue();
  });

  // Session detail + messages
  await page.route(`${BACKEND}/sessions/*/messages`, (route) =>
    route.fulfill({ json: { messages: MOCK_MESSAGES } }),
  );

  await page.route(`${BACKEND}/sessions/*`, (route) => {
    if (route.request().method() === "GET") {
      const url = route.request().url();
      const id = url.split("/").pop() ?? "s-mock";
      return route.fulfill({
        json: {
          id,
          title: "Сессия mock",
          channel_id: "db-a",
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      });
    }
    if (route.request().method() === "DELETE") {
      return route.fulfill({ status: 204, body: "" });
    }
    return route.continue();
  });

  // Chat SSE stream
  await page.route(`${BACKEND}/chat`, (route) => {
    const body = makeSseBody();
    return route.fulfill({
      status: 200,
      headers: { "content-type": "text/event-stream", "cache-control": "no-cache" },
      body,
    });
  });

  // Chat confirm
  await page.route(`${BACKEND}/chat/confirm`, (route) =>
    route.fulfill({ status: 204, body: "" }),
  );

  // MCP ping
  await page.route(`${BACKEND}/mcp/**`, (route) =>
    route.fulfill({
      json: {
        mcp_version: "2025-03-26",
        tool_count: 10,
        session_id: "mock-sid",
        duration_ms: 50,
      },
    }),
  );
}

/** LLM config для localStorage. */
export const MOCK_LLM_CONFIG = {
  api_key: "test-key",
  endpoint: "http://localhost:11434/v1",
  model: "test-model",
};

/**
 * Устанавливает данные в localStorage до загрузки страницы.
 * Вызывать ПОСЛЕ goto() с пустым состоянием или через addInitScript.
 */
export async function setLocalStorage(
  page: Page,
  data: {
    llmConfig?: typeof MOCK_LLM_CONFIG;
    connections?: typeof MOCK_CONNECTIONS;
    activeChannelId?: string;
  },
): Promise<void> {
  // Ключи должны совпадать с frontend/lib/storage.ts
  await page.evaluate((d) => {
    if (d.llmConfig) {
      localStorage.setItem("analyst.llm", JSON.stringify(d.llmConfig));
    }
    if (d.connections) {
      localStorage.setItem("analyst.mcp_connections", JSON.stringify(d.connections));
    }
    if (d.activeChannelId) {
      localStorage.setItem("analyst.active_channel", d.activeChannelId);
    }
  }, data);
}
