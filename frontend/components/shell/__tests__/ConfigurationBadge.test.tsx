import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

// Dropdown мокаем passthrough-дивами: контент рендерится всегда (как в TypicalSelector.test).
vi.mock("@/components/ui/dropdown-menu", () => ({
  DropdownMenu: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  DropdownMenuTrigger: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  DropdownMenuContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  DropdownMenuItem: ({
    children,
    onSelect,
    ...rest
  }: {
    children: React.ReactNode;
    onSelect?: (e: Event) => void;
    [k: string]: unknown;
  }) => (
    <div {...rest} onClick={() => onSelect && onSelect(new Event("select"))}>
      {children}
    </div>
  ),
  DropdownMenuLabel: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  DropdownMenuSeparator: () => <hr />,
}));

vi.mock("@/lib/api", () => ({ fetchTypicalConfigurations: vi.fn() }));
vi.mock("@/lib/storage", () => ({
  getActiveTypicalChannelId: vi.fn(() => null),
  setActiveTypicalChannelId: vi.fn(),
}));

import { ConfigurationBadge } from "@/components/shell/ConfigurationBadge";
import { fetchTypicalConfigurations } from "@/lib/api";
import { getActiveTypicalChannelId, setActiveTypicalChannelId } from "@/lib/storage";

const mockFetch = fetchTypicalConfigurations as ReturnType<typeof vi.fn>;
const mockGet = getActiveTypicalChannelId as ReturnType<typeof vi.fn>;
const mockSet = setActiveTypicalChannelId as ReturnType<typeof vi.fn>;

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const base = { id: "c1", name: "B", endpoint: "http://x/mcp" } as any;

function typ(channel_id: string, config_kind: string, config_version = "x") {
  return {
    channel_id,
    config_kind,
    config_version,
    display_name: channel_id,
    status: "graph_built",
    indexed_at: null,
    source_path: null,
    node_counts: {},
    card_counts: {},
    total_nodes: 0,
    total_cards: 0,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  mockGet.mockReturnValue(null);
  mockFetch.mockResolvedValue({ configurations: [], total: 0 });
});

describe("ConfigurationBadge — состояния (регресс)", () => {
  it("показывает detected-конфу с пометкой (авто)", () => {
    render(
      <ConfigurationBadge
        connection={{ ...base, configuration: "КА 2.5", configuration_source: "auto" }}
        onOverride={vi.fn()}
      />,
    );
    expect(screen.getAllByText(/КА 2\.5/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/авто/i)).toBeInTheDocument();
  });

  it("ambiguous → data-state ambiguous", () => {
    render(
      <ConfigurationBadge
        connection={{ ...base, configuration: "КА 2.5", configuration_source: "ambiguous" }}
        onOverride={vi.fn()}
      />,
    );
    expect(screen.getByTestId("config-badge")).toHaveAttribute("data-state", "ambiguous");
  });

  it("failed → data-state failed", () => {
    render(
      <ConfigurationBadge
        connection={{ ...base, configuration: null, configuration_source: "failed" }}
        onOverride={vi.fn()}
      />,
    );
    expect(screen.getByTestId("config-badge")).toHaveAttribute("data-state", "failed");
  });

  it("custom → Самописная", () => {
    render(
      <ConfigurationBadge
        connection={{ ...base, configuration: "Самописная", configuration_source: "custom" }}
        onOverride={vi.fn()}
      />,
    );
    expect(screen.getAllByText(/Самописная/).length).toBeGreaterThanOrEqual(1);
  });

  it("none → data-state none", () => {
    render(
      <ConfigurationBadge
        connection={{ ...base, configuration: null, configuration_source: null }}
        onOverride={vi.fn()}
      />,
    );
    expect(screen.getByTestId("config-badge")).toHaveAttribute("data-state", "none");
  });

  it("confirmed → data-state confirmed", () => {
    render(
      <ConfigurationBadge
        connection={{ ...base, configuration: "УТ 11.5", configuration_source: "confirmed" }}
        onOverride={vi.fn()}
      />,
    );
    expect(screen.getByTestId("config-badge")).toHaveAttribute("data-state", "confirmed");
  });
});

describe("ConfigurationBadge — авто-привязка типовой", () => {
  it("конфа КА + загружена типовая KA_2 → setActiveTypicalChannelId(KA)", async () => {
    mockFetch.mockResolvedValue({ configurations: [typ("_ka2_25", "KA_2")], total: 1 });
    render(
      <ConfigurationBadge
        connection={{ ...base, configuration: "КА 2.5", configuration_source: "auto" }}
        onOverride={vi.fn()}
      />,
    );
    await waitFor(() => expect(mockSet).toHaveBeenCalledWith("_ka2_25"));
  });

  it("конфа КА, но KA_2 не загружена → типовую не трогаем + подсказка", async () => {
    mockFetch.mockResolvedValue({ configurations: [typ("_ut115", "UT_115")], total: 1 });
    render(
      <ConfigurationBadge
        connection={{ ...base, configuration: "КА 2.5", configuration_source: "auto" }}
        onOverride={vi.fn()}
      />,
    );
    await waitFor(() =>
      expect(screen.getByTestId("typical-not-loaded-hint")).toBeInTheDocument(),
    );
    expect(mockSet).not.toHaveBeenCalled();
  });
});

describe("ConfigurationBadge — сравнить с другой типовой", () => {
  it("клик по типовой в дропдауне → setActiveTypicalChannelId(её id)", async () => {
    mockFetch.mockResolvedValue({
      configurations: [typ("_ka2_25", "KA_2"), typ("_erp25", "ERP_25")],
      total: 2,
    });
    render(
      <ConfigurationBadge
        connection={{ ...base, configuration: "КА 2.5", configuration_source: "auto" }}
        onOverride={vi.fn()}
      />,
    );
    await waitFor(() =>
      expect(screen.getByTestId("typical-option-_erp25")).toBeInTheDocument(),
    );
    mockSet.mockClear(); // отбросить вызов авто-привязки
    fireEvent.click(screen.getByTestId("typical-option-_erp25"));
    expect(mockSet).toHaveBeenCalledWith("_erp25");
  });
});
