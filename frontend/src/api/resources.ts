import { runtimeConfig } from "../auth/config";
import { freshAccessToken, rejectSession } from "../auth/session";
import { ApiError } from "./client";
import type { components } from "./schema";
export type ResourceResponse = components["schemas"]["ResourceEnvelope"];
export type ResourceData = ResourceResponse["data"];
async function read(path: string, signal: AbortSignal): Promise<unknown> {
  const config = runtimeConfig();
  const token = config.mode === "cognito" ? await freshAccessToken() : null;
  if (config.mode === "cognito" && !token)
    throw new ApiError(401, "Sign in to read compliance evidence.");
  let response: Response;
  try {
    response = await fetch(`${config.apiBase}${path}`, {
      method: "GET",
      credentials: "omit",
      signal: AbortSignal.any([signal, AbortSignal.timeout(15000)]),
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
      "The compliance API could not be reached. Try refreshing.",
    );
  }
  if (!response.ok) {
    if (config.mode === "cognito" && response.status === 401) rejectSession();
    throw new ApiError(
      response.status,
      response.status === 401 || response.status === 403
        ? "Access denied. Sign in with an authorized governance reader account."
        : "Current compliance data is unavailable. No local or historical fallback has been substituted.",
    );
  }
  let value: unknown;
  try {
    value = await response.json();
  } catch {
    throw new ApiError(0, "Unreadable compliance response.");
  }
  return value;
}
export async function resourceState(
  signal: AbortSignal,
): Promise<ResourceResponse> {
  const value = (await read(
    "/api/v1/summary?view=resources",
    signal,
  )) as ResourceResponse;
  if (
    value?.metadata?.api_version !== "v1" ||
    value.metadata.simulated !== true ||
    value.metadata.source !== "northstar-synthetic-resources" ||
    !Array.isArray(value.data?.resources) ||
    !Array.isArray(value.data?.accounts) ||
    !Array.isArray(value.data?.findings) ||
    !Array.isArray(value.data?.activity) ||
    !value.data.summary ||
    value.data.summary.resources !== value.data.resources.length ||
    value.data.summary.accounts !== value.data.accounts.length ||
    value.data.findings.some((f) => f.simulated !== true)
  )
    throw new ApiError(
      0,
      "The API returned inconsistent or unlabelled synthetic data.",
    );
  return value;
}

type AccountRecords =
  | components["schemas"]["Page_Deployment_"]
  | components["schemas"]["Page_ExceptionView_"];
export async function accountRecords(
  exceptions: boolean,
  signal: AbortSignal,
): Promise<AccountRecords> {
  // Let the server resolve its current account catalogue and reference time.
  const value = (await read(
    `/api/v1/${exceptions ? "exceptions" : "deployments"}?limit=100`,
    signal,
  )) as AccountRecords;
  if (
    value?.metadata?.api_version !== "v1" ||
    value.metadata.simulated !== true ||
    !Array.isArray(value.data) ||
    value.data.some(
      (row) =>
        ("exception" in row ? row.exception.simulated : row.simulated) !== true,
    )
  )
    throw new ApiError(0, "Unlabelled account-governance response.");
  return value;
}
