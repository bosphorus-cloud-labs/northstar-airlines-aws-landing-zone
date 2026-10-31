import { afterEach, expect, it, vi } from "vitest";
import { request, REFERENCE_AT } from "../api/client";
import responses from "./api-responses.json";
afterEach(() => vi.unstubAllGlobals());
it("uses only read operations and sends no browser credentials or tokens", async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValue(
      new Response(JSON.stringify(responses["/api/v1/summary"])),
    );
  vi.stubGlobal("fetch", fetcher);
  await request("/api/v1/summary", new AbortController().signal);
  expect(fetcher).toHaveBeenCalledWith(
    expect.stringContaining("/api/v1/summary?at="),
    expect.objectContaining({
      method: "GET",
      credentials: "omit",
      headers: { Accept: "application/json" },
    }),
  );
});
it("rejects a mismatched evaluation timestamp", async () => {
  const body = structuredClone(responses["/api/v1/summary"]);
  body.metadata.evaluated_at = "2026-10-30T12:00:00Z";
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response(JSON.stringify(body))),
  );
  await expect(
    request("/api/v1/summary", new AbortController().signal),
  ).rejects.toThrow("evaluation time");
});
it("does not display raw backend error bodies", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue(
        new Response("/private/internal/path", { status: 500 }),
      ),
  );
  await expect(
    request("/api/v1/summary", new AbortController().signal),
  ).rejects.toThrow("could not complete");
});
it("handles malformed successful JSON without exposing it", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("not-json")));
  await expect(
    request("/api/v1/summary", new AbortController().signal),
  ).rejects.toThrow("unreadable response");
});
it("omits evaluation parameters from health requests", async () => {
  const fetcher = vi.fn().mockResolvedValue(
    new Response(
      JSON.stringify({
        metadata: {
          simulated: true,
          source: "northstar-synthetic-v1",
          api_version: "v1",
          evaluated_at: REFERENCE_AT,
        },
        data: { status: "ok", authentication_mode: "local-demo" },
      }),
    ),
  );
  vi.stubGlobal("fetch", fetcher);
  await request("/api/v1/health", new AbortController().signal);
  expect(fetcher.mock.calls[0][0]).toBe("/api/v1/health?");
});
