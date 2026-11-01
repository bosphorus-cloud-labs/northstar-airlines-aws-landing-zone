import { DEFAULT_SELECTION, useSelection, type Selection } from "./selection";
import { runtimeConfig } from "../auth/config";
import { accessToken } from "../auth/session";
import { useQuery } from "@tanstack/react-query";
import type { components, paths } from "./schema";

export const REFERENCE_AT = "2026-10-31T12:00:00Z";
export type Models = components["schemas"];
export type Status = Models["Status"];
export type Environment = Models["Environment"];
export type Finding = Models["Finding"];
export type AccountView = Models["AccountView"];
type ApiPath = keyof paths;
type Responses = {
  [
    P in ApiPath
  ]: paths[P]["get"]["responses"][200]["content"]["application/json"];
};
type ResponseFor<P extends ApiPath> = Responses[P];

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

export async function request<P extends ApiPath>(
  path: P,
  signal: AbortSignal,
  params: Record<string, string | number> = {},
  accountId?: string,
  selection: Selection = DEFAULT_SELECTION,
): Promise<ResponseFor<P>> {
  const query = new URLSearchParams(
    path === "/api/v1/health"
      ? {}
      : {
          at: selection.evaluated_at,
          ...(selection.snapshot_id || selection.policy_version !== "1.0.0"
            ? { policy_version: selection.policy_version }
            : {}),
        },
  );
  for (const [key, value] of Object.entries(params))
    query.set(key, String(value));
  const config = runtimeConfig();
  const token = config.mode === "cognito" ? accessToken() : null;
  if (config.mode === "cognito" && !token)
    throw new ApiError(
      401,
      "Sign in with Cognito to access governance evidence.",
    );
  let response: Response;
  try {
    const target = accountId
      ? path.replace("{account_id}", encodeURIComponent(accountId))
      : path;
    response = await fetch(`${config.apiBase}${target}?${query}`, {
      method: "GET",
      signal: AbortSignal.any([signal, AbortSignal.timeout(15000)]),
      credentials: "omit",
      headers: {
        Accept: "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });
  } catch {
    if (signal.aborted)
      throw new DOMException("Request cancelled", "AbortError");
    throw new ApiError(
      0,
      "The governance API could not be reached. Check the local backend and try again.",
    );
  }
  if (!response.ok) {
    const message =
      response.status === 401
        ? config.mode === "local"
          ? "Backend access is locked. Start the API with --local-demo on this workstation."
          : "Your session was rejected. Sign out and sign in again."
        : response.status === 403
          ? config.mode === "local"
            ? "Access was denied. This console requires the loopback-only local demo backend."
            : "Access was denied. A governance reader scope and group membership are required."
          : response.status === 404
            ? "The requested account or resource was not found."
            : "The governance API could not complete this request. Try again.";
    throw new ApiError(response.status, message);
  }
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    throw new ApiError(0, "The API returned an unreadable response.");
  }
  if (
    !body ||
    typeof body !== "object" ||
    !("metadata" in body) ||
    !("data" in body)
  ) {
    throw new ApiError(0, "The API returned an unsupported response format.");
  }
  const metadata = body.metadata as Partial<Models["Metadata"]> | null;
  if (
    metadata?.api_version !== "v1" ||
    metadata.simulated !== true ||
    metadata.source !== "northstar-synthetic-v1" ||
    metadata.evaluated_at !== selection.evaluated_at ||
    ((selection.snapshot_id || selection.policy_version !== "1.0.0") &&
      (!("policy_version" in metadata) ||
        metadata.policy_version !== selection.policy_version ||
        !("snapshot_id" in metadata) ||
        metadata.snapshot_id !== selection.snapshot_id))
  ) {
    throw new ApiError(
      0,
      "The API provenance or evaluation time does not match this simulation. No results were displayed.",
    );
  }
  return body as ResponseFor<P>;
}

type ListPath =
  | "/api/v1/accounts"
  | "/api/v1/findings"
  | "/api/v1/deployments"
  | "/api/v1/drift"
  | "/api/v1/exceptions";
async function allPages<P extends ListPath>(
  path: P,
  signal: AbortSignal,
  selection: Selection,
): Promise<ResponseFor<P>["data"]> {
  const rows: unknown[] = [];
  let offset = 0;
  let total: number | undefined;
  for (let count = 0; count < 100; count++) {
    const result = await request(
      path,
      signal,
      { limit: 100, offset },
      undefined,
      selection,
    );
    if (
      !Array.isArray(result.data) ||
      !result.pagination ||
      result.pagination.offset !== offset ||
      !Number.isSafeInteger(result.pagination.total) ||
      result.pagination.total < 0 ||
      !Number.isSafeInteger(result.pagination.limit) ||
      result.pagination.limit < 1 ||
      result.pagination.limit > 100 ||
      result.data.length > result.pagination.limit ||
      (total !== undefined && result.pagination.total !== total)
    ) {
      throw new ApiError(0, "The API returned invalid pagination.");
    }
    total = result.pagination.total;
    rows.push(...result.data);
    if (
      result.pagination.next_offset === null ||
      result.pagination.next_offset === undefined
    ) {
      if (rows.length !== result.pagination.total)
        throw new ApiError(
          0,
          "The API returned an incomplete inventory. No results were displayed.",
        );
      return rows as ResponseFor<P>["data"];
    }
    if (
      !Number.isSafeInteger(result.pagination.next_offset) ||
      result.pagination.next_offset !== offset + result.data.length ||
      result.pagination.next_offset <= offset ||
      result.pagination.next_offset >= total
    )
      throw new ApiError(0, "The API returned invalid pagination.");
    offset = result.pagination.next_offset;
  }
  throw new ApiError(0, "The dataset exceeds the local console limit.");
}

function completeCounts(counts: Models["Counts"]): Required<Models["Counts"]> {
  const number = (value: number | undefined) => {
    if (typeof value !== "number" || !Number.isInteger(value) || value < 0) {
      throw new ApiError(
        0,
        "The API returned incomplete compliance counts. No results were displayed.",
      );
    }
    return value;
  };
  return {
    compliant: number(counts.compliant),
    noncompliant: number(counts.noncompliant),
    unknown: number(counts.unknown),
    stale: number(counts.stale),
  };
}

async function loadDataset(signal: AbortSignal, selection: Selection) {
  const [summary, accounts, findings, deployments, drift, exceptions] =
    await Promise.all([
      request("/api/v1/summary", signal, {}, undefined, selection),
      allPages("/api/v1/accounts", signal, selection),
      allPages("/api/v1/findings", signal, selection),
      allPages("/api/v1/deployments", signal, selection),
      allPages("/api/v1/drift", signal, selection),
      allPages("/api/v1/exceptions", signal, selection),
    ]);
  const account_counts = completeCounts(summary.data.account_counts);
  const finding_counts = completeCounts(summary.data.finding_counts);
  if (
    accounts.length !== summary.data.account_count ||
    findings.length !== summary.data.finding_count ||
    Object.values(account_counts).reduce((a, b) => a + b, 0) !==
      accounts.length ||
    Object.values(finding_counts).reduce((a, b) => a + b, 0) !== findings.length
  ) {
    throw new ApiError(
      0,
      "The API snapshot totals are inconsistent. No results were displayed.",
    );
  }
  // Reconcile API-provided statuses, not policy rules, across endpoint responses.
  const statuses = Object.keys(account_counts) as Status[];
  const accountIds = new Set(accounts.map((a) => a.account.id));
  const findingIds = new Set(findings.map((f) => f.id));
  const environmentCounts: Record<string, number> = {};
  for (const { account } of accounts) {
    environmentCounts[account.environment] =
      (environmentCounts[account.environment] ?? 0) + 1;
  }
  const environments = new Set([
    ...Object.keys(environmentCounts),
    ...Object.keys(summary.data.environment_counts),
  ]);
  if (
    accountIds.size !== accounts.length ||
    findingIds.size !== findings.length ||
    findings.some((f) => !accountIds.has(f.account_id)) ||
    statuses.some(
      (status) =>
        accounts.filter((a) => a.compliance.status === status).length !==
          account_counts[status] ||
        findings.filter((f) => f.status === status).length !==
          finding_counts[status],
    ) ||
    [...environments].some(
      (environment) =>
        !Number.isSafeInteger(summary.data.environment_counts[environment]) ||
        (environmentCounts[environment] ?? 0) !==
          summary.data.environment_counts[environment],
    )
  ) {
    throw new ApiError(
      0,
      "The API snapshot totals are inconsistent. No results were displayed.",
    );
  }
  return {
    summary: { ...summary.data, account_counts, finding_counts },
    metadata: summary.metadata,
    accounts,
    findings,
    deployments,
    drift,
    exceptions,
  };
}
export type Dataset = Awaited<ReturnType<typeof loadDataset>>;
export function useDataset() {
  const selection = useSelection();
  return useQuery({
    queryKey: ["governance", selection],
    enabled: selection.ready !== false,
    queryFn: ({ signal }) => loadDataset(signal, selection),
    staleTime: 60000,
    retry: false,
    refetchOnWindowFocus: false,
  });
}
export function useAccount(accountId: string) {
  const selection = useSelection();
  return useQuery({
    queryKey: ["account", accountId, selection],
    queryFn: ({ signal }) =>
      request(
        "/api/v1/accounts/{account_id}",
        signal,
        {},
        accountId,
        selection,
      ),
    enabled: Boolean(accountId) && selection.ready !== false,
    staleTime: 60000,
    retry: false,
    refetchOnWindowFocus: false,
  });
}
