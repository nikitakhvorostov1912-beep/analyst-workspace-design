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

test.describe("Design v2 — Header layout (Phase 11.3)", () => {
  test("Header содержит brand mark «1С» в accent square 28×28", async ({ page }) => {
    await setupOnboardingMocks(page, {
      initialConnections: LEGACY_CONNECTIONS,
      initialLLM: LEGACY_LLM,
    });
    await page.addInitScript(() => {
      localStorage.clear();
    });

    await page.goto("/");

    // Header rendered (legacy guard auto-set onboarding flag)
    const header = page.getByTestId("app-header");
    await expect(header).toBeVisible({ timeout: 15000 });

    // Brand mark «1С» в accent square
    await expect(header.getByText("1С", { exact: true })).toBeVisible();

    // Версия и app name
    await expect(header.getByText("v1.2.1")).toBeVisible();
    await expect(header.getByText("Аналитик")).toBeVisible();
  });

  test("AnonymizationToggle переключается ВКЛ → amber pill", async ({ page }) => {
    await setupOnboardingMocks(page, {
      initialConnections: LEGACY_CONNECTIONS,
      initialLLM: LEGACY_LLM,
    });
    await page.addInitScript(() => {
      localStorage.clear();
    });

    await page.goto("/");

    const toggle = page.getByRole("button", { name: "Переключатель анонимизации" });
    await expect(toggle).toBeVisible({ timeout: 15000 });

    // Изначально ВЫКЛ
    await expect(toggle).toHaveAttribute("data-anon", "off");

    // Клик → ВКЛ + amber styling
    await toggle.click();
    await expect(toggle).toHaveAttribute("data-anon", "on");
    await expect(toggle).toHaveAttribute("aria-pressed", "true");

    // Visual: amber pill — class содержит warning palette
    const cls = await toggle.getAttribute("class");
    expect(cls).toMatch(/warning/);

    // Повторный клик → ВЫКЛ
    await toggle.click();
    await expect(toggle).toHaveAttribute("data-anon", "off");
  });

  test("ModelBadge показывает Sparkles + читаемое имя модели + tech id в data-model", async ({ page }) => {
    await setupOnboardingMocks(page, {
      initialConnections: LEGACY_CONNECTIONS,
      initialLLM: { ...LEGACY_LLM, model: "claude-sonnet-4-6", temperature: 0.7 },
    });
    await page.addInitScript(() => {
      localStorage.clear();
    });

    await page.goto("/");

    const badge = page.getByTestId("model-badge");
    await expect(badge).toBeVisible({ timeout: 15000 });
    // Видимый текст — человекочитаемое имя
    await expect(badge).toContainText("Claude Sonnet 4.6");
    await expect(badge).toContainText(/0\.7/);
    // Tech id доступен в data-атрибуте для интеграций
    await expect(badge).toHaveAttribute("data-model", "claude-sonnet-4-6");

    // Sparkles SVG icon
    const svg = badge.locator("svg").first();
    await expect(svg).toBeVisible();
  });

  test("ModelBadge: для unknown модели показывает tech id как есть", async ({ page }) => {
    await setupOnboardingMocks(page, {
      initialConnections: LEGACY_CONNECTIONS,
      initialLLM: { ...LEGACY_LLM, model: "some-custom-model-2025", temperature: 0.5 },
    });
    await page.addInitScript(() => {
      localStorage.clear();
    });

    await page.goto("/");

    const badge = page.getByTestId("model-badge");
    await expect(badge).toBeVisible({ timeout: 15000 });
    await expect(badge).toContainText("some-custom-model-2025");
    await expect(badge).toHaveAttribute("data-model", "some-custom-model-2025");
  });

  test("ModelBadge: Xiaomi MiMo v2 Pro отображается человекочитаемо", async ({ page }) => {
    await setupOnboardingMocks(page, {
      initialConnections: LEGACY_CONNECTIONS,
      initialLLM: { ...LEGACY_LLM, model: "mimo-v2-pro", temperature: 0.3 },
    });
    await page.addInitScript(() => {
      localStorage.clear();
    });

    await page.goto("/");

    const badge = page.getByTestId("model-badge");
    await expect(badge).toBeVisible({ timeout: 15000 });
    await expect(badge).toContainText("Xiaomi MiMo v2 Pro");
    await expect(badge).toHaveAttribute("data-model", "mimo-v2-pro");
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
