import { describe, it, expect } from "vitest";
import { parseSSEStream } from "@/lib/sse";
import type { SSEEvent } from "@/lib/types";

function streamOf(text: string): ReadableStream<Uint8Array> {
  return new ReadableStream({
    start(controller) {
      controller.enqueue(new TextEncoder().encode(text));
      controller.close();
    },
  });
}

async function collect(text: string): Promise<SSEEvent[]> {
  const out: SSEEvent[] = [];
  for await (const e of parseSSEStream(streamOf(text))) out.push(e);
  return out;
}

describe("parseSSEStream — clarify/confirm события", () => {
  it("clarify_required проходит как есть (а не «Неизвестный тип события»)", async () => {
    const sse =
      'event: clarify_required\ndata: {"clarify_id":"c1","question":"Какой период?"}\n\n';
    const events = await collect(sse);
    expect(events).toEqual([
      {
        event: "clarify_required",
        data: { clarify_id: "c1", question: "Какой период?" },
      },
    ]);
  });

  it("confirm_required проходит как есть", async () => {
    const sse =
      'event: confirm_required\ndata: {"tool_call_id":"t1","name":"execute_code","args":{},"reason":"keyword"}\n\n';
    const events = await collect(sse);
    expect(events[0]!.event).toBe("confirm_required");
  });

  it("по-настоящему неизвестное событие → error sse_parse", async () => {
    const sse = 'event: totally_unknown\ndata: {"x":1}\n\n';
    const events = await collect(sse);
    expect(events[0]!.event).toBe("error");
    // @ts-expect-error — узкое сужение для теста
    expect(events[0]!.data.code).toBe("sse_parse");
  });

  it("обычные события (delta) не сломаны", async () => {
    const sse = 'event: delta\ndata: {"content":"привет"}\n\n';
    const events = await collect(sse);
    expect(events).toEqual([{ event: "delta", data: { content: "привет" } }]);
  });
});
