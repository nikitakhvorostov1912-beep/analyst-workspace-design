/**
 * Mock данные для E2E тестов.
 * Используем Playwright route() — не MSW (Karpathy Simplicity).
 * Реальные handlers-функции находятся в ../fixtures.ts (setupRoutes).
 */

export { MOCK_CONNECTIONS, MOCK_LLM_CONFIG, MOCK_MESSAGES, makeMockSessions } from "../fixtures";
