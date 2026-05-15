import { render, screen, waitFor, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import "@testing-library/jest-dom";

vi.mock("@/lib/api", () => ({
  fetchConnections: vi.fn(),
  fetchLLMConfig: vi.fn(),
}));

vi.mock("@/lib/toast", () => ({
  publishToast: vi.fn(),
}));

vi.mock("@/lib/api-keys", () => ({
  getLLMApiKey: vi.fn().mockReturnValue(null),
  setLLMApiKey: vi.fn(),
  clearLLMApiKey: vi.fn(),
}));

// Мокаем next/link
vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    className,
  }: {
    href: string;
    children: React.ReactNode;
    className?: string;
  }) => (
    <a href={href} className={className}>
      {children}
    </a>
  ),
}));

// Мокаем дочерние компоненты настроек — упрощаем для интеграционного теста страницы
vi.mock("@/components/settings/MCPConnectionList", () => ({
  MCPConnectionList: ({
    initialConnections,
  }: {
    initialConnections: { id: string; name: string }[];
  }) => (
    <div data-testid="mcp-list">
      {initialConnections.map((c) => (
        <div key={c.id} data-testid="mcp-conn-row">
          {c.name}
        </div>
      ))}
    </div>
  ),
}));

vi.mock("@/components/settings/LLMConfigForm", () => ({
  LLMConfigForm: ({
    initial,
  }: {
    initial: { model: string } | null;
  }) => (
    <div data-testid="llm-form">
      {initial ? (
        <span data-testid="llm-model">{initial.model}</span>
      ) : (
        <span data-testid="llm-empty">LLM не настроен</span>
      )}
    </div>
  ),
}));

import SettingsPage from "@/app/settings/page";
import { fetchConnections, fetchLLMConfig } from "@/lib/api";
import type { MCPConnection, LLMConfigResponse } from "@/lib/types";

const makeConn = (id: string, name: string): MCPConnection => ({
  id,
  name,
  endpoint: `http://localhost:${6000 + parseInt(id)}/mcp`,
  channel: null,
  anon_enabled: false,
});

describe("SettingsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("отображает 2 подключения из fetchConnections, LLM форма с null", async () => {
    const conns = [makeConn("1", "Транзит"), makeConn("2", "Второй стенд")];
    vi.mocked(fetchConnections).mockResolvedValue(conns);
    vi.mocked(fetchLLMConfig).mockResolvedValue(null);

    await act(async () => {
      render(<SettingsPage />);
    });

    await waitFor(() => {
      expect(screen.getByTestId("mcp-list")).toBeInTheDocument();
    });

    const rows = screen.getAllByTestId("mcp-conn-row");
    expect(rows).toHaveLength(2);
    expect(rows[0]).toHaveTextContent("Транзит");
    expect(rows[1]).toHaveTextContent("Второй стенд");

    // LLM форма показывает null state
    expect(screen.getByTestId("llm-empty")).toBeInTheDocument();
  });

  it("отображает LLM конфиг если fetchLLMConfig возвращает данные", async () => {
    vi.mocked(fetchConnections).mockResolvedValue([]);
    const llm: LLMConfigResponse = {
      id: "default",
      endpoint: "http://localhost:1234/v1",
      model: "gpt-4o-mini",
      temperature: 0.3,
    };
    vi.mocked(fetchLLMConfig).mockResolvedValue(llm);

    await act(async () => {
      render(<SettingsPage />);
    });

    await waitFor(() => {
      expect(screen.getByTestId("llm-model")).toHaveTextContent("gpt-4o-mini");
    });
  });

  it("показывает ошибку backend если оба запроса падают", async () => {
    vi.mocked(fetchConnections).mockRejectedValue(new Error("network"));
    vi.mocked(fetchLLMConfig).mockRejectedValue(new Error("network"));

    await act(async () => {
      render(<SettingsPage />);
    });

    await waitFor(() => {
      expect(
        screen.getByText(/Backend недоступен/i),
      ).toBeInTheDocument();
    });
  });

  it("не содержит текст-заглушку про Phase 2", async () => {
    vi.mocked(fetchConnections).mockResolvedValue([]);
    vi.mocked(fetchLLMConfig).mockResolvedValue(null);

    await act(async () => {
      render(<SettingsPage />);
    });

    await waitFor(() => {
      expect(screen.getByTestId("mcp-list")).toBeInTheDocument();
    });

    expect(
      screen.queryByText(/следующей итерации/i),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(/Phase 2/i),
    ).not.toBeInTheDocument();
  });

  it("показывает загрузку сначала, потом контент", async () => {
    let resolveConns!: (v: MCPConnection[]) => void;
    const connsPromise = new Promise<MCPConnection[]>((r) => { resolveConns = r; });
    vi.mocked(fetchConnections).mockReturnValue(connsPromise);
    vi.mocked(fetchLLMConfig).mockResolvedValue(null);

    render(<SettingsPage />);

    // Сначала загрузка
    expect(screen.getByText("Загрузка...")).toBeInTheDocument();

    // Затем контент
    await act(async () => {
      resolveConns([]);
    });

    await waitFor(() => {
      expect(screen.queryByText("Загрузка...")).not.toBeInTheDocument();
      expect(screen.getByTestId("mcp-list")).toBeInTheDocument();
    });
  });
});
