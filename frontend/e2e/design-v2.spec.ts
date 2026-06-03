/**
 * E2E: Design v2 visual smoke (Phase 11).
 *
 * Проверяет визуальные изменения Phase 11.1-11.5:
 * - Header brand mark «1С» в accent square
 * - AnonymizationToggle amber pill toggle
 * - ModelBadge Sparkles + mono model name
 * - Onboarding wizard 4 шага (Learn opt-in на шаге 3, Готово на шаге 4)
 *
 * НЕ покрывает: chat streaming, ToolTrace mini chips, StreamingStages (vitest unit-тесты).
 */
import { test, expect } from "@playwright/test";
import { setupOnboardingMocks } from "./mocks/onboarding-handlers";

const LEGACY_CONNECTIONS = [
  {
    id: "c1",
    name: "Test Channel",
    endpoint: "http://localhost:6010/mcp",
    channel: null,
    anon_enabled: false,
    last_seen_at: null,
    created_at: new Date().toISOString(),
  },
];

const LEGACY_LLM = {
  id: "default" as const,
  endpoint: "http://localhost:1234/v1",
  model: "gpt-4o-mini",
  temperature: 0.3,
};

test.describe("Shell v3 — Header layout (3 зоны)", () => {
  test("Header: 3 цели справа (Search · StatusCapsule · ⋯), база слева", async ({ page }) => {
    await setupOnboardingMocks(page, {
      initialConnections: LEGACY_CONNECTIONS,
      initialLLM: LEGACY_LLM,
    });
    await page.addInitScript(() => localStorage.clear());

    await page.goto("/");

    const header = page.getByTestId("app-header");
    await expect(header).toBeVisible({ timeout: 15000 });

    // Зона 1 — контекст базы слева
    await expect(page.getByTestId("channel-selector-button")).toBeVisible();
    // Зона 3 — статус + overflow (Search-кнопка появляется при onOpenCmdK)
    await expect(page.getByTestId("status-capsule")).toBeVisible();
    await expect(page.getByTestId("overflow-menu")).toBeVisible();

    // ModelBadge / отдельный anon-pill убраны из хедера (поглощены StatusCapsule)
    await expect(page.getByTestId("model-badge")).toHaveCount(0);
  });

  test("StatusCapsule открывается → база / модель / анонимизация в одном месте", async ({ page }) => {
    await setupOnboardingMocks(page, {
      initialConnections: LEGACY_CONNECTIONS,
      initialLLM: LEGACY_LLM,
    });
    await page.addInitScript(() => localStorage.clear());

    await page.goto("/");

    const capsule = page.getByTestId("status-capsule");
    await expect(capsule).toBeVisible({ timeout: 15000 });
    await capsule.click();

    // В поповере — подсистемы (стабильные русские подписи)
    await expect(page.getByText("Модель", { exact: true })).toBeVisible();
    await expect(page.getByTestId("anon-status")).toBeVisible();
    await expect(page.getByText("Анонимизация")).toBeVisible();

    // Esc закрывает
    await page.keyboard.press("Escape");
    await expect(page.getByText("Анонимизация")).not.toBeVisible();
  });

  test("OverflowMenu «⋯» — подписанные пункты + переключение темы", async ({ page }) => {
    await setupOnboardingMocks(page, {
      initialConnections: LEGACY_CONNECTIONS,
      initialLLM: LEGACY_LLM,
    });
    await page.addInitScript(() => localStorage.clear());

    await page.goto("/");

    await page.getByTestId("overflow-menu").click();
    await expect(page.getByTestId("theme-toggle")).toBeVisible();
    await expect(page.getByText("Настройки")).toBeVisible();
    await expect(page.getByText("Диагностика")).toBeVisible();

    // Тема переключается → data-theme на <html>
    await page.getByTestId("theme-toggle").click();
    const theme = await page.evaluate(() =>
      document.documentElement.getAttribute("data-theme"),
    );
    expect(theme).toBe("light");
  });

  test("EnvBadge: помеченная как ПРОД база выделяется в чипе", async ({ page }) => {
    await setupOnboardingMocks(page, {
      initialConnections: LEGACY_CONNECTIONS,
      initialLLM: LEGACY_LLM,
    });
    // Вариант B: окружение в localStorage по id подключения + активный канал c1
    await page.addInitScript(() => {
      localStorage.clear();
      localStorage.setItem("analyst.active_channel", "c1");
      localStorage.setItem("analyst.connection_env", JSON.stringify({ c1: "prod" }));
    });

    await page.goto("/");

    const chip = page.getByTestId("channel-selector-button");
    await expect(chip).toBeVisible({ timeout: 15000 });
    const badge = chip.getByTestId("env-badge");
    await expect(badge).toHaveText("ПРОД");
    await expect(badge).toHaveAttribute("data-env", "prod");
  });
});

test.describe("Design v2 — Onboarding 4-step (Phase 11.3)", () => {
  test("first-run: wizard показывает 4 шага с Learn opt-in на шаге 3", async ({ page }) => {
    await setupOnboardingMocks(page, { initialConnections: [], initialLLM: null });
    await page.addInitScript(() => {
      localStorage.clear();
      sessionStorage.clear();
    });

    await page.goto("/");

    // Шаг 1: MCP
    await expect(page.getByText("Подключите вашу базу 1С")).toBeVisible({ timeout: 15000 });

    await page.getByPlaceholder("Моя база").fill("Local 1C");
    await page.getByPlaceholder("http://localhost:6010/mcp").fill("http://localhost:6010/mcp");
    await page.getByRole("button", { name: "Сохранить" }).click();
    await expect(page.getByText("База 1С отвечает")).toBeVisible({ timeout: 10000 });

    await page.getByRole("button", { name: /Далее/ }).click();

    // Шаг 2: LLM
    await expect(page.getByText("Подключите модель ИИ")).toBeVisible();
    await page.getByPlaceholder("http://localhost:1234/v1").fill("http://localhost:1234/v1");
    await page.getByPlaceholder("gpt-4o-mini").fill("gpt-4o-mini");
    await page.getByPlaceholder("sk-...").fill("sk-test-1234567890");
    await page.getByRole("button", { name: "Тест" }).click();
    await expect(page.getByText(/Модель отвечает/i)).toBeVisible({ timeout: 10000 });
    await page.getByRole("button", { name: "Сохранить" }).click();
    await expect(page.getByText("Настройки модели ИИ сохранены")).toBeVisible({ timeout: 10000 });
    await page.getByRole("button", { name: /Далее/ }).click();

    // Шаг 3 NEW: Learn opt-in
    await expect(page.getByTestId("onboarding-step-learn")).toBeVisible({ timeout: 10000 });
    const learnSwitch = page.getByRole("switch").first();
    await expect(learnSwitch).toBeVisible();

    // Шаг 4: Готово
    await page.getByRole("button", { name: /Далее/ }).click();
    await expect(page.getByText("Готово!")).toBeVisible({ timeout: 10000 });

    await page.getByRole("button", { name: "Начать работу" }).click();
    await expect(page.getByText("Подключите вашу базу 1С")).not.toBeVisible({ timeout: 10000 });

    const completed = await page.evaluate(() =>
      localStorage.getItem("analyst.onboarding_completed"),
    );
    expect(completed).toBe("true");
  });

  test("Learn switch toggle: переключается и сохраняется в localStorage", async ({ page }) => {
    await setupOnboardingMocks(page, { initialConnections: [], initialLLM: null });
    await page.addInitScript(() => {
      localStorage.clear();
      sessionStorage.clear();
    });

    await page.goto("/");

    // Прохождение шагов 1+2
    await expect(page.getByText("Подключите вашу базу 1С")).toBeVisible({ timeout: 15000 });
    await page.getByPlaceholder("Моя база").fill("Test");
    await page.getByPlaceholder("http://localhost:6010/mcp").fill("http://localhost:6010/mcp");
    await page.getByRole("button", { name: "Сохранить" }).click();
    await expect(page.getByText("База 1С отвечает")).toBeVisible({ timeout: 10000 });
    await page.getByRole("button", { name: /Далее/ }).click();

    await page.getByPlaceholder("http://localhost:1234/v1").fill("http://localhost:1234/v1");
    await page.getByPlaceholder("gpt-4o-mini").fill("gpt-4o-mini");
    await page.getByPlaceholder("sk-...").fill("sk-test-1234567890");
    await page.getByRole("button", { name: "Тест" }).click();
    await expect(page.getByText(/Модель отвечает/i)).toBeVisible({ timeout: 10000 });
    await page.getByRole("button", { name: "Сохранить" }).click();
    await expect(page.getByText("Настройки модели ИИ сохранены")).toBeVisible({ timeout: 10000 });
    await page.getByRole("button", { name: /Далее/ }).click();

    // Шаг 3: Learn opt-in
    await expect(page.getByTestId("onboarding-step-learn")).toBeVisible({ timeout: 10000 });
    const learnSwitch = page.getByRole("switch").first();
    await expect(learnSwitch).toBeVisible();

    // Включаем Learn
    await learnSwitch.click();
    await page.getByRole("button", { name: /Далее/ }).click();
    await page.getByRole("button", { name: "Начать работу" }).click();

    // Проверяем флаг
    const learnEnabled = await page.evaluate(() =>
      localStorage.getItem("analyst.learn_enabled"),
    );
    expect(learnEnabled).toBe("true");
  });
});
