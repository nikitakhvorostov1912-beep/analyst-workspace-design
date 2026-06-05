/**
 * Tests for updateConnectionConfiguration (Phase 6, Task 6.1).
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { updateConnectionConfiguration } from "@/lib/api";

afterEach(() => vi.restoreAllMocks());

describe("updateConnectionConfiguration", () => {
  it("PUT /connections/{id} с configuration + source", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        id: "c1",
        configuration: "КА 2.5",
        configuration_source: "manual",
      }),
    });
    vi.stubGlobal("fetch", fetchMock);
    const res = await updateConnectionConfiguration("c1", "КА 2.5", "manual");
    expect(res.configuration).toBe("КА 2.5");
    const [, opts] = fetchMock.mock.calls[0];
    expect(opts.method).toBe("PUT");
    expect(JSON.parse(opts.body as string)).toMatchObject({
      configuration: "КА 2.5",
      configuration_source: "manual",
    });
  });

  it("бросает ошибку при не-ok ответе", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 404 }));
    await expect(
      updateConnectionConfiguration("c1", "УТ 11.5", "confirmed"),
    ).rejects.toThrow("404");
  });
});
