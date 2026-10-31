import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AuthGate } from "../auth/AuthGate";
import { readConfig } from "../auth/config";
import { oidcSettings } from "../auth/oidc";
import { request } from "../api/client";
import { accessToken, setTokenProvider } from "../auth/session";
import responses from "./api-responses.json";

const mocks = vi.hoisted(() => ({
  getUser: vi.fn(),
  signinRedirectCallback: vi.fn(),
  signinRedirect: vi.fn(),
  removeUser: vi.fn(),
  addAccessTokenExpired: vi.fn(),
  removeAccessTokenExpired: vi.fn(),
}));
vi.mock("../auth/oidc", async (importOriginal) => {
  const original = await importOriginal<typeof import("../auth/oidc")>();
  return { ...original, createManager: () => ({ ...mocks, events: mocks }) };
});
const env = {
  VITE_AUTH_MODE: "cognito",
  VITE_API_BASE_URL:
    "https://offline.execute-api.eu-central-1.amazonaws.com/poc",
  VITE_COGNITO_ISSUER:
    "https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_offline",
  VITE_COGNITO_CLIENT_ID: "offlinepublicclient",
  VITE_COGNITO_DOMAIN: "https://offline.auth.eu-central-1.amazoncognito.com",
  VITE_APP_ORIGIN: "https://poc.example.invalid",
};
const config = readConfig(env, false);
beforeEach(() => {
  vi.clearAllMocks();
  mocks.getUser.mockResolvedValue(null);
  setTokenProvider(() => null);
  window.history.replaceState(null, "", "/");
});
afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  setTokenProvider(() => null);
  window.history.replaceState(null, "", "/");
});
function show() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <AuthGate config={config}>
          <p>Protected dashboard</p>
        </AuthGate>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("deployment configuration and OIDC boundaries", () => {
  it("keeps local development working but rejects production demo fallback", () => {
    expect(readConfig({}, true).mode).toBe("local");
    expect(() => readConfig({}, false)).toThrow("production build");
    expect(() => readConfig({ VITE_AUTH_MODE: "local" }, false)).toThrow(
      "production build",
    );
    expect(readConfig(env, false).mode).toBe("cognito");
  });
  it("rejects insecure/missing/wrong-region configuration", () => {
    for (const change of [
      { VITE_API_BASE_URL: "http://insecure.invalid" },
      { VITE_COGNITO_ISSUER: "" },
      {
        VITE_API_BASE_URL:
          "https://offline.execute-api.us-east-1.amazonaws.com/poc",
      },
    ])
      expect(() => readConfig({ ...env, ...change }, false)).toThrow();
  });
  it("uses Authorization Code with PKCE and memory-only tokens", () => {
    if (config.mode !== "cognito") throw new Error("config");
    const settings = oidcSettings(config);
    expect(settings.response_type).toBe("code");
    expect(settings.disablePKCE).toBe(false);
    expect(settings.scope).toContain("northstar-governance/read");
    expect(settings.client_secret).toBeUndefined();
    expect(settings.automaticSilentRenew).toBe(false);
    expect(settings.redirect_uri).toBe(
      "https://poc.example.invalid/auth/callback",
    );
  });
  it("does not mount protected content or fetch data while signed out", async () => {
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    show();
    await screen.findByRole("button", { name: "Sign in with Cognito" });
    expect(screen.queryByText("Protected dashboard")).not.toBeInTheDocument();
    expect(fetcher).not.toHaveBeenCalled();
  });
  it("publishes only the OIDC-established access token and clears it on expiry", async () => {
    mocks.getUser.mockResolvedValue({
      access_token: "opaque-test-access-value",
      expired: false,
    });
    show();
    await screen.findByText("Protected dashboard");
    expect(accessToken()).toBe("opaque-test-access-value");
    const expired = mocks.addAccessTokenExpired.mock.calls[0][0];
    expired();
    await screen.findByRole("button", { name: "Sign in with Cognito" });
    expect(accessToken()).toBeNull();
  });
  it("handles callback failure without displaying tokens or error details", async () => {
    window.history.replaceState(
      null,
      "",
      "/auth/callback?code=offline-code&state=offline-state",
    );
    setTokenProvider(() => "previous-opaque-test-access");
    mocks.signinRedirectCallback.mockRejectedValue(
      new Error("sensitive upstream detail"),
    );
    show();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Sign-in could not be completed",
    );
    expect(screen.queryByText("Protected dashboard")).not.toBeInTheDocument();
    expect(accessToken()).toBeNull();
  });
  it("uses the absolute deployed API URL with a bearer access token, never the Vite proxy", async () => {
    for (const [key, value] of Object.entries(env)) vi.stubEnv(key, value);
    setTokenProvider(() => "opaque-test-access-value");
    const fetcher = vi
      .fn()
      .mockResolvedValue(
        new Response(JSON.stringify(responses["/api/v1/summary"])),
      );
    vi.stubGlobal("fetch", fetcher);
    await request("/api/v1/summary", new AbortController().signal);
    expect(fetcher).toHaveBeenCalledWith(
      expect.stringContaining(`${env.VITE_API_BASE_URL}/api/v1/summary?`),
      expect.objectContaining({
        credentials: "omit",
        headers: {
          Accept: "application/json",
          Authorization: "Bearer opaque-test-access-value",
        },
      }),
    );
  });
  it("makes no API request when the deployed session is missing", async () => {
    for (const [key, value] of Object.entries(env)) vi.stubEnv(key, value);
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    await expect(
      request("/api/v1/summary", new AbortController().signal),
    ).rejects.toThrow("Sign in with Cognito");
    expect(fetcher).not.toHaveBeenCalled();
  });
  it("completes a successful callback using the OIDC library rather than decoding a browser token", async () => {
    window.history.replaceState(
      null,
      "",
      "/auth/callback?code=offline-code&state=offline-state",
    );
    mocks.signinRedirectCallback.mockResolvedValue({
      access_token: "opaque-test-access-value",
      expired: false,
    });
    mocks.getUser.mockResolvedValue({
      access_token: "opaque-test-access-value",
      expired: false,
    });
    show();
    await waitFor(() =>
      expect(screen.getByText("Protected dashboard")).toBeInTheDocument(),
    );
    expect(mocks.signinRedirectCallback).toHaveBeenCalledTimes(1);
  });
});
