import { beforeEach, afterEach, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { App } from "../App";
import { request } from "../api/client";
import versions from "./version-responses.json";
const fixtures = versions as Record<string, Record<string, unknown>>;
let rejectV2 = false;
let currentPolicy = "1.0.0";
let catalogFailure = false;
beforeEach(() => {
  rejectV2 = false;
  currentPolicy = "1.0.0";
  catalogFailure = false;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(String(input), "http://127.0.0.1");
      const version = url.searchParams.get("policy_version") ?? "1.0.0";
      if (rejectV2 && version === "2.0.0")
        return new Response("unavailable", { status: 500 });
      if (catalogFailure && url.searchParams.get("catalog") === "true")
        return new Response("unavailable", { status: 500 });
      const data = structuredClone(fixtures[version]?.[url.pathname]);
      if (
        url.pathname === "/api/v1/summary" &&
        data &&
        typeof data === "object" &&
        "data" in data
      ) {
        const summary = data.data as {
          current?: unknown;
          current_run?: string;
          versions: { policy_version: string }[];
        };
        summary.current = summary.versions.find(
          (v) => v.policy_version === currentPolicy,
        );
        summary.current_run =
          currentPolicy === "1.0.0" ? "baseline" : "run-0001";
      }
      const status =
        data && typeof data === "object" && "error" in data
          ? 404
          : data
            ? 200
            : 404;
      return new Response(JSON.stringify(data), { status });
    }),
  );
});
afterEach(() => vi.unstubAllGlobals());
function show() {
  return render(
    <QueryClientProvider
      client={
        new QueryClient({
          defaultOptions: { queries: { retry: false, gcTime: Infinity } },
        })
      }
    >
      <MemoryRouter>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
it("switches all pages, account details, rollout outcomes and evidence timestamps without leaking V2 into V1", async () => {
  const user = userEvent.setup();
  show();
  await screen.findByRole("heading", { name: "Account compliance posture" });
  const selector = screen.getByRole("combobox", {
    name: "Historical snapshot",
  });
  await waitFor(() =>
    expect(within(selector).getAllByRole("option")).toHaveLength(3),
  );
  await user.selectOptions(selector, "2.0.0");
  await screen.findByText(/SIMULATED policy rollout/);
  expect(screen.getByText(/canary passed/i)).toBeInTheDocument();
  expect(screen.getByText(/rollout blocked/i)).toBeInTheDocument();
  expect(screen.getByText(/31 Oct 2026, 12:28/)).toBeInTheDocument();
  await user.click(screen.getByRole("link", { name: /Accounts/ }));
  await user.type(
    await screen.findByRole("searchbox", { name: "Search accounts" }),
    "sim-account-011",
  );
  const account = await screen.findByText("NorthStar New Development");
  await user.click(account.closest("a")!);
  await screen.findByText("Audit log integrity validation");
  expect(screen.getAllByText(/2026-10-31 12:27:00 UTC/).length).toBeGreaterThan(
    0,
  );
  await user.click(screen.getByRole("link", { name: /Compliance/ }));
  await screen.findByRole("heading", { name: "Policy compliance" });
  await user.click(screen.getByRole("link", { name: /Accounts/ }));
  await user.selectOptions(
    screen.getByRole("combobox", { name: "Historical snapshot" }),
    "1.0.0",
  );
  await screen.findByText("10 synthetic accounts");
  expect(
    screen.queryByText("NorthStar New Development"),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByText(/SIMULATED policy rollout/),
  ).not.toBeInTheDocument();
});
it("shows a V2 error without substituting V1 and allows a safe return to V1", async () => {
  const user = userEvent.setup();
  show();
  await screen.findByRole("heading", { name: "Account compliance posture" });
  await waitFor(() =>
    expect(
      screen.getByRole("option", { name: /Policy 2.0.0/ }),
    ).toBeInTheDocument(),
  );
  rejectV2 = true;
  await user.selectOptions(
    screen.getByRole("combobox", { name: "Historical snapshot" }),
    "2.0.0",
  );
  await screen.findByText(/could not complete/);
  expect(
    screen.queryByRole("heading", { name: "Account compliance posture" }),
  ).not.toBeInTheDocument();
  await user.selectOptions(
    screen.getByRole("combobox", { name: "Historical snapshot" }),
    "1.0.0",
  );
  await screen.findByRole("heading", { name: "Account compliance posture" });
});
it("rejects a response from the wrong immutable partition even when its policy version matches", async () => {
  const response = structuredClone(versions["2.0.0"]["/api/v1/summary"]);
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response(JSON.stringify(response))),
  );
  await expect(
    request("/api/v1/summary", new AbortController().signal, {}, undefined, {
      policy_version: "2.0.0",
      evaluated_at: response.metadata.evaluated_at,
      snapshot_id: "wrong-digest",
    }),
  ).rejects.toThrow("provenance or evaluation time");
});

it("opens CURRENT on each new session instead of restoring historical selection", async () => {
  currentPolicy = "2.0.0";
  const user = userEvent.setup();
  const first = show();
  await screen.findByText(/CURRENT GOVERNANCE · Policy revision 2.0.0/);
  expect(
    screen.getByRole("combobox", { name: "Historical snapshot" }),
  ).toHaveValue("current");
  await user.selectOptions(
    screen.getByRole("combobox", { name: "Historical snapshot" }),
    "1.0.0",
  );
  await screen.findByText(/HISTORICAL EVALUATION · Policy revision 1.0.0/);
  first.unmount();
  show();
  await screen.findByText(/CURRENT GOVERNANCE · Policy revision 2.0.0/);
  expect(
    screen.getByRole("combobox", { name: "Historical snapshot" }),
  ).toHaveValue("current");
});

it("advances CURRENT on one refresh and reset returns CURRENT to baseline while history stays readable", async () => {
  const user = userEvent.setup();
  show();
  await screen.findByText(/CURRENT GOVERNANCE · Policy revision 1.0.0/);
  currentPolicy = "2.0.0";
  await user.click(
    screen.getByRole("button", { name: "Refresh current state" }),
  );
  await screen.findByText(/CURRENT GOVERNANCE · Policy revision 2.0.0/);
  await screen.findByText(/SIMULATED policy rollout/);
  expect(
    screen.getByRole("combobox", { name: "Historical snapshot" }),
  ).toHaveValue("current");
  currentPolicy = "1.0.0";
  await user.click(
    screen.getByRole("button", { name: "Refresh current state" }),
  );
  await screen.findByText(/CURRENT GOVERNANCE · Policy revision 1.0.0/);
  await user.selectOptions(
    screen.getByRole("combobox", { name: "Historical snapshot" }),
    "2.0.0",
  );
  await screen.findByText(/HISTORICAL EVALUATION · Policy revision 2.0.0/);
});

it("does not show a historical baseline as CURRENT when current resolution fails", async () => {
  catalogFailure = true;
  show();
  await screen.findByRole("alert");
  expect(
    screen.queryByRole("heading", { name: "Account compliance posture" }),
  ).not.toBeInTheDocument();
  expect(screen.getByText("Current state unavailable")).toBeInTheDocument();
});

it("prioritizes rollout targets, approval, retry and noncompliant evidence in Deployments", async () => {
  currentPolicy = "2.0.0";
  const user = userEvent.setup();
  show();
  await screen.findByText(/CURRENT GOVERNANCE · Policy revision 2.0.0/);
  await user.click(screen.getByRole("link", { name: /Deployments/ }));
  await screen.findByRole("heading", { name: "Governance rollout history" });
  expect(
    screen.getByText(
      /9 targeted accounts · 10 attempts · 1 retries retained · 1 failed attempts/,
    ),
  ).toBeInTheDocument();
  expect(
    screen.getByText(/completed with 2 inactive accounts deferred/),
  ).toBeInTheDocument();
  expect(
    screen.getByText(/4 noncompliant, 9 unknown and 10 stale findings/),
  ).toBeInTheDocument();
});
