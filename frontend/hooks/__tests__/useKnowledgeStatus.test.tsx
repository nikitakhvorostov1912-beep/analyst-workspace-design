/**
 * Tests for hooks/useKnowledgeStatus (M-K2.11).
 *
 * pollIntervalMs=0 для изоляции (без setTimeout утечек).
 */

import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useKnowledgeStatus } from "../useKnowledgeStatus";

vi.mock("@/lib/api", () => ({
  getITSStatus: vi.fn(),
  getBSPStatus: vi.fn(),
}));

import { getBSPStatus, getITSStatus } from "@/lib/api";

const mockITS = vi.mocked(getITSStatus);
const mockBSP = vi.mocked(getBSPStatus);

const NO_POLL = { pollIntervalMs: 0 };

afterEach(() => {
  vi.resetAllMocks();
});

const itsReady = {
  chunks: 2543,
  documents: 600,
  enabled: true,
  ready: true,
  provider: "openai",
  model: "text-embedding-3-small",
  dim: 1536,
  docs_root: "/repo/tools/v8std/docs",
};

const bspReady = {
  methods: 1820,
  modules: 556,
  by_version: { "3.1": 0, "3.2": 1820 },
  enabled: true,
  ready: true,
  ssl_roots: ["/repo/tools/ssl_3_2"],
};

const itsDisabled = { ...itsReady, enabled: false, ready: false };
const bspEmpty = { ...bspReady, methods: 0, modules: 0, by_version: {} };

describe("useKnowledgeStatus", () => {
  it("returns null initially and fills after mount fetch", async () => {
    mockITS.mockResolvedValue(itsReady);
    mockBSP.mockResolvedValue(bspReady);

    const { result } = renderHook(() => useKnowledgeStatus(NO_POLL));

    expect(result.current.its).toBeNull();
    expect(result.current.bsp).toBeNull();

    await waitFor(() => {
      expect(result.current.its).toEqual(itsReady);
      expect(result.current.bsp).toEqual(bspReady);
    });
  });

  it("bothReady=true когда оба индекса enabled+ready", async () => {
    mockITS.mockResolvedValue(itsReady);
    mockBSP.mockResolvedValue(bspReady);

    const { result } = renderHook(() => useKnowledgeStatus(NO_POLL));

    await waitFor(() => {
      expect(result.current.bothReady).toBe(true);
      expect(result.current.anyReady).toBe(true);
    });
  });

  it("anyReady=true когда только один готов", async () => {
    mockITS.mockResolvedValue(itsReady);
    mockBSP.mockResolvedValue({ ...bspReady, ready: false });

    const { result } = renderHook(() => useKnowledgeStatus(NO_POLL));

    await waitFor(() => {
      expect(result.current.bothReady).toBe(false);
      expect(result.current.anyReady).toBe(true);
    });
  });

  it("bothReady=false когда оба disabled", async () => {
    mockITS.mockResolvedValue(itsDisabled);
    mockBSP.mockResolvedValue({ ...bspReady, enabled: false });

    const { result } = renderHook(() => useKnowledgeStatus(NO_POLL));

    await waitFor(() => {
      expect(result.current.bothReady).toBe(false);
      expect(result.current.anyReady).toBe(false);
    });
  });

  it("totalEntries = sum of chunks + methods", async () => {
    mockITS.mockResolvedValue(itsReady);
    mockBSP.mockResolvedValue(bspReady);

    const { result } = renderHook(() => useKnowledgeStatus(NO_POLL));

    await waitFor(() => {
      expect(result.current.totalEntries).toBe(2543 + 1820);
    });
  });

  it("Если один из endpoints упал — второй всё равно загружается", async () => {
    mockITS.mockRejectedValue(new Error("ITS endpoint down"));
    mockBSP.mockResolvedValue(bspReady);

    const { result } = renderHook(() => useKnowledgeStatus(NO_POLL));

    await waitFor(() => {
      expect(result.current.bsp).toEqual(bspReady);
    });
    expect(result.current.its).toBeNull();
    // error остаётся null (один из запросов прошёл)
    expect(result.current.error).toBeNull();
  });

  it("Если оба endpoints упали — error выставлен", async () => {
    mockITS.mockRejectedValue(new Error("ITS fail"));
    mockBSP.mockRejectedValue(new Error("BSP fail"));

    const { result } = renderHook(() => useKnowledgeStatus(NO_POLL));

    await waitFor(() => {
      expect(result.current.error).not.toBeNull();
    });
  });

  it("refresh() заново вызывает оба endpoints", async () => {
    mockITS.mockResolvedValue(itsReady);
    mockBSP.mockResolvedValue(bspReady);

    const { result } = renderHook(() => useKnowledgeStatus(NO_POLL));

    await waitFor(() => {
      expect(result.current.its).not.toBeNull();
    });

    mockITS.mockClear();
    mockBSP.mockClear();
    await result.current.refresh();

    expect(mockITS).toHaveBeenCalledTimes(1);
    expect(mockBSP).toHaveBeenCalledTimes(1);
  });

  it("fetchOnMount=false → не дёргает endpoints при mount", async () => {
    mockITS.mockResolvedValue(itsReady);
    mockBSP.mockResolvedValue(bspReady);

    renderHook(() =>
      useKnowledgeStatus({ pollIntervalMs: 0, fetchOnMount: false }),
    );

    // Дать чуть времени
    await new Promise((r) => setTimeout(r, 50));
    expect(mockITS).not.toHaveBeenCalled();
    expect(mockBSP).not.toHaveBeenCalled();
  });

  it("Пустой BSP индекс — totalEntries только из ИТС", async () => {
    mockITS.mockResolvedValue(itsReady);
    mockBSP.mockResolvedValue(bspEmpty);

    const { result } = renderHook(() => useKnowledgeStatus(NO_POLL));

    await waitFor(() => {
      expect(result.current.totalEntries).toBe(2543);
    });
  });
});
