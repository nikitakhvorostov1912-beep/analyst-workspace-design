import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ITSSourcesCard } from "../ITSSourcesCard";
import { CardRenderer } from "../CardRenderer";
import type { ITSSourcesCardPayload } from "@/lib/types";

const payload: ITSSourcesCardPayload = {
  total: 2,
  sources: [
    {
      title: "Практическое пособие разработчика",
      url: "https://its.1c.ru/db/pubdevguide83#content:461:hdoc",
      doc_id: "its-pubdevguide83-461-hdoc",
    },
    { title: "Каталог без якоря", url: "https://its.1c.ru/db/bsp321doc", doc_id: null },
  ],
};

const fivePayload: ITSSourcesCardPayload = {
  total: 5,
  sources: [1, 2, 3, 4, 5].map((n) => ({
    title: `Статья ${n}`,
    url: `https://its.1c.ru/db/x${n}#content:${n}:hdoc`,
    doc_id: `its-x${n}-${n}-hdoc`,
  })),
};

describe("ITSSourcesCard", () => {
  it("рендерит ссылки на its.1c.ru (открываются в новой вкладке)", () => {
    render(<ITSSourcesCard payload={payload} />);
    const link = screen.getByRole("link", { name: /Практическое пособие/ });
    expect(link).toHaveAttribute("href", payload.sources[0].url);
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", expect.stringContaining("noopener"));
  });

  it("кнопка «Разобрать» только у источника с doc_id, вызывает onAnalyze", () => {
    const onAnalyze = vi.fn();
    render(<ITSSourcesCard payload={payload} onAnalyze={onAnalyze} />);
    const buttons = screen.getAllByRole("button", { name: /Разобрать/ });
    expect(buttons).toHaveLength(1); // только у первого источника (doc_id есть)
    fireEvent.click(buttons[0]);
    expect(onAnalyze).toHaveBeenCalledWith(payload.sources[0]);
  });

  it("без onAnalyze кнопок нет (read-only история)", () => {
    render(<ITSSourcesCard payload={payload} />);
    expect(screen.queryByRole("button", { name: /Разобрать/ })).toBeNull();
  });

  it("показывает 3 источника + кнопку «показать ещё N»", () => {
    render(<ITSSourcesCard payload={fivePayload} />);
    expect(screen.getAllByRole("link")).toHaveLength(3);
    fireEvent.click(screen.getByRole("button", { name: /показать ещё 2/ }));
    expect(screen.getAllByRole("link")).toHaveLength(5);
  });

  it("при ≤3 источниках кнопки свёртки нет", () => {
    render(<ITSSourcesCard payload={payload} />); // 2 источника
    expect(screen.queryByRole("button", { name: /показать ещё/ })).toBeNull();
  });
});

describe("CardRenderer · its_sources", () => {
  it("прокидывает sendMessage → onAnalyze с шаблоном fetch_its", () => {
    const sendMessage = vi.fn();
    render(
      <CardRenderer
        card={{ type: "its_sources", payload }}
        sendMessage={sendMessage}
      />,
    );
    fireEvent.click(screen.getAllByRole("button", { name: /Разобрать/ })[0]);
    expect(sendMessage).toHaveBeenCalledWith(
      expect.stringContaining('fetch_its(id="its-pubdevguide83-461-hdoc")'),
    );
  });
});
