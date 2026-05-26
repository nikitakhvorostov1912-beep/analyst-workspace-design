/**
 * Tests for hooks/useIndexerStatus (M-K2.10).
 *
 * Все тесты используют pollIntervalMs=0 чтобы изолировать polling и не
 * утечь setTimeout между тестами. Polling-логика покрывается через
 * фактическое поведение в IndexerProgress компоненте (E2E mock).
 */

import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useIndexerStatus } from "../useIndexerStatus";

vi.mock("@/lib/api", () => ({
  getIndexerStatus: vi.fn(),
  startIndexer: vi.fn(),
}));

import { getIndexerStatus, startIndexer } from "@/lib/api";

const mockGetStatus = vi.mocked(getIndexerStatus);
const mockStartIndexer = vi.mocked(startIndexer);

const NO_POLL = { pollIntervalMs: 0, idlePollIntervalMs: 0 };

afterEach(() => {
  vi.resetAllMocks();
});

const baseRun = {
  id: 1,
  channel_id: "ch-1",
  started_at: "2026-05-26T09:00:00+00:00",
  finished_at: null as string | null,
  duration_ms: null as number | null,
  objects_total: 0,
  objects_written: 0,
  objects_skipped: 0,
  error: null as string | null,
};

const idleStatus = {
  channel_id: "ch-1",
  latest: null,
  running: null,
};

const doneStatus = {
  channel_id: "ch-1",
  latest: { ...baseRun, status: "done" as const, objects_written: 42, duration_ms: 5000, finished_at: "2026-05-26T09:00:05+00:00" },
  running: null,
};

const runningStatus = {
  channel_id: "ch-1",
  latest: null,
  running: { ...baseRun, id: 2, status: "running" as const, objects_written: 7 },
};

describe("useIndexerStatus", () => {
  it("fetches status on mount and exposes latest+running", async () => {
    mockGetStatus.mockResolvedValue(doneStatus);

    const { result, unmount } = renderHook(() =>
      useIndexerStatus("ch-1", NO_POLL),
    );

    await waitFor(() => {
      expect(result.current.status).not.toBeNull();
    });

    expect(result.current.isRunning).toBe(false);
    expect(result.current.latest?.objects_written).toBe(42);
    expect(result.current.running).toBeNull();
    expect(result.current.error).toBeNull();
    unmount();
  });

  it("returns null status when channelId is null", () => {
    const { result, unmount } = renderHook(() =>
      useIndexerStatus(null, NO_POLL),
    );
    expect(result.current.status).toBeNull();
    expect(result.current.isRunning).toBe(false);
    expect(mockGetStatus).not.toHaveBeenCalled();
    unmount();
  });

  it("captures fetch errors in state without throwing", async () => {
    mockGetStatus.mockRejectedValue(new Error("Network fail"));

    const { result, unmount } = renderHook(() =>
      useIndexerStatus("ch-1", NO_POLL),
    );

    await waitFor(() => {
      expect(result.current.error).toBe("Network fail");
    });
    expect(result.current.status).toBeNull();
    unmount();
  });

  it("start() POSTs and immediately updates state to running", async () => {
    mockGetStatus.mockResolvedValue(idleStatus);
    mockStartIndexer.mockResolvedValueOnce({
      run_id: 99,
      channel_id: "ch-1",
      status: "running",
      started_at: "2026-05-26T09:30:00+00:00",
      message: "ok",
    });

    const { result, unmount } = renderHook(() =>
      useIndexerStatus("ch-1", NO_POLL),
    );

    await waitFor(() => {
      expect(result.current.status).not.toBeNull();
    });

    await act(async () => {
      await result.current.start();
    });

    expect(mockStartIndexer).toHaveBeenCalledWith("ch-1");
    expect(result.current.isRunning).toBe(true);
    expect(result.current.running?.id).toBe(99);
    expect(result.current.error).toBeNull();
    unmount();
  });

  it("start() with 409 sets current_run from error.cause", async () => {
    mockGetStatus.mockResolvedValue(idleStatus);
    const err = new Error("уже запущен");
    (err as Error & { cause?: unknown }).cause = runningStatus.running;
    mockStartIndexer.mockRejectedValueOnce(err);

    const { result, unmount } = renderHook(() =>
      useIndexerStatus("ch-1", NO_POLL),
    );

    await waitFor(() => {
      expect(result.current.status).not.toBeNull();
    });

    await act(async () => {
      try {
        await result.current.start();
      } catch {
        // start re-raises, это OK
      }
    });

    expect(result.current.isRunning).toBe(true);
    expect(result.current.running?.id).toBe(2);
    expect(result.current.error).toContain("уже запущен");
    unmount();
  });

  it("start() reports error when channelId is null", async () => {
    const { result, unmount } = renderHook(() =>
      useIndexerStatus(null, NO_POLL),
    );
    await act(async () => {
      await result.current.start();
    });
    expect(result.current.error).toContain("не выбран");
    expect(mockStartIndexer).not.toHaveBeenCalled();
    unmount();
  });

  it("refresh() force-fetches status", async () => {
    mockGetStatus
      .mockResolvedValueOnce(doneStatus)
      .mockResolvedValueOnce({
        ...doneStatus,
        latest: { ...doneStatus.latest!, objects_written: 100 },
      });

    const { result, unmount } = renderHook(() =>
      useIndexerStatus("ch-1", NO_POLL),
    );

    await waitFor(() => {
      expect(result.current.latest?.objects_written).toBe(42);
    });

    await act(async () => {
      await result.current.refresh();
    });

    expect(result.current.latest?.objects_written).toBe(100);
    unmount();
  });

  it("does not fetch on mount when fetchOnMount=false", async () => {
    const { unmount } = renderHook(() =>
      useIndexerStatus("ch-1", { ...NO_POLL, fetchOnMount: false }),
    );
    // microtask + минимальный setTimeout
    await new Promise((r) => setTimeout(r, 30));
    expect(mockGetStatus).not.toHaveBeenCalled();
    unmount();
  });

  it("isRunning shortcut reflects status.running", async () => {
    mockGetStatus.mockResolvedValue(runningStatus);

    const { result, unmount } = renderHook(() =>
      useIndexerStatus("ch-1", NO_POLL),
    );

    await waitFor(() => {
      expect(result.current.isRunning).toBe(true);
    });
    expect(result.current.running?.objects_written).toBe(7);
    unmount();
  });
});
