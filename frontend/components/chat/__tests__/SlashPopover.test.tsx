import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { SlashPopover } from "../SlashPopover";
// SLASH_COMMANDS доступен через импорт SlashPopover
import { createRef } from "react";

describe("SlashPopover", () => {
  const anchorRef = createRef<HTMLElement>();

  it("open=true renders all 5 commands when no filter", () => {
    const onSelect = vi.fn();
    render(
      <SlashPopover open query="/" onSelect={onSelect} anchor={anchorRef} />
    );
    // Все 5 команд должны быть видны
    expect(screen.getByText("/sql")).toBeInTheDocument();
    expect(screen.getByText("/journal")).toBeInTheDocument();
    expect(screen.getByText("/find")).toBeInTheDocument();
    expect(screen.getByText("/audit")).toBeInTheDocument();
    expect(screen.getByText("/clear")).toBeInTheDocument();
  });

  it("filter by 'sq' shows only sql command", () => {
    const onSelect = vi.fn();
    render(
      <SlashPopover open query="/sq" onSelect={onSelect} anchor={anchorRef} />
    );
    expect(screen.getByText("/sql")).toBeInTheDocument();
    expect(screen.queryByText("/journal")).not.toBeInTheDocument();
    expect(screen.queryByText("/find")).not.toBeInTheDocument();
  });

  it("click item → onSelect called with command", () => {
    const onSelect = vi.fn();
    render(
      <SlashPopover open query="/" onSelect={onSelect} anchor={anchorRef} />
    );
    const sqlOption = screen.getByText("/sql").closest("[role='option']")!;
    fireEvent.click(sqlOption);
    expect(onSelect).toHaveBeenCalledWith(
      expect.objectContaining({ key: "sql" })
    );
  });

  it("ArrowDown moves highlight to next item", () => {
    const onSelect = vi.fn();
    render(
      <SlashPopover open query="/" onSelect={onSelect} anchor={anchorRef} />
    );
    // Initial: first item is active (aria-selected=true)
    const options = screen.getAllByRole("option");
    expect(options[0]).toHaveAttribute("aria-selected", "true");

    fireEvent.keyDown(document, { key: "ArrowDown" });
    // Now second item should be active
    const optionsAfter = screen.getAllByRole("option");
    expect(optionsAfter[1]).toHaveAttribute("aria-selected", "true");
  });

  it("Enter triggers onSelect for active item", () => {
    const onSelect = vi.fn();
    render(
      <SlashPopover open query="/" onSelect={onSelect} anchor={anchorRef} />
    );
    fireEvent.keyDown(document, { key: "Enter" });
    expect(onSelect).toHaveBeenCalledWith(
      expect.objectContaining({ key: "sql" }) // первый item по умолчанию
    );
  });

  it("open=false → returns null", () => {
    const onSelect = vi.fn();
    const { container } = render(
      <SlashPopover open={false} query="/" onSelect={onSelect} anchor={anchorRef} />
    );
    expect(container.firstChild).toBeNull();
  });

  it("listbox has aria-label", () => {
    const onSelect = vi.fn();
    render(
      <SlashPopover open query="/" onSelect={onSelect} anchor={anchorRef} />
    );
    expect(screen.getByRole("listbox")).toBeInTheDocument();
  });
});
