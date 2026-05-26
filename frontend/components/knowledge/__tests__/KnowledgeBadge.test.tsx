/**
 * Tests for KnowledgeBadge (M-K2.11).
 */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { KnowledgeBadge } from "../KnowledgeBadge";

vi.mock("@/lib/api", () => ({
  getITSStatus: vi.fn(),
  getBSPStatus: vi.fn(),
}));

import { getBSPStatus, getITSStatus } from "@/lib/api";

const mockITS = vi.mocked(getITSStatus);
const mockBSP = vi.mocked(getBSPStatus);

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
  by_version: { "3.2": 1820 },
  enabled: true,
  ready: true,
  ssl_roots: ["/repo/tools/ssl_3_2"],
};

beforeEach(() => {
  // По умолчанию оба готовы — переопределяем в тестах
  mockITS.mockResolvedValue(itsReady);
  mockBSP.mockResolvedValue(bspReady);
});

afterEach(() => {
  vi.resetAllMocks();
});

describe("KnowledgeBadge", () => {
  it("renders badge with label containing counts", async () => {
    render(<KnowledgeBadge />);
    await waitFor(() => {
      expect(screen.getByTestId("knowledge-badge")).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByText(/ИТС 2543/)).toBeInTheDocument();
      expect(screen.getByText(/БСП 1820/)).toBeInTheDocument();
    });
  });

  it("показывает фоллбэк-надпись если оба индекса пустые/disabled", async () => {
    mockITS.mockResolvedValue({ ...itsReady, enabled: false });
    mockBSP.mockResolvedValue({ ...bspReady, enabled: false });

    render(<KnowledgeBadge />);
    await waitFor(() => {
      expect(screen.getByText("База знаний")).toBeInTheDocument();
    });
  });

  it("открывает popover по клику с подробностями", async () => {
    render(<KnowledgeBadge />);
    await waitFor(() => {
      expect(screen.getByTestId("knowledge-badge")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("knowledge-badge"));
    await waitFor(() => {
      expect(screen.getByTestId("knowledge-badge-popover")).toBeInTheDocument();
    });

    expect(screen.getByText("Локальная база знаний")).toBeInTheDocument();
    expect(screen.getByText("ИТС-стандарты")).toBeInTheDocument();
    expect(screen.getByText("БСП Pattern Index")).toBeInTheDocument();
  });

  it("popover содержит privacy-нотификацию", async () => {
    render(<KnowledgeBadge />);
    fireEvent.click(await screen.findByTestId("knowledge-badge"));

    await waitFor(() => {
      expect(screen.getByTestId("knowledge-badge-popover")).toBeInTheDocument();
    });
    expect(screen.getByText("Privacy")).toBeInTheDocument();
    expect(screen.getByText(/локально/i)).toBeInTheDocument();
    // provider name (openai)
    expect(screen.getByText("openai")).toBeInTheDocument();
  });

  it("popover закрывается повторным кликом", async () => {
    render(<KnowledgeBadge />);
    const badge = await screen.findByTestId("knowledge-badge");
    fireEvent.click(badge);
    await waitFor(() => {
      expect(screen.getByTestId("knowledge-badge-popover")).toBeInTheDocument();
    });
    fireEvent.click(badge);
    await waitFor(() => {
      expect(
        screen.queryByTestId("knowledge-badge-popover"),
      ).not.toBeInTheDocument();
    });
  });

  it("показывает версии БСП в popover если есть by_version", async () => {
    mockBSP.mockResolvedValue({
      ...bspReady,
      by_version: { "3.1": 500, "3.2": 1320 },
    });
    render(<KnowledgeBadge />);
    fireEvent.click(await screen.findByTestId("knowledge-badge"));

    await waitFor(() => {
      expect(
        screen.getByText(/3\.1 \(500\)/),
      ).toBeInTheDocument();
      expect(screen.getByText(/3\.2 \(1320\)/)).toBeInTheDocument();
    });
  });

  it("показывает hint про пустые индексы когда totalEntries=0", async () => {
    mockITS.mockResolvedValue({ ...itsReady, chunks: 0, documents: 0 });
    mockBSP.mockResolvedValue({
      ...bspReady,
      methods: 0,
      modules: 0,
      by_version: {},
    });
    render(<KnowledgeBadge />);
    fireEvent.click(await screen.findByTestId("knowledge-badge"));

    await waitFor(() => {
      expect(screen.getByText(/Индексы пусты/)).toBeInTheDocument();
    });
  });
});
