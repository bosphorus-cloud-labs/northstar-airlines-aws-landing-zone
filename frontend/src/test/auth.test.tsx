import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { Link, MemoryRouter } from "react-router-dom";
import { AuthGate } from "../auth/AuthGate";
import { readConfig } from "../auth/config";
import { oidcSettings } from "../auth/oidc";
import * as oidc from "../auth/oidc";
import { request } from "../api/client";
import {
  accessToken,
  freshAccessToken,
  rejectSession,
  setTokenProvider,
} from "../auth/session";
import responses from "./api-responses.json";
import { ErrorResponse, User, UserManager } from "oidc-client-ts";
import { resourceState } from "../api/resources";

const mocks = vi.hoisted(() => ({
  getUser: vi.fn(),
  signinSilent: vi.fn(),
  addAccessTokenExpiring: vi.fn(),
  removeAccessTokenExpiring: vi.fn(),
  addUserLoaded: vi.fn(),
  removeUserLoaded: vi.fn(),
  addUserUnloaded: vi.fn(),
  removeUserUnloaded: vi.fn(),
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
  mocks.signinSilent.mockReset().mockResolvedValue(null);
  mocks.removeUser.mockResolvedValue(undefined);
  setTokenProvider(() => null);
  window.history.replaceState(null, "", "/");
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  setTokenProvider(() => null);
  window.history.replaceState(null, "", "/");
});
function show(
  client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity } },
  }),
) {
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <AuthGate config={config}>
          <p>Protected dashboard</p>
          <Link to="/resources">Navigate</Link>
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
    expect(settings.silent_redirect_uri).toBe("");
    expect(settings.accessTokenExpiringNotificationTimeInSeconds).toBe(60);
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

function establishedUser(sequence = 0) {
  const now = Math.floor(Date.now() / 1000);
  return new User({
    access_token: `opaque-unit-access-${sequence}`,
    refresh_token: `opaque-unit-refresh-${sequence}`,
    token_type: "Bearer",
    scope: "openid email profile northstar-governance/read",
    expires_at: now + 600,
    profile: {
      sub: "synthetic-reader",
      iss: env.VITE_COGNITO_ISSUER,
      aud: env.VITE_COGNITO_CLIENT_ID,
      iat: now,
      exp: now + 600,
    },
  });
}

it("keeps a 30-minute session usable with real OIDC timers and refresh-token grants", async () => {
  if (config.mode !== "cognito") throw new Error("config");
  vi.useFakeTimers();
  const manager = new UserManager(oidcSettings(config));
  await manager.storeUser(establishedUser());
  const factory = vi.spyOn(oidc, "createManager").mockReturnValue(manager);
  let sequence = 0;
  const fetcher = vi.fn().mockImplementation(
    async () =>
      new Response(
        JSON.stringify({
          access_token: `opaque-unit-access-${++sequence}`,
          token_type: "Bearer",
          expires_in: 600,
          scope: "openid email profile northstar-governance/read",
        }),
        { headers: { "Content-Type": "application/json" } },
      ),
  );
  vi.stubGlobal("fetch", fetcher);
  try {
    await act(async () => {
      show();
    });
    expect(screen.getByText("Protected dashboard")).toBeInTheDocument();
    for (let renewal = 1; renewal <= 3; renewal++) {
      await act(async () => {
        await vi.advanceTimersByTimeAsync(9 * 60_000);
      });
      expect(accessToken()).toBe(`opaque-unit-access-${renewal}`);
      expect(screen.getByText("Protected dashboard")).toBeInTheDocument();
    }
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3 * 60_000);
    });
    expect(await freshAccessToken()).toBe("opaque-unit-access-3");
    expect(fetcher).toHaveBeenCalledTimes(3);
    for (const [url, args] of fetcher.mock.calls) {
      expect(url).toBe(`${config.domain}/oauth2/token`);
      expect(new URLSearchParams(args.body).get("grant_type")).toBe(
        "refresh_token",
      );
    }
    expect(
      JSON.stringify({ ...localStorage, ...sessionStorage }),
    ).not.toContain("opaque-unit-");
  } finally {
    await act(async () => {
      await manager.removeUser();
    });
    factory.mockRestore();
  }
});

it("deduplicates renewal and replaces the original token used by API callers", async () => {
  vi.useFakeTimers({ toFake: ["Date"] });
  const start = Date.now();
  mocks.getUser.mockResolvedValue(establishedUser());
  let complete!: (user: User) => void;
  mocks.signinSilent.mockReturnValue(
    new Promise<User>((resolve) => {
      complete = resolve;
    }),
  );
  show();
  await screen.findByText("Protected dashboard");
  vi.setSystemTime(start + 11 * 60_000); // Simulates a background tab waking after expiry.
  expect(accessToken()).toBeNull();
  let first!: Promise<string | null>, second!: Promise<string | null>;
  await act(async () => {
    first = freshAccessToken();
    second = freshAccessToken();
  });
  expect(mocks.signinSilent).toHaveBeenCalledTimes(1);
  await act(async () => {
    fireEvent.click(screen.getByRole("link", { name: "Navigate" }));
  });
  expect(mocks.getUser).toHaveBeenCalledTimes(1);
  await act(async () => {
    complete(establishedUser(1));
    await first;
    await second;
  });
  expect(await first).toBe("opaque-unit-access-1");
  expect(await second).toBe("opaque-unit-access-1");
  expect(accessToken()).toBe("opaque-unit-access-1");
});

it("handles revoked refresh tokens safely and never reveals upstream details", async () => {
  vi.useFakeTimers({ toFake: ["Date"] });
  mocks.getUser.mockResolvedValue(establishedUser());
  mocks.signinSilent.mockRejectedValue(
    new ErrorResponse({
      error: "invalid_grant",
      error_description: "private-token-detail",
    }),
  );
  const client = new QueryClient();
  client.setQueryData(["private-evidence"], { synthetic: true });
  show(client);
  await screen.findByText("Protected dashboard");
  await act(async () => {
    mocks.addAccessTokenExpiring.mock.calls[0][0]();
  });
  expect(
    await screen.findByRole("button", { name: "Sign in with Cognito" }),
  ).toBeInTheDocument();
  expect(accessToken()).toBeNull();
  expect(screen.queryByText(/private-token-detail/)).not.toBeInTheDocument();
  expect(mocks.removeUser).toHaveBeenCalled();
  expect(client.getQueryCache().getAll()).toHaveLength(0);
});

it("does not discard a valid session on a transient renewal error but fails closed at expiry", async () => {
  vi.useFakeTimers({ toFake: ["Date"] });
  const start = Date.now();
  mocks.getUser.mockResolvedValue(establishedUser());
  mocks.signinSilent.mockRejectedValue(new TypeError("network detail"));
  show();
  await screen.findByText("Protected dashboard");
  vi.setSystemTime(start + 9 * 60_000);
  await act(async () => {
    mocks.addAccessTokenExpiring.mock.calls[0][0]();
  });
  expect(accessToken()).toBe("opaque-unit-access-0");
  vi.setSystemTime(start + 11 * 60_000);
  await act(async () => {
    await freshAccessToken();
  });
  expect(accessToken()).toBeNull();
  expect(
    await screen.findByRole("button", { name: "Sign in with Cognito" }),
  ).toBeInTheDocument();
});

it("cannot resurrect a rejected session when an in-flight renewal completes", async () => {
  mocks.getUser.mockResolvedValue(establishedUser());
  let complete!: (user: User) => void;
  mocks.signinSilent.mockReturnValue(
    new Promise<User>((resolve) => {
      complete = resolve;
    }),
  );
  show();
  await screen.findByText("Protected dashboard");
  await act(async () => {
    mocks.addAccessTokenExpiring.mock.calls[0][0]();
  });
  await act(async () => {
    rejectSession();
  });
  await act(async () => {
    complete(establishedUser(1));
  });
  expect(accessToken()).toBeNull();
  expect(screen.queryByText("Protected dashboard")).not.toBeInTheDocument();
  expect(mocks.removeUser).toHaveBeenCalled();
});

it("sends refresh-token grants through the real OIDC library without persistent credentials or iframe login", async () => {
  if (config.mode !== "cognito") throw new Error("config");
  const manager = new UserManager(oidcSettings(config));
  await manager.storeUser(establishedUser());
  const fetcher = vi.fn().mockResolvedValue(
    new Response(
      JSON.stringify({
        access_token: "opaque-unit-renewed",
        token_type: "Bearer",
        expires_in: 600,
        scope: "openid email profile northstar-governance/read",
      }),
      { headers: { "Content-Type": "application/json" } },
    ),
  );
  vi.stubGlobal("fetch", fetcher);
  const next = await manager.signinSilent({
    silentRequestTimeoutInSeconds: 10,
  });
  expect(next?.access_token).toBe("opaque-unit-renewed");
  expect(next?.refresh_token).toBe("opaque-unit-refresh-0");
  expect(fetcher).toHaveBeenCalledTimes(1);
  expect(fetcher.mock.calls[0][0]).toBe(`${config.domain}/oauth2/token`);
  const body = new URLSearchParams(fetcher.mock.calls[0][1].body);
  expect(body.get("grant_type")).toBe("refresh_token");
  expect(body.get("client_id")).toBe(config.clientId);
  expect(body.has("client_secret")).toBe(false);
  expect(JSON.stringify({ ...localStorage, ...sessionStorage })).not.toContain(
    "opaque-unit-",
  );
  await manager.removeUser();
});

it.each([
  request,
  (_path: string, signal: AbortSignal) => resourceState(signal),
])(
  "clears Cognito sessions on API 401, not on permission-denied 403",
  async (read) => {
    for (const [key, value] of Object.entries(env)) vi.stubEnv(key, value);
    const rejected = vi.fn();
    const fetcher = vi
      .fn()
      .mockResolvedValue(new Response("", { status: 403 }));
    vi.stubGlobal("fetch", fetcher);
    setTokenProvider(() => "opaque-unit-access", undefined, rejected);
    await expect(
      read("/api/v1/summary", new AbortController().signal),
    ).rejects.toThrow();
    expect(rejected).not.toHaveBeenCalled();
    expect(accessToken()).toBe("opaque-unit-access");
    fetcher.mockResolvedValue(new Response("", { status: 401 }));
    await expect(
      read("/api/v1/summary", new AbortController().signal),
    ).rejects.toThrow();
    expect(rejected).toHaveBeenCalledTimes(1);
    expect(accessToken()).toBeNull();
  },
);
