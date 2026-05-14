import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

// Мокаем DropdownMenu для обхода Portal-рендеринга в jsdom.
// DropdownMenu хранит onOpenChange в ref чтобы Trigger мог его вызвать.
let _onOpenChange: ((v: boolean) => void) | undefined;

vi.mock("@/components/ui/dropdown-menu", () => ({
  DropdownMenu: ({ children, open, onOpenChange }: {
    children: React.ReactNode;
    open?: boolean;
    onOpenChange?: (v: boolean) => void;
  }) => {
    _onOpenChange = onOpenChange;
    return (
      <div data-testid="dropdown-root" data-open={String(open)}>
        {children}
      </div>
    );
  },
  DropdownMenuTrigger: ({ children }: {
    children: React.ReactNode;
    asChild?: boolean;
  }) => (
    <div
      data-testid="dropdown-trigger"
      onClick={() => _onOpenChange?.(true)}
    >
      {children}
    </div>
  ),
  DropdownMenuContent: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="dropdown-content">{children}</div>
  ),
  DropdownMenuItem: ({ children, onSelect, className }: {
    children: React.ReactNode;
    onSelect?: (e: Event) => void;
    className?: string;
  }) => (
    <div
      data-testid="dropdown-item"
      className={className}
      onClick={() => onSelect && onSelect(new Event("select"))}
    >
      {children}
    </div>
  ),
  DropdownMenuLabel: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="dropdown-label">{children}</div>
  ),
  DropdownMenuSeparator: () => <hr data-testid="dropdown-separator" />,
}));

// Мокаем next/link как простой <a>
vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    className,
    onClick,
  }: {
    href: string;
    children: React.ReactNode;
    className?: string;
    onClick?: () => void;
  }) => (
    <a href={href} className={className} onClick={onClick}>
      {children}
    </a>
  ),
}));

// Мокаем api и storage
vi.mock("@/lib/api", () => ({
  fetchConnections: vi.fn(),
  pingConnection: vi.fn(),
}));

vi.mock("@/lib/storage", () => ({
  getMCPConnections: vi.fn(),
  setActiveChannelId: vi.fn(),
  syncMCPConnections: vi.fn(),
}));

import { ChannelSelector } from "../../shell/ChannelSelector";
import { fetchConnections, pingConnection } from "@/lib/api";
import { getMCPConnections, setMCPConnections } from "@/lib/storage";
import type { MCPConnection } from "@/lib/types";

const makeConn = (id: string, name: string): MCPConnection => ({
  id,
  name,
  endpoint: `http://localhost:${6000 + parseInt(id)}/mcp`,
  channel: null,
  anon_enabled: false,
});

describe("ChannelSelector", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("показывает 'Подключения не настроены' если connections пусты", async () => {
    vi.mocked(fetchConnections).mockResolvedValue([]);
    vi.mocked(getMCPConnections as ReturnType<typeof vi.fn>).mockReturnValue([]);

    await act(async () => {
      render(<ChannelSelector activeId={null} onChange={vi.fn()} />);
    });

    expect(screen.getByText("Подключения не настроены")).toBeInTheDocument();
  });

  it("рендерит 2 подключения после загрузки", async () => {
    const conns = [makeConn("1", "Транзит"), makeConn("2", "Второй стенд")];
    vi.mocked(fetchConnections).mockResolvedValue(conns);
    vi.mocked(getMCPConnections as ReturnType<typeof vi.fn>).mockReturnValue([]);

    await act(async () => {
      render(<ChannelSelector activeId={null} onChange={vi.fn()} />);
    });

    // Оба имени должны быть видны в dropdown-content (который мокнут в DOM напрямую)
    expect(screen.getByText("Транзит")).toBeInTheDocument();
    expect(screen.getByText("Второй стенд")).toBeInTheDocument();
  });

  it("вызывает onChange при клике на connection item", async () => {
    const conns = [makeConn("42", "База 42")];
    vi.mocked(fetchConnections).mockResolvedValue(conns);
    vi.mocked(getMCPConnections as ReturnType<typeof vi.fn>).mockReturnValue([]);
    vi.mocked(pingConnection).mockResolvedValue({
      mcp_version: "2025-03-26",
      tool_count: 3,
      session_id: "s1",
      duration_ms: 50,
    });

    const onChange = vi.fn();
    await act(async () => {
      render(<ChannelSelector activeId={null} onChange={onChange} />);
    });

    // Кликаем на DropdownMenuItem с именем базы
    const items = screen.getAllByTestId("dropdown-item");
    const bazaItem = items.find((el) => el.textContent?.includes("База 42"));
    expect(bazaItem).toBeTruthy();
    fireEvent.click(bazaItem!);

    expect(onChange).toHaveBeenCalledWith("42");
  });

  it("fallback на localStorage если fetchConnections выбрасывает", async () => {
    vi.mocked(fetchConnections).mockRejectedValue(new Error("network"));
    const cached = [makeConn("99", "Кеш-база")];
    vi.mocked(getMCPConnections as ReturnType<typeof vi.fn>).mockReturnValue(cached);

    await act(async () => {
      render(<ChannelSelector activeId={null} onChange={vi.fn()} />);
    });

    // Кеш-база должна быть видна из localStorage fallback
    expect(screen.getByText("Кеш-база")).toBeInTheDocument();
  });

  it("pingAll вызывает pingConnection для каждого connection при открытии", async () => {
    const conns = [makeConn("1", "A"), makeConn("2", "B")];
    vi.mocked(fetchConnections).mockResolvedValue(conns);
    vi.mocked(getMCPConnections as ReturnType<typeof vi.fn>).mockReturnValue([]);
    vi.mocked(pingConnection).mockResolvedValue({
      mcp_version: "2025-03-26",
      tool_count: 5,
      session_id: "sess",
      duration_ms: 10,
    });

    await act(async () => {
      render(<ChannelSelector activeId={null} onChange={vi.fn()} />);
    });

    // Кликаем на dropdown-trigger div — он вызывает onOpenChange(true)
    const triggerDiv = screen.getByTestId("dropdown-trigger");

    await act(async () => {
      fireEvent.click(triggerDiv);
    });

    await waitFor(() => {
      expect(pingConnection).toHaveBeenCalledTimes(2);
    });
  });
});
