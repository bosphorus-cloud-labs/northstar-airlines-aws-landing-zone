import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { App } from "../App";
import { resourceState } from "../api/resources";
import * as configuration from "../auth/config";
import { setTokenProvider } from "../auth/session";
import response from "./resource-responses.json";
import legacy from "./api-responses.json";
const fetcher = vi.fn<typeof fetch>();
const clients: QueryClient[] = [];
function show(path = "/") {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity } },
  });
  clients.push(client);
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
beforeEach(() => {
  vi.stubEnv("VITE_GOVERNANCE_API_MODE", "resources");
  fetcher.mockReset().mockImplementation(async (input) => {
    const path = new URL(String(input), "http://127.0.0.1").pathname;
    return new Response(
      JSON.stringify(
        path === "/api/v1/exceptions"
          ? legacy["/api/v1/exceptions"]
          : path === "/api/v1/deployments"
            ? legacy["/api/v1/deployments"]
            : response,
      ),
    );
  });
  vi.stubGlobal("fetch", fetcher);
});
afterEach(() => {
  clients.splice(0).forEach((c) => c.clear());
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  setTokenProvider(() => null);
});
it("uses the current backend dataset with visible simulation and no policy selectors", async () => {
  show();
  expect(
    await screen.findByRole("heading", { name: "What needs attention" }),
  ).toBeInTheDocument();
  expect(screen.getByText("SIMULATED DATA")).toBeInTheDocument();
  expect(
    screen.getByText(/Not run for this local fixture/),
  ).toBeInTheDocument();
  expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  expect(screen.queryByText(/V1|V2|snapshot digest/i)).not.toBeInTheDocument();
  expect(fetcher.mock.calls[0][0]).toBe("/api/v1/summary?view=resources");
  expect(fetcher.mock.calls[0][1]?.method).toBe("GET");
});
it("navigates, paginates and filters account inventory then opens account resources", async () => {
  const user = userEvent.setup();
  show("/accounts");
  await screen.findByText(/10 accounts · Page 1/);
  await user.selectOptions(screen.getByLabelText("Rows per page"), "5");
  await user.click(screen.getByRole("button", { name: "Next" }));
  expect(screen.getByText(/Page 2/)).toBeInTheDocument();
  await user.selectOptions(screen.getByLabelText("Environment"), "production");
  expect(screen.getByText(/3 accounts · Page 1/)).toBeInTheDocument();
  await user.type(screen.getByLabelText("Search"), "sim-account-001");
  expect(screen.getByText(/1 accounts · Page 1/)).toBeInTheDocument();
  await user.click(
    screen.getByRole("link", { name: response.data.accounts[0].name }),
  );
  expect(await screen.findByText("Booking API")).toBeInTheDocument();
  expect(
    screen.getByRole("columnheader", { name: "Desired" }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("columnheader", { name: "Observed" }),
  ).toBeInTheDocument();
});
it("shows why a specific resource fails and handles empty resource filters", async () => {
  const user = userEvent.setup();
  show("/resources");
  await screen.findByText("Booking API");
  await user.selectOptions(
    screen.getByLabelText("Compliance status"),
    "noncompliant",
  );
  expect(screen.queryByText("Booking API")).not.toBeInTheDocument();
  expect(
    screen.getByText(
      response.data.findings.find((f) => f.status === "noncompliant")!.reason,
    ),
  ).toBeInTheDocument();
  await user.type(screen.getByLabelText("Search"), "no-such-resource");
  expect(
    screen.getByText("No resources match these filters."),
  ).toBeInTheDocument();
});
it("refreshes the same current endpoint and exposes loading and sanitized failure", async () => {
  fetcher.mockImplementationOnce(() => new Promise(() => {}));
  const first = show();
  expect(screen.getByRole("status")).toHaveTextContent("Loading");
  first.unmount();
  fetcher.mockResolvedValue(
    new Response("secret/internal/path", { status: 503 }),
  );
  show();
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Current compliance data is unavailable",
  );
  expect(screen.queryByText("secret/internal/path")).not.toBeInTheDocument();
  fetcher.mockImplementation(
    async () => new Response(JSON.stringify(response)),
  );
  await userEvent.click(screen.getByRole("button", { name: "Try again" }));
  await screen.findByRole("heading", { name: "What needs attention" });
  await userEvent.click(screen.getByRole("button", { name: "Refresh" }));
  await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(4));
});
it("reports no fabricated publication events for an unseeded local fixture", async () => {
  show("/deployments");
  expect(
    await screen.findByText(/No protected publications recorded/),
  ).toBeInTheDocument();
  expect(
    screen.getByText(/not Terraform apply executions/),
  ).toBeInTheDocument();
});
it("rejects unlabelled API data", async () => {
  fetcher.mockResolvedValue(
    new Response(
      JSON.stringify({
        ...response,
        metadata: { ...response.metadata, simulated: false },
      }),
    ),
  );
  await expect(resourceState(new AbortController().signal)).rejects.toThrow(
    "inconsistent or unlabelled",
  );
});

it("retains visible approved and expired exceptions without hiding violations", async () => {
  show("/exceptions");
  expect(
    await screen.findByText("sim-account-002 · baseline-encryption"),
  ).toBeInTheDocument();
  expect(screen.getByText("Expired")).toBeInTheDocument();
  const url = fetcher.mock.calls
    .map(([input]) => String(input))
    .find((path) => path.includes("/exceptions"));
  expect(url).toBe("/api/v1/exceptions?limit=100");
  expect(
    screen.getAllByText("The underlying compliance violation remains visible."),
  ).toHaveLength(2);
});

it("requires a Cognito session and transmits its access token only as a read authorization header", async () => {
  const config = vi.spyOn(configuration, "runtimeConfig").mockReturnValue({
    mode: "cognito",
    apiBase: "https://synthetic.execute-api.eu-central-1.amazonaws.com/poc",
    issuer:
      "https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_synthetic",
    clientId: "synthetic",
    domain: "https://synthetic.auth.eu-central-1.amazoncognito.com",
    appOrigin: "https://synthetic.amplifyapp.com",
  });
  try {
    await expect(resourceState(new AbortController().signal)).rejects.toThrow(
      "Sign in",
    );
    expect(fetcher).not.toHaveBeenCalled();
    setTokenProvider(() => "synthetic-unit-token");
    await resourceState(new AbortController().signal);
    expect(fetcher.mock.calls[0][1]?.headers).toMatchObject({
      Authorization: "Bearer synthetic-unit-token",
    });
    expect(fetcher.mock.calls[0][1]?.credentials).toBe("omit");
    expect(String(fetcher.mock.calls[0][0])).not.toContain(
      "synthetic-unit-token",
    );
  } finally {
    config.mockRestore();
  }
});

it("opens a read-only acceptance preview without changing the default or authentication", async () => {
  vi.stubEnv("VITE_GOVERNANCE_API_MODE", "catalog");
  fetcher.mockImplementation(async (input) => {
    const url = new URL(String(input), "http://127.0.0.1");
    const key =
      url.pathname +
      (url.searchParams.get("catalog") === "true" ? "?catalog=true" : "");
    return new Response(
      JSON.stringify(
        url.searchParams.get("view") === "resources"
          ? response
          : (legacy as Record<string, unknown>)[key],
      ),
    );
  });
  show();
  await screen.findByRole("heading", { name: "Account compliance posture" });
  await userEvent.click(
    screen.getByRole("button", { name: "Preview resource console" }),
  );
  expect(
    await screen.findByRole("heading", { name: "What needs attention" }),
  ).toBeInTheDocument();
  expect(
    fetcher.mock.calls.some(([input]) =>
      String(input).includes("view=resources"),
    ),
  ).toBe(true);
  expect(
    fetcher.mock.calls.every(([, options]) => options?.method === "GET"),
  ).toBe(true);
});

it("navigates the full 100-account fleet, filters environments and handles current-state shrink", async () => {
  const scale = (await import("./resource-scale-responses.json")).default;
  fetcher.mockImplementation(async () => new Response(JSON.stringify(scale)));
  const user = userEvent.setup();
  show("/accounts");
  await screen.findByText(/100 accounts · Page 1 of 10/);
  expect(
    screen.getByText(/Evaluating 100 synthetic AWS accounts/),
  ).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Last" }));
  expect(screen.getByText(/Page 10 of 10/)).toBeInTheDocument();
  expect(screen.getByText("sim-account-100")).toBeInTheDocument();
  await user.selectOptions(screen.getByLabelText("Environment"), "production");
  expect(screen.getByText(/30 accounts · Page 1 of 3/)).toBeInTheDocument();
  await user.selectOptions(
    screen.getByLabelText("Compliance status"),
    "noncompliant",
  );
  expect(screen.getByText(/2 accounts · Page 1 of 1/)).toBeInTheDocument();
  await user.selectOptions(screen.getByLabelText("Environment"), "");
  await user.selectOptions(screen.getByLabelText("Compliance status"), "");
  await user.selectOptions(screen.getByLabelText("Rows per page"), "25");
  expect(screen.getByText(/100 accounts · Page 1 of 4/)).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Last" }));
  fetcher.mockImplementation(
    async () => new Response(JSON.stringify(response)),
  );
  await user.click(screen.getByRole("button", { name: "Refresh" }));
  expect(
    await screen.findByText(/10 accounts · Page 1 of 1/),
  ).toBeInTheDocument();
  expect(screen.getByText("sim-account-001")).toBeInTheDocument();
});

it("paginates 100 resource findings and keeps Booking API discoverable by account or name", async () => {
  const scale = (await import("./resource-scale-responses.json")).default;
  fetcher.mockImplementation(async () => new Response(JSON.stringify(scale)));
  const user = userEvent.setup();
  show("/resources");
  await screen.findByText(/100 resources · Page 1 of 10/);
  expect(screen.getAllByRole("row")).toHaveLength(11);
  await user.click(screen.getByRole("button", { name: "Last" }));
  expect(screen.getByText(/Page 10 of 10/)).toBeInTheDocument();
  await user.type(screen.getByLabelText("Search"), "Booking API");
  expect(screen.getByText(/1 resources · Page 1 of 1/)).toBeInTheDocument();
  expect(screen.getByText("Booking API")).toBeInTheDocument();
  await user.clear(screen.getByLabelText("Search"));
  await user.type(screen.getByLabelText("Search"), "sim-account-100");
  expect(screen.getByText(/1 resources · Page 1 of 1/)).toBeInTheDocument();
  expect(
    screen.getByRole("link", { name: "sim-account-100" }),
  ).toBeInTheDocument();
});

it("summarizes backend evidence by control and environment across the 100-account fleet", async () => {
  const scale = (await import("./resource-scale-responses.json")).default;
  fetcher.mockImplementation(async () => new Response(JSON.stringify(scale)));
  const user = userEvent.setup();
  show("/compliance");
  await screen.findByRole("heading", {
    name: "Compliance by governance control",
  });
  expect(screen.getByText("SIMULATED DATA")).toBeInTheDocument();
  expect(
    screen.queryByRole("columnheader", { name: "Observed" }),
  ).not.toBeInTheDocument();
  expect(screen.queryByLabelText("Search")).not.toBeInTheDocument();
  expect(screen.getAllByRole("row")).toHaveLength(5);
  const statuses = ["compliant", "noncompliant", "unknown", "stale"] as const;
  for (const env of [
    "",
    "production",
    "pre-production",
    "testing",
    "development",
  ]) {
    await user.selectOptions(screen.getByLabelText("Environment"), env);
    const evidence = scale.data.findings.filter(
      (finding) => !env || finding.environment === env,
    );
    for (const control of scale.data.controls) {
      const row = screen.getByRole("row", { name: new RegExp(control.name) });
      const findings = evidence.filter(
        (finding) => finding.control_id === control.id,
      );
      const counts = within(row)
        .getAllByRole("cell")
        .slice(1)
        .map((cell) => Number(cell.textContent));
      expect(counts).toEqual([
        findings.length,
        ...statuses.map(
          (status) =>
            findings.filter((finding) => finding.status === status).length,
        ),
      ]);
      expect(screen.queryByText(control.reason)).not.toBeInTheDocument();
    }
    const totals = within(screen.getByRole("row", { name: /^All controls/ }))
      .getAllByRole("cell")
      .map((cell) => Number(cell.textContent));
    expect(totals).toEqual([
      evidence.length,
      ...statuses.map(
        (status) =>
          evidence.filter((finding) => finding.status === status).length,
      ),
    ]);
    if (!env)
      expect(totals).toEqual([
        scale.data.summary.resources,
        ...statuses.map((status) => scale.data.summary[status]),
      ]);
    expect(
      screen.getByText(
        `${evidence.length} synthetic control evaluations in this view.`,
      ),
    ).toBeInTheDocument();
  }
  expect(fetcher).toHaveBeenCalledTimes(1);
  expect(fetcher.mock.calls[0][0]).toBe("/api/v1/summary?view=resources");
});

it("navigates from control-level Compliance to distinct resource drift and account details", async () => {
  const user = userEvent.setup();
  show("/compliance");
  await screen.findByRole("heading", {
    name: "Compliance by governance control",
  });
  expect(screen.queryByText("Booking API")).not.toBeInTheDocument();
  expect(
    screen.queryByRole("columnheader", { name: "Desired" }),
  ).not.toBeInTheDocument();
  await user.click(
    within(screen.getByRole("main")).getByRole("link", {
      name: "Resources & drift",
    }),
  );
  expect(await screen.findByText("Booking API")).toBeInTheDocument();
  expect(
    screen.getByRole("columnheader", { name: "Desired" }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("columnheader", { name: "Observed" }),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("heading", { name: "Compliance by governance control" }),
  ).not.toBeInTheDocument();
  await user.type(screen.getByLabelText("Search"), "Booking API");
  await user.click(screen.getByRole("link", { name: "sim-account-001" }));
  expect(
    await screen.findByRole("heading", {
      name: response.data.accounts[0].name,
    }),
  ).toBeInTheDocument();
  expect(screen.getByText("Booking API")).toBeInTheDocument();
  expect(
    fetcher.mock.calls.every(([, options]) => options?.method === "GET"),
  ).toBe(true);
});

it("does not manufacture results for unobserved controls and refreshes the current evidence", async () => {
  const user = userEvent.setup();
  show("/compliance");
  await screen.findByRole("heading", {
    name: "Compliance by governance control",
  });
  await user.selectOptions(
    screen.getByLabelText("Environment"),
    "pre-production",
  );
  const ebs = screen.getByRole("row", { name: /Encrypt EBS volumes/ });
  expect(
    within(ebs)
      .getAllByRole("cell")
      .slice(1)
      .map((cell) => Number(cell.textContent)),
  ).toEqual([0, 0, 0, 0, 0]);
  await user.selectOptions(screen.getByLabelText("Environment"), "");
  const scale = (await import("./resource-scale-responses.json")).default;
  fetcher.mockImplementation(async () => new Response(JSON.stringify(scale)));
  await user.click(screen.getByRole("button", { name: "Refresh" }));
  await screen.findByText("100 synthetic control evaluations in this view.");
  const totals = within(screen.getByRole("row", { name: /^All controls/ }))
    .getAllByRole("cell")
    .map((cell) => Number(cell.textContent));
  expect(totals).toEqual([100, 77, 9, 7, 7]);
  expect(fetcher).toHaveBeenCalledTimes(2);
});
