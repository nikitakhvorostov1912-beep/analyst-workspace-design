/**
 * Tests for components/shell/ModeBadge (M-K1.11).
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ModeBadge } from "../ModeBadge";

describe("ModeBadge", () => {
  it("renders nothing when mode is undefined", () => {
    const { container } = render(<ModeBadge mode={undefined} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing when mode is null", () => {
    const { container } = render(<ModeBadge mode={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders MCP label for mcp_only mode", () => {
    render(<ModeBadge mode="mcp_only" />);
    const badge = screen.getByTestId("mode-badge-mcp_only");
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveTextContent("MCP");
  });

  it("renders EPF label for epf mode", () => {
    render(<ModeBadge mode="epf" />);
    const badge = screen.getByTestId("mode-badge-epf");
    expect(badge).toHaveTextContent("EPF");
    expect(badge).toHaveAttribute("title", expect.stringContaining("АналитикLite"));
  });

  it("renders CFE label for cfe mode with signal tone", () => {
    render(<ModeBadge mode="cfe" />);
    const badge = screen.getByTestId("mode-badge-cfe");
    expect(badge).toHaveTextContent("CFE");
    expect(badge).toHaveAttribute("title", expect.stringContaining("АналитикПлюс"));
  });

  it("each mode has different tooltip", () => {
    const { rerender } = render(<ModeBadge mode="mcp_only" />);
    const mcpTooltip = screen.getByTestId("mode-badge-mcp_only").getAttribute("title");

    rerender(<ModeBadge mode="cfe" />);
    const cfeTooltip = screen.getByTestId("mode-badge-cfe").getAttribute("title");

    expect(mcpTooltip).not.toBe(cfeTooltip);
  });

  it("applies className prop", () => {
    render(<ModeBadge mode="epf" className="custom-class" />);
    const badge = screen.getByTestId("mode-badge-epf");
    expect(badge.className).toContain("custom-class");
  });
});
