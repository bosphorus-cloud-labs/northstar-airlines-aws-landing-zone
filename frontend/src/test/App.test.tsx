import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import responses from "./api-responses.json";

const clients: QueryClient[] = [];
const fixtures = responses as Record<string, unknown>;
const mockFetch = vi.fn<typeof fetch>();
function respond(input: RequestInfo | URL): Response {
  const url = new URL(String(input), "http://127.0.0.1");
  const response = fixtures[url.pathname];
  return new Response(
    JSON.stringify(response ?? { error: { code: "account_not_found" } }),
    {
      status: response ? 200 : 404,
      headers: { "Content-Type": "application/json" },
    },
  );
}
function renderApp(route = "/") {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity } },
  });
  clients.push(client);
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[route]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
beforeEach(() => {
  mockFetch.mockReset();
  mockFetch.mockImplementation(async (input) => respond(input));
  vi.stubGlobal("fetch", mockFetch);
});
afterEach(() => {
  clients.splice(0).forEach((c) => c.clear());
  vi.unstubAllGlobals();
});

describe("Governance console", () => {
  it("renders API summary, environment distribution and persistent simulation context", async () => {
    renderApp();
    expect(
      await screen.findByRole("heading", {
        name: "Account compliance posture",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("SIMULATED DATA")).toBeInTheDocument();
    expect(screen.getByText("31 Oct 2026, 12:00 UTC")).toBeInTheDocument();
    expect(screen.getByText("31")).toBeInTheDocument();
    expect(
      screen.getByText("2 unknown · 2 stale accounts"),
    ).toBeInTheDocument();
    expect(screen.getByText("Production")).toBeInTheDocument();
    for (const [input] of mockFetch.mock.calls)
      expect(String(input)).toContain("at=2026-10-31T12%3A00%3A00Z");
  });

  it("navigates to every functional page without losing simulation labeling", async () => {
    const user = userEvent.setup();
    renderApp();
    await screen.findByRole("heading", { name: "Account compliance posture" });
    for (const [nav, title] of [
      ["Accounts", "Account inventory"],
      ["Compliance", "Policy compliance"],
      ["Deployments", "Deployment history"],
      ["Configuration Drift", "Configuration drift"],
      ["Governance Exceptions", "Governance exceptions"],
      ["Overview", "Governance overview"],
    ]) {
      await user.click(
        within(
          screen.getByRole("navigation", { name: "Main navigation" }),
        ).getByRole("link", { name: nav }),
      );
      expect(
        screen.getByRole("heading", { level: 1, name: title }),
      ).toHaveFocus();
      expect(screen.getByText("SIMULATED DATA")).toBeInTheDocument();
    }
  });

  it("follows backend pagination before searching the full account set", async () => {
    mockFetch.mockImplementation(async (input) => {
      const url = new URL(String(input), "http://127.0.0.1");
      if (url.pathname !== "/api/v1/accounts") return respond(input);
      const original = structuredClone(responses["/api/v1/accounts"]);
      const offset = Number(url.searchParams.get("offset"));
      const responsePage = {
        ...original,
        data: original.data.slice(offset, offset + 4),
        pagination: {
          total: 10,
          limit: 4,
          offset,
          next_offset: offset + 4 < 10 ? offset + 4 : null,
        },
      };
      return new Response(JSON.stringify(responsePage));
    });
    const user = userEvent.setup();
    renderApp("/accounts");
    await screen.findByText("1–5 of 10 accounts");
    await user.type(
      screen.getByRole("searchbox", { name: "Search accounts" }),
      "sim-account-010",
    );
    expect(screen.getByText("1–1 of 1 accounts")).toBeInTheDocument();
    expect(
      mockFetch.mock.calls.some(([input]) =>
        String(input).includes("offset=8"),
      ),
    ).toBe(true);
  });

  it("rejects incomplete pages instead of presenting a partial inventory", async () => {
    mockFetch.mockImplementation(async (input) => {
      const body = await respond(input).json();
      if (String(input).startsWith("/api/v1/accounts?"))
        body.data = body.data.slice(0, 1);
      return new Response(JSON.stringify(body));
    });
    renderApp();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "incomplete inventory",
    );
  });

  it("does not substitute zero for a missing summary count", async () => {
    mockFetch.mockImplementation(async (input) => {
      const body = await respond(input).json();
      if (String(input).startsWith("/api/v1/summary?"))
        delete body.data.account_counts.unknown;
      return new Response(JSON.stringify(body));
    });
    renderApp();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "incomplete compliance counts",
    );
  });

  it("rejects summary distributions that disagree with account statuses", async () => {
    mockFetch.mockImplementation(async (input) => {
      const body = await respond(input).json();
      if (String(input).startsWith("/api/v1/accounts?"))
        body.data[0].compliance.status = "noncompliant";
      return new Response(JSON.stringify(body));
    });
    renderApp();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "snapshot totals are inconsistent",
    );
    expect(
      screen.queryByText("Control evaluation coverage"),
    ).not.toBeInTheDocument();
  });

  it("rejects duplicated inventory rows even when totals match", async () => {
    mockFetch.mockImplementation(async (input) => {
      const body = await respond(input).json();
      if (String(input).startsWith("/api/v1/accounts?"))
        body.data[8] = structuredClone(body.data[0]);
      return new Response(JSON.stringify(body));
    });
    renderApp();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "snapshot totals are inconsistent",
    );
  });

  it("rejects invalid pagination offsets without fetching an endless sequence", async () => {
    mockFetch.mockImplementation(async (input) => {
      const body = await respond(input).json();
      if (String(input).startsWith("/api/v1/accounts?"))
        body.pagination.next_offset = 0;
      return new Response(JSON.stringify(body));
    });
    renderApp();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "invalid pagination",
    );
    expect(
      mockFetch.mock.calls.filter(([input]) =>
        String(input).startsWith("/api/v1/accounts?"),
      ),
    ).toHaveLength(1);
  });

  it("shows a meaningful loading state without fabricated zero metrics", () => {
    mockFetch.mockImplementation(() => new Promise(() => {}));
    renderApp();
    expect(screen.getByRole("status")).toHaveTextContent(
      "Loading governance evidence",
    );
    expect(
      screen.queryByText("Control evaluation coverage"),
    ).not.toBeInTheDocument();
  });

  it("explains authorization failures and supports retry", async () => {
    mockFetch.mockResolvedValue(new Response("{}", { status: 401 }));
    const user = userEvent.setup();
    renderApp();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Backend access is locked",
    );
    expect(screen.queryByText("31")).not.toBeInTheDocument();
    mockFetch.mockImplementation(async (input) => respond(input));
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(
      await screen.findByRole("heading", {
        name: "Control evaluation coverage",
      }),
    ).toBeInTheDocument();
  });

  it("handles an unreachable backend without exposing raw exception contents", async () => {
    mockFetch.mockRejectedValue(new Error("/private/internal/path"));
    renderApp();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "could not be reached",
    );
    expect(
      screen.queryByText("/private/internal/path"),
    ).not.toBeInTheDocument();
  });

  it("fails closed for unexpected simulation provenance", async () => {
    mockFetch.mockImplementation(async (input) => {
      const payload = await respond(input).json();
      payload.metadata.simulated = false;
      return new Response(JSON.stringify(payload));
    });
    renderApp();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "provenance or evaluation time does not match",
    );
    expect(screen.queryByText("31")).not.toBeInTheDocument();
  });

  it("searches across the complete account inventory and paginates", async () => {
    const user = userEvent.setup();
    renderApp("/accounts");
    await screen.findByText("1–5 of 10 accounts");
    expect(
      screen.getByRole("button", { name: "Previous page" }),
    ).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Next page" }));
    expect(screen.getByText("6–10 of 10 accounts")).toBeInTheDocument();
    await user.type(
      screen.getByRole("searchbox", { name: "Search accounts" }),
      "sim-account-002",
    );
    expect(screen.getByText("1–1 of 1 accounts")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "View sim-account-002" }),
    ).toBeInTheDocument();
  });

  it("combines environment/status filters and handles an empty result", async () => {
    const user = userEvent.setup();
    renderApp("/accounts");
    await screen.findByText("1–5 of 10 accounts");
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Environment" }),
      "production",
    );
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Compliance status" }),
      "noncompliant",
    );
    expect(screen.getByText("1–1 of 1 accounts")).toBeInTheDocument();
    await user.type(
      screen.getByRole("searchbox", { name: "Search accounts" }),
      "absent-account",
    );
    expect(
      screen.getByText("No records match your filters."),
    ).toBeInTheDocument();
  });

  it("loads account details through the API and preserves the failed control", async () => {
    const user = userEvent.setup();
    renderApp("/accounts");
    await screen.findByText("1–5 of 10 accounts");
    await user.click(
      screen.getByRole("link", { name: "View sim-account-002" }),
    );
    await screen.findByText("SIMULATED ACCOUNT");
    const row = screen.getByText("Baseline encryption").closest("tr")!;
    expect(within(row).getByText("Noncompliant")).toBeInTheDocument();
    expect(within(row).getByText("exc-002 · Active")).toBeInTheDocument();
    expect(
      mockFetch.mock.calls.some(([input]) =>
        String(input).startsWith("/api/v1/accounts/sim-account-002?"),
      ),
    ).toBe(true);
  });

  it("shows unknown account errors rather than inventing details", async () => {
    renderApp("/accounts/sim-account-999");
    expect(await screen.findByRole("alert")).toHaveTextContent("was not found");
  });

  it("filters findings and clearly distinguishes stale and missing evidence", async () => {
    const user = userEvent.setup();
    renderApp("/compliance");
    await screen.findByText("1–5 of 50 findings");
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Compliance status" }),
      "stale",
    );
    expect(screen.getByText("1–5 of 10 findings")).toBeInTheDocument();
    expect(screen.getAllByText("Evidence expired")).toHaveLength(5);
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Compliance status" }),
      "unknown",
    );
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Account" }),
      "sim-account-004",
    );
    expect(screen.getByText("No evidence recorded")).toBeInTheDocument();
    expect(screen.getByText("1–1 of 1 findings")).toBeInTheDocument();
  });

  it("shows simulated deployment failures and unequal desired/observed revisions", async () => {
    renderApp("/deployments?status=failed");
    await screen.findByText("Simulated customization failure");
    expect(screen.getByText("SIMULATED HISTORY")).toBeInTheDocument();
    expect(screen.getByText("synthetic-revision-002")).toBeInTheDocument();
    expect(screen.getByText("synthetic-revision-001")).toBeInTheDocument();
    expect(screen.getByText("1–1 of 1 executions")).toBeInTheDocument();
  });

  it("renders actual drift observations", async () => {
    renderApp("/drift");
    await screen.findByText("1–1 of 1 observations");
    const row = screen.getByText("Public access restrictions").closest("tr")!;
    expect(within(row).getByText("true")).toBeInTheDocument();
    expect(within(row).getByText("false")).toBeInTheDocument();
    expect(within(row).getByText("Drifted")).toBeInTheDocument();
  });

  it("retains violations for active and expired exceptions and does not fabricate pending requests", async () => {
    const user = userEvent.setup();
    renderApp("/exceptions");
    await screen.findByText("1–2 of 2 exceptions");
    expect(screen.getAllByText("Noncompliant")).toHaveLength(2);
    expect(
      within(screen.getByRole("table")).getByText("Active"),
    ).toBeInTheDocument();
    expect(
      within(screen.getByRole("table")).getByText("Expired"),
    ).toBeInTheDocument();
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Expiration state" }),
      "pending",
    );
    expect(
      screen.getByText("No records match your filters."),
    ).toBeInTheDocument();
  });

  it("provides a mobile navigation toggle and closes the drawer on navigation", async () => {
    const user = userEvent.setup();
    renderApp();
    const toggle = screen.getByRole("button", { name: "Toggle navigation" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    await user.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    await user.keyboard("{Escape}");
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(toggle).toHaveFocus();
    await user.click(toggle);
    await user.click(
      within(screen.getByRole("navigation")).getByRole("link", {
        name: "Accounts",
      }),
    );
    expect(toggle).toHaveAttribute("aria-expanded", "false");
  });

  it("refreshes the API snapshot on demand", async () => {
    const user = userEvent.setup();
    renderApp();
    await screen.findByRole("heading", { name: "Account compliance posture" });
    const initial = mockFetch.mock.calls.length;
    await user.click(screen.getByRole("button", { name: "Refresh snapshot" }));
    await waitFor(() =>
      expect(mockFetch.mock.calls.length).toBeGreaterThan(initial),
    );
  });
});
