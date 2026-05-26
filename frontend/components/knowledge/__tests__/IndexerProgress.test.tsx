/**
 * Tests for components/knowledge/IndexerProgress (M-K2.10).
 *
 * Покрытие 4 состояний UI:
 *  - idle (нет latest, нет running) → кнопка «Изучить базу»
 *  - running → animated chip с прогрессом
 *  - done → success chip + relative time + retry
 *  - failed → error chip + сообщение + retry
 */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api", () => ({
  getIndexerStatus: vi.fn(),
  startIndexer: vi.fn(),
}));

import { getIndexerStatus, startIndexer } from "@/lib/api";
import { IndexerProgress } from "../IndexerProgress";

const mockGet = vi.mocked(getIndexerStatus);
const mockStart = vi.mocked(startIndexer);

afterEach(() => {
  vi.restoreAllMocks();
});

const baseRun = {
  id: 1,
  channel_id: "ch-1",
  started_at: "2026-05-26T09:00:00+00:00",
  finished_at: null,
  duration_ms: null,
  objects_total: 0,
  objects_written: 0,
  objects_skipped: 0,
  error: null as string | null,
};

describe("IndexerProgress", () => {
  it("renders start button when no runs exist (idle state)", async () => {
    mockGet.mockResolvedValue({
      channel_id: "ch-1",
      latest: null,
      running: null,
    });

    render(<IndexerProgress channelId="ch-1" />);

    const button = await screen.findByTestId("indexer-start-button");
    expect(button).toHaveTextContent("Изучить базу");
    expect(screen.getByText(/Загрузит структуру/)).toBeInTheDocument();
  });

  it("renders running chip with object count", async () => {
    mockGet.mockResolvedValue({
      channel_id: "ch-1",
      latest: null,
      running: {
        ...baseRun,
        status: "running",
        objects_written: 42,
      },
    });

    render(<IndexerProgress channelId="ch-1" />);

    const chip = await screen.findByTestId("indexer-chip-running");
    expect(chip).toHaveTextContent("Индексирую");
    expect(chip).toHaveTextContent("42");
  });

  it("renders done chip with object count and retry button", async () => {
    mockGet.mockResolvedValue({
      channel_id: "ch-1",
      latest: {
        ...baseRun,
        status: "done",
        finished_at: "2026-05-26T09:00:05+00:00",
        duration_ms: 5000,
        objects_written: 123,
      },
      running: null,
    });

    render(<IndexerProgress channelId="ch-1" />);

    const chip = await screen.findByTestId("indexer-chip-done");
    expect(chip).toHaveTextContent("123 объектов");
    expect(screen.getByTestId("indexer-refresh-button")).toBeInTheDocument();
  });

  it("renders failed chip with error message and retry button", async () => {
    mockGet.mockResolvedValue({
      channel_id: "ch-1",
      latest: {
        ...baseRun,
        status: "failed",
        finished_at: "2026-05-26T09:00:01+00:00",
        duration_ms: 100,
        error: "MCP timeout: hardcore failure",
      },
      running: null,
    });

    render(<IndexerProgress channelId="ch-1" />);

    const chip = await screen.findByTestId("indexer-chip-failed");
    expect(chip).toHaveTextContent("Ошибка индексации");
    expect(screen.getByText(/MCP timeout/)).toBeInTheDocument();
    expect(screen.getByTestId("indexer-retry-button")).toBeInTheDocument();
  });

  it("clicking start triggers startIndexer", async () => {
    mockGet.mockResolvedValue({
      channel_id: "ch-1",
      latest: null,
      running: null,
    });
    mockStart.mockResolvedValue({
      run_id: 99,
      channel_id: "ch-1",
      status: "running",
      started_at: "2026-05-26T09:30:00+00:00",
      message: "ok",
    });

    render(<IndexerProgress channelId="ch-1" />);

    const button = await screen.findByTestId("indexer-start-button");
    fireEvent.click(button);

    await waitFor(() => {
      expect(mockStart).toHaveBeenCalledWith("ch-1");
    });
  });

  it("compact mode renders only chip without label", async () => {
    mockGet.mockResolvedValue({
      channel_id: "ch-1",
      latest: {
        ...baseRun,
        status: "done",
        finished_at: "2026-05-26T09:00:05+00:00",
        duration_ms: 5000,
        objects_written: 50,
      },
      running: null,
    });

    render(<IndexerProgress channelId="ch-1" compact />);

    const chip = await screen.findByTestId("indexer-chip-done");
    expect(chip).toBeInTheDocument();
    // В compact mode нет кнопки переиндексации и нет подписи
    expect(screen.queryByTestId("indexer-refresh-button")).toBeNull();
    expect(screen.queryByText(/Переиндексировать/)).toBeNull();
  });

  it("compact mode shows compact start button when idle", async () => {
    mockGet.mockResolvedValue({
      channel_id: "ch-1",
      latest: null,
      running: null,
    });

    render(<IndexerProgress channelId="ch-1" compact />);

    const btn = await screen.findByTestId("indexer-start-button-compact");
    expect(btn).toHaveTextContent("Изучить");
  });

  beforeEach(() => {
    // тесты могут запускаться с лагом из-за async, разумно ставим таймаут
    vi.setConfig({ testTimeout: 5000 });
  });
});
