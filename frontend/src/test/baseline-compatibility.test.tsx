import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { App } from "../App";
import { governanceApiMode } from "../api/capabilities";
import responses from "./api-responses.json";

const clients: QueryClient[] = [];
const fixtures = responses as Record<string, unknown>;
const fetchMock = vi.fn<typeof fetch>();
function show() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity } },
  });
  clients.push(client);
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
beforeEach(() => {
  vi.stubEnv("VITE_GOVERNANCE_API_MODE", "baseline-v1");
  fetchMock.mockReset();
  fetchMock.mockImplementation(async (input) => {
    const url = new URL(String(input), "http://127.0.0.1");
    // Deployed V1 rejects unknown query parameters; it has no catalogue fields.
    if (
      url.searchParams.has("catalog") ||
      url.searchParams.has("policy_version")
    )
      return new Response("unsupported query", { status: 422 });
    const payload = structuredClone(fixtures[url.pathname]) as
      | { metadata: Record<string, unknown>; data: Record<string, unknown> }
      | undefined;
    if (!payload) return new Response("not found", { status: 404 });
    for (const key of ["snapshot_id", "policy_version", "profile", "generator"])
      delete payload.metadata[key];
    if (url.pathname === "/api/v1/summary")
      for (const key of [
        "current",
        "versions",
        "current_run",
        "journal",
        "proposal",
        "environment_policies",
      ])
        delete payload.data[key];
    return new Response(JSON.stringify(payload), { status: 200 });
  });
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => {
  clients.splice(0).forEach((client) => client.clear());
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

it("renders all six pages from the V1 API without pretending it has current/history metadata", async () => {
  const user = userEvent.setup();
  show();
  await screen.findByRole("heading", { name: "Account compliance posture" });
  expect(
    screen.getByText(/BASELINE EVALUATION · Policy revision 1.0.0/),
  ).toBeInTheDocument();
  expect(
    screen.getByText("V1 backend compatibility mode."),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("combobox", { name: "Baseline evaluation" }),
  ).toBeDisabled();
  expect(screen.queryByText(/CURRENT GOVERNANCE ·/)).not.toBeInTheDocument();
  for (const [name, title] of [
    ["Accounts", "Account inventory"],
    ["Compliance", "Policy compliance"],
    ["Deployments", "Governance deployments"],
    ["Configuration Drift", "Configuration drift"],
    ["Governance Exceptions", "Governance exceptions"],
    ["Overview", "Governance overview"],
  ]) {
    await user.click(screen.getByRole("link", { name: new RegExp(name) }));
    await screen.findByRole("heading", { name: title });
    expect(screen.getByText("SIMULATED DATA")).toBeInTheDocument();
  }
  for (const [input] of fetchMock.mock.calls) {
    const url = new URL(String(input), "http://127.0.0.1");
    expect(url.searchParams.has("catalog")).toBe(false);
    expect(url.searchParams.has("policy_version")).toBe(false);
    expect(url.searchParams.get("at")).toBe("2026-10-31T12:00:00Z");
  }
});

it("keeps authorization failures visible without falling back to another data source", async () => {
  fetchMock.mockImplementation(
    async () => new Response("unauthorized", { status: 401 }),
  );
  show();
  await screen.findByRole("heading", {
    name: "Baseline evaluation could not be loaded",
  });
  expect(
    screen.queryByRole("heading", { name: "Account compliance posture" }),
  ).not.toBeInTheDocument();
});

it("catalog mode still fails closed when its server cannot resolve current governance", async () => {
  vi.stubEnv("VITE_GOVERNANCE_API_MODE", "catalog");
  show();
  await screen.findByRole("heading", {
    name: "Current governance could not be resolved",
  });
  expect(
    screen.queryByRole("heading", { name: "Account compliance posture" }),
  ).not.toBeInTheDocument();
});

it("rejects unsupported compatibility modes", () => {
  vi.stubEnv("VITE_GOVERNANCE_API_MODE", "unsupported");
  expect(governanceApiMode).toThrow(
    "Unsupported governance API compatibility mode",
  );
});
