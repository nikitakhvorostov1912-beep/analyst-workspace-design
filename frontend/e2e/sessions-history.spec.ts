/**
 * E2E: Sessions history — 4 группы в sidebar, click → загрузка истории.
 *
 * Сценарий:
 * 1. Mock GET /sessions возвращает 4 группы (Сегодня/Вчера/На этой неделе/Раньше)
 * 2. Открываем / с конфигурацией → sidebar показывает 4 секции
 * 3. Click на первую сессию «Сегодня» → URL меняется на /sessions/{id}
 * 4. Mock GET /sessions/{id}/messages → DOM содержит оба сообщения
 */
import { test, expect } from "@playwright/test";
import { MOCK_LLM_CONFIG, MOCK_CONNECTIONS, setupRoutes } from "./fixtures";

test.describe("sessions-history", () => {
  test.beforeEach(async ({ page }) => {
    await setupRoutes(page);
    await page.addInitScript(
      ({ llm, conns }: { llm: typeof MOCK_LLM_CONFIG; conns: typeof MOCK_CONNECTIONS }) => {
        localStorage.setItem("analyst.llm", JSON.stringify(llm));
        localStorage.setItem("analyst.mcp_connections", JSON.stringify(conns));
        localStorage.setItem("analyst.active_channel", conns[0]?.id ?? "db-a");
      },
      { llm: MOCK_LLM_CONFIG, conns: MOCK_CONNECTIONS },
    );
  });

  test("sidebar показывает группы 'Сегодня' и 'Вчера'", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Ждём загрузки сессий — sidebar должен показать секции
    await expect(page.getByText("Сегодня")).toBeVisible({ timeout: 5000 });
    await expect(page.getByText("Вчера")).toBeVisible();
  });

  test("sidebar показывает все 4 группы", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    await expect(page.getByText("Сегодня")).toBeVisible({ timeout: 5000 });
    await expect(page.getByText("Вчера")).toBeVisible();
    // "На этой неделе" — поиск по части текста
    await expect(page.getByText(/неделе/i)).toBeVisible();
    await expect(page.getByText(/Раньше/i)).toBeVisible();
  });

  test("click на сессию → URL обновляется, показываются сообщения", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Ждём появления элемента с первой сессией «Сегодня»
    await expect(page.getByText("Сегодня")).toBeVisible({ timeout: 5000 });

    // Кликаем на первую сессию «Сессия сегодня 1»
    await page.getByText("Сессия сегодня 1").click();

    // URL должен обновиться на /sessions/s-today-1
    await expect(page).toHaveURL(/\/sessions\/s-today-1/);

    // Сообщения из mock /sessions/s-today-1/messages
    await expect(page.getByText("Привет, я ассистент")).toBeVisible({ timeout: 5000 });
  });
});
