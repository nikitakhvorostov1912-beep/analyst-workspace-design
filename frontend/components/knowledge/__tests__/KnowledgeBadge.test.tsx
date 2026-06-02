/**
 * Tests for KnowledgeBadge — бейдж «3 источника знаний» (P0 user-facing).
 */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { KnowledgeBadge } from "../KnowledgeBadge";
import type { UseSourcesStatus } from "@/hooks/useSourcesStatus";

vi.mock("@/hooks/useSourcesStatus", () => ({
  useSourcesStatus: vi.fn(),
}));

import { useSourcesStatus } from "@/hooks/useSourcesStatus";

const mockHook = vi.mocked(useSourcesStatus);

function makeStatus(over: Partial<UseSourcesStatus> = {}): UseSourcesStatus {
  return {
    base: { state: "ready", detail: "подключение живо · 12 инструментов" },
    typical: { state: "ready", detail: "4 конфигурации · 63 207 карточек" },
    its: { state: "ready", detail: "Напарник на связи · живая ИТС" },
    itsStatic: {
      chunks: 2543,
      documents: 600,
      enabled: true,
      ready: true,
      provider: "openai",
      model: "text-embedding-3-small",
      dim: 1536,
      docs_root: "/repo/tools/v8std/docs",
    },
    bspStatic: {
      methods: 1820,
      modules: 556,
      by_version: { "3.2": 1820 },
      enabled: true,
      ready: true,
      ssl_roots: ["/repo/tools/ssl_3_2"],
    },
    loading: false,
    refresh: vi.fn(),
    ...over,
  };
}

afterEach(() => {
  vi.resetAllMocks();
});

describe("KnowledgeBadge (3 источника)", () => {
  it("рендерит бейдж с подписью «Источники»", () => {
    mockHook.mockReturnValue(makeStatus());
    render(<KnowledgeBadge />);
    expect(screen.getByTestId("knowledge-badge")).toBeInTheDocument();
    expect(screen.getByText("Источники")).toBeInTheDocument();
  });

  it("открывает popover c тремя источниками по клику", async () => {
    mockHook.mockReturnValue(makeStatus());
    render(<KnowledgeBadge />);
    fireEvent.click(screen.getByTestId("knowledge-badge"));
    await waitFor(() => {
      expect(screen.getByTestId("knowledge-badge-popover")).toBeInTheDocument();
    });
    expect(screen.getByText("Ваша база 1С")).toBeInTheDocument();
    expect(screen.getByText("Типовая конфигурация")).toBeInTheDocument();
    expect(screen.getByText("ИТС · Напарник")).toBeInTheDocument();
  });

  it("показывает live-детали источников и статический RAG", async () => {
    mockHook.mockReturnValue(makeStatus());
    render(<KnowledgeBadge />);
    fireEvent.click(screen.getByTestId("knowledge-badge"));
    await waitFor(() => {
      expect(
        screen.getByText(/Напарник на связи · живая ИТС/),
      ).toBeInTheDocument();
    });
    expect(screen.getByText(/Локальный RAG: ИТС 2543/)).toBeInTheDocument();
    expect(screen.getByText("openai")).toBeInTheDocument();
  });

  it("ИТС down — показывает «недоступен»", async () => {
    mockHook.mockReturnValue(
      makeStatus({
        its: { state: "down", detail: "Напарник недоступен — запустите 1c-buddy :6002" },
      }),
    );
    render(<KnowledgeBadge />);
    fireEvent.click(screen.getByTestId("knowledge-badge"));
    await waitFor(() => {
      expect(
        screen.getByText(/Напарник недоступен/),
      ).toBeInTheDocument();
    });
  });

  it("popover закрывается повторным кликом", async () => {
    mockHook.mockReturnValue(makeStatus());
    render(<KnowledgeBadge />);
    const badge = screen.getByTestId("knowledge-badge");
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
});
