import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

let _onOpenChange: ((v: boolean) => void) | undefined;

vi.mock("@/components/ui/dropdown-menu", () => ({
  DropdownMenu: ({
    children,
    open,
    onOpenChange,
  }: {
    children: React.ReactNode;
    open?: boolean;
    onOpenChange?: (v: boolean) => void;
  }) => {
    _onOpenChange = onOpenChange;
    return (
      <div data-testid="ts-dropdown-root" data-open={String(open)}>
        {children}
      </div>
    );
  },
  DropdownMenuTrigger: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="ts-trigger" onClick={() => _onOpenChange?.(true)}>
      {children}
    </div>
  ),
  DropdownMenuContent: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="ts-content">{children}</div>
  ),
  DropdownMenuItem: ({
    children,
    onSelect,
    className,
  }: {
    children: React.ReactNode;
    onSelect?: (e: Event) => void;
    className?: string;
  }) => (
    <div
      data-testid="ts-item"
      className={className}
      onClick={() => onSelect && onSelect(new Event("select"))}
    >
      {children}
    </div>
  ),
  DropdownMenuLabel: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="ts-label">{children}</div>
  ),
  DropdownMenuSeparator: () => <hr data-testid="ts-separator" />,
}));

vi.mock("@/lib/api", () => ({
  fetchTypicalConfigurations: vi.fn(),
}));

vi.mock("@/lib/storage", () => ({
  getActiveTypicalChannelId: vi.fn(() => null),
  setActiveTypicalChannelId: vi.fn(),
}));

import { TypicalSelector } from "../../shell/TypicalSelector";
import { fetchTypicalConfigurations } from "@/lib/api";
import {
  getActiveTypicalChannelId,
  setActiveTypicalChannelId,
} from "@/lib/storage";

const mockFetch = fetchTypicalConfigurations as ReturnType<typeof vi.fn>;
const mockGet = getActiveTypicalChannelId as ReturnType<typeof vi.fn>;
const mockSet = setActiveTypicalChannelId as ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.clearAllMocks();
  mockGet.mockReturnValue(null);
});

describe("TypicalSelector", () => {
  it("показывает empty state когда нет загруженных типовых", async () => {
    mockFetch.mockResolvedValue({ configurations: [], total: 0 });

    render(<TypicalSelector />);

    await waitFor(() => {
      expect(
        screen.getByTestId("typical-selector-empty"),
      ).toBeInTheDocument();
    });
    expect(screen.getByText("не загружена")).toBeInTheDocument();
  });

  it("показывает error state при ошибке fetch", async () => {
    mockFetch.mockRejectedValue(new Error("Network down"));

    render(<TypicalSelector />);

    await waitFor(() => {
      expect(
        screen.getByTestId("typical-selector-error"),
      ).toBeInTheDocument();
    });
  });

  it("рендерит кнопку с прочерком когда типовая не выбрана", async () => {
    mockFetch.mockResolvedValue({
      configurations: [
        {
          channel_id: "_bp30_138_24",
          config_kind: "BP_30",
          config_version: "3.0.138.24",
          display_name: "БП 3.0.138.24",
          status: "graph_built",
          indexed_at: null,
          source_path: null,
          node_counts: { MetadataObject: 11713 },
          card_counts: { generated: 10 },
          total_nodes: 60326,
          total_cards: 10,
        },
      ],
      total: 1,
    });

    render(<TypicalSelector />);

    await waitFor(() => {
      expect(
        screen.getByTestId("typical-selector-button"),
      ).toBeInTheDocument();
    });
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("показывает короткий kind label когда типовая активна", async () => {
    mockGet.mockReturnValue("_bp30_138_24");
    mockFetch.mockResolvedValue({
      configurations: [
        {
          channel_id: "_bp30_138_24",
          config_kind: "BP_30",
          config_version: "3.0.138.24",
          display_name: "БП 3.0.138.24",
          status: "graph_built",
          indexed_at: null,
          source_path: null,
          node_counts: {},
          card_counts: {},
          total_nodes: 60326,
          total_cards: 10,
        },
      ],
      total: 1,
    });

    render(<TypicalSelector />);

    await waitFor(() => {
      // «БП 3.0» появляется в 2 местах: кнопка-trigger + dropdown item.
      // Проверяем что лейбл встречается хотя бы один раз.
      expect(screen.getAllByText("БП 3.0").length).toBeGreaterThanOrEqual(1);
    });
  });

  it("показывает несколько типовых в dropdown с счётчиками", async () => {
    mockFetch.mockResolvedValue({
      configurations: [
        {
          channel_id: "_bp30_138_24",
          config_kind: "BP_30",
          config_version: "3.0.138.24",
          display_name: "БП",
          status: "graph_built",
          indexed_at: null,
          source_path: null,
          node_counts: {},
          card_counts: {},
          total_nodes: 60326,
          total_cards: 10,
        },
        {
          channel_id: "_ka2_25_92",
          config_kind: "KA_2",
          config_version: "2.5.25.92",
          display_name: "КА",
          status: "parsed",
          indexed_at: null,
          source_path: null,
          node_counts: {},
          card_counts: {},
          total_nodes: 0,
          total_cards: 0,
        },
      ],
      total: 2,
    });

    render(<TypicalSelector />);

    await waitFor(() => {
      expect(screen.getByText("БП 3.0")).toBeInTheDocument();
      expect(screen.getByText("КА 2")).toBeInTheDocument();
    });
    // Версии видны
    expect(screen.getByText("3.0.138.24")).toBeInTheDocument();
    expect(screen.getByText("2.5.25.92")).toBeInTheDocument();
    // Бейдж статуса для не-graph_built
    expect(screen.getByText("parsed")).toBeInTheDocument();
  });

  it("вызывает setActiveTypicalChannelId и onChange при выборе", async () => {
    const onChange = vi.fn();
    mockFetch.mockResolvedValue({
      configurations: [
        {
          channel_id: "_bp30_138_24",
          config_kind: "BP_30",
          config_version: "3.0.138.24",
          display_name: "БП",
          status: "graph_built",
          indexed_at: null,
          source_path: null,
          node_counts: {},
          card_counts: {},
          total_nodes: 60326,
          total_cards: 10,
        },
      ],
      total: 1,
    });

    render(<TypicalSelector onChange={onChange} />);

    await waitFor(() => {
      expect(screen.getAllByTestId("ts-item").length).toBeGreaterThan(0);
    });

    // Первый item = "Без типовой", второй = БП
    const items = screen.getAllByTestId("ts-item");
    fireEvent.click(items[1]);

    expect(mockSet).toHaveBeenCalledWith("_bp30_138_24");
    expect(onChange).toHaveBeenCalledWith("_bp30_138_24");
  });

  it("очищает выбор при клике «Без типовой»", async () => {
    mockGet.mockReturnValue("_bp30_138_24");
    const onChange = vi.fn();
    mockFetch.mockResolvedValue({
      configurations: [
        {
          channel_id: "_bp30_138_24",
          config_kind: "BP_30",
          config_version: "3.0.138.24",
          display_name: "БП",
          status: "graph_built",
          indexed_at: null,
          source_path: null,
          node_counts: {},
          card_counts: {},
          total_nodes: 60326,
          total_cards: 10,
        },
      ],
      total: 1,
    });

    render(<TypicalSelector onChange={onChange} />);

    await waitFor(() => {
      expect(screen.getAllByTestId("ts-item").length).toBeGreaterThan(0);
    });

    const items = screen.getAllByTestId("ts-item");
    fireEvent.click(items[0]); // «Без типовой»

    expect(mockSet).toHaveBeenCalledWith(null);
    expect(onChange).toHaveBeenCalledWith(null);
  });
});
