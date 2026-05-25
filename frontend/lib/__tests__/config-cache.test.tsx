/**
 * Тесты ConfigCacheProvider — PERF-3 (M-K0.3).
 *
 * Контракт:
 * 1. Без провайдера useConfigCache() работает в fallback — каждый вызов = fetch.
 * 2. С провайдером первый вызов делает fetch, последующие — из кэша.
 * 3. invalidate сбрасывает кэш — следующий вызов снова делает fetch.
 * 4. Concurrent requests коалесцируются в один in-flight fetch.
 */

import { renderHook, act, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import type { ReactNode } from "react";

import { ConfigCacheProvider, useConfigCache } from "@/lib/config-cache";

vi.mock("@/lib/api", () => ({
  fetchLLMConfig: vi.fn(),
  fetchConnections: vi.fn(),
}));

import { fetchConnections, fetchLLMConfig } from "@/lib/api";

const llmConfigMock = {
  endpoint: "http://llm.test",
  model: "test-model",
  temperature: 0.3,
  max_tokens: 4096,
  has_env_api_key: false,
};

const connectionsMock = [
  { id: "ch1", name: "Test", endpoint: "http://mcp.test/mcp", anon_enabled: false },
];

beforeEach(() => {
  vi.mocked(fetchLLMConfig).mockReset();
  vi.mocked(fetchConnections).mockReset();
  vi.mocked(fetchLLMConfig).mockResolvedValue(llmConfigMock);
  vi.mocked(fetchConnections).mockResolvedValue(connectionsMock);
});

function withProvider(children: ReactNode) {
  return <ConfigCacheProvider>{children}</ConfigCacheProvider>;
}

describe("ConfigCacheProvider — caching", () => {
  it("первый get делает fetch, второй берёт из кэша", async () => {
    const { result } = renderHook(() => useConfigCache(), {
      wrapper: ({ children }) => withProvider(children),
    });

    const first = await result.current.getLLMConfig();
    const second = await result.current.getLLMConfig();
    const third = await result.current.getLLMConfig();

    expect(first).toEqual(llmConfigMock);
    expect(second).toEqual(llmConfigMock);
    expect(third).toEqual(llmConfigMock);
    expect(fetchLLMConfig).toHaveBeenCalledTimes(1);
  });

  it("getConnections кэшируется отдельно от getLLMConfig", async () => {
    const { result } = renderHook(() => useConfigCache(), {
      wrapper: ({ children }) => withProvider(children),
    });

    await result.current.getLLMConfig();
    await result.current.getConnections();
    await result.current.getLLMConfig();
    await result.current.getConnections();

    expect(fetchLLMConfig).toHaveBeenCalledTimes(1);
    expect(fetchConnections).toHaveBeenCalledTimes(1);
  });

  it("invalidateLLMConfig сбрасывает только LLM кэш", async () => {
    const { result } = renderHook(() => useConfigCache(), {
      wrapper: ({ children }) => withProvider(children),
    });

    await result.current.getLLMConfig();
    await result.current.getConnections();

    act(() => {
      result.current.invalidateLLMConfig();
    });

    await result.current.getLLMConfig();
    await result.current.getConnections();

    expect(fetchLLMConfig).toHaveBeenCalledTimes(2);
    expect(fetchConnections).toHaveBeenCalledTimes(1);
  });

  it("invalidateConnections сбрасывает только connections кэш", async () => {
    const { result } = renderHook(() => useConfigCache(), {
      wrapper: ({ children }) => withProvider(children),
    });

    await result.current.getLLMConfig();
    await result.current.getConnections();

    act(() => {
      result.current.invalidateConnections();
    });

    await result.current.getLLMConfig();
    await result.current.getConnections();

    expect(fetchLLMConfig).toHaveBeenCalledTimes(1);
    expect(fetchConnections).toHaveBeenCalledTimes(2);
  });

  it("concurrent get'ы коалесцируются в один fetch (request coalescing)", async () => {
    // Делаем fetch медленным чтобы concurrent calls точно успели запуститься.
    let resolveFn: (value: typeof llmConfigMock) => void = () => undefined;
    vi.mocked(fetchLLMConfig).mockReturnValue(
      new Promise<typeof llmConfigMock>((resolve) => {
        resolveFn = resolve;
      }),
    );

    const { result } = renderHook(() => useConfigCache(), {
      wrapper: ({ children }) => withProvider(children),
    });

    const p1 = result.current.getLLMConfig();
    const p2 = result.current.getLLMConfig();
    const p3 = result.current.getLLMConfig();

    resolveFn(llmConfigMock);
    await waitFor(async () => {
      const all = await Promise.all([p1, p2, p3]);
      expect(all[0]).toEqual(llmConfigMock);
    });

    // Все три await'а закрылись одним fetch'ем.
    expect(fetchLLMConfig).toHaveBeenCalledTimes(1);
  });
});

describe("useConfigCache — fallback без провайдера", () => {
  it("без провайдера каждый getLLMConfig делает fetch (legacy поведение)", async () => {
    const { result } = renderHook(() => useConfigCache());

    await result.current.getLLMConfig();
    await result.current.getLLMConfig();
    await result.current.getLLMConfig();

    expect(fetchLLMConfig).toHaveBeenCalledTimes(3);
  });

  it("без провайдера invalidate — no-op (не падает)", () => {
    const { result } = renderHook(() => useConfigCache());

    expect(() => {
      result.current.invalidateLLMConfig();
      result.current.invalidateConnections();
    }).not.toThrow();
  });
});
