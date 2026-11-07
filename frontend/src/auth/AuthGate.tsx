import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { ErrorResponse, type User, type UserManager } from "oidc-client-ts";
import type { RuntimeConfig } from "./config";
import { createManager } from "./oidc";
import { setTokenProvider } from "./session";
import { Session } from "./context";
const callbacks = new WeakMap<UserManager, Promise<User>>();
export function AuthGate({
  config,
  children,
}: {
  config: RuntimeConfig;
  children: ReactNode;
}) {
  const manager = useMemo(
    () => (config.mode === "cognito" ? createManager(config) : null),
    [config],
  );
  const [user, setUser] = useState<User | null>(null);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(Boolean(manager));
  const endSession = useRef<() => void>(() => {});
  const client = useQueryClient();
  const navigate = useNavigate();
  const navigateRef = useRef(navigate);
  useEffect(() => {
    navigateRef.current = navigate;
  }, [navigate]);
  useEffect(() => {
    if (!manager) return;
    let active = true;
    let ended = false;
    let current: User | null = null;
    let renewal: Promise<User | null> | null = null;
    const clear = (message = "") => {
      if (!active || ended) return;
      ended = true;
      current = null;
      setTokenProvider(() => null);
      client.clear();
      setUser(null);
      setPending(false);
      setError(message);
      void manager.removeUser().catch(() => {});
    };
    endSession.current = () => clear();
    const token = () =>
      current && !current.expired ? current.access_token : null;
    const install = (next: User) => {
      if (!active || ended) return;
      current = next;
      setTokenProvider(token, ensureFresh, () =>
        clear("Your session was rejected. Please sign in again."),
      );
      setUser(next);
      setPending(false);
      setError("");
    };
    const renew = (): Promise<User | null> => {
      if (renewal) return renewal;
      if (!active || ended || !current?.refresh_token)
        return Promise.resolve(null);
      renewal = (async () => {
        try {
          // The library uses the stored refresh token. No JWT decoding or iframe fallback.
          const next = await manager.signinSilent({
            silentRequestTimeoutInSeconds: 10,
          });
          if (!active || ended) {
            await manager.removeUser().catch(() => {});
            return null;
          }
          if (!next || next.expired) {
            clear("Your session has expired. Please sign in again.");
            return null;
          }
          install(next);
          return next;
        } catch (cause) {
          if (
            active &&
            !ended &&
            (cause instanceof ErrorResponse || current?.expired)
          )
            clear("Your session could not be renewed. Please sign in again.");
          // A transient error does not discard a still-valid token. Expiry/request/focus retries
          // are single-flight; expired credentials are never sent to the governance API.
          return null;
        } finally {
          renewal = null;
        }
      })();
      return renewal;
    };
    async function ensureFresh() {
      if (!active || ended || !current) return null;
      if (
        current.refresh_token &&
        (current.expired || (current.expires_in ?? Infinity) <= 60)
      )
        await renew();
      if (current?.expired)
        clear("Your session has expired. Please sign in again.");
      return token();
    }
    const expiring = () => {
      void renew();
    };
    const expired = () => {
      if (!current?.refresh_token)
        clear("Your session has expired. Please sign in again.");
      else {
        setPending(true);
        void renew().then(() => {
          if (active && !ended) {
            if (token()) setPending(false);
            else clear("Your session has expired. Please sign in again.");
          }
        });
      }
    };
    const resume = () => {
      if (document.visibilityState !== "hidden") void ensureFresh();
    };
    const unloaded = () =>
      clear("Your session has ended. Please sign in again.");
    manager.events.addAccessTokenExpiring(expiring);
    manager.events.addAccessTokenExpired(expired);
    manager.events.addUserLoaded(install);
    manager.events.addUserUnloaded(unloaded);
    window.addEventListener("focus", resume);
    document.addEventListener("visibilitychange", resume);
    const initialize = async () => {
      try {
        let signedIn: User | null;
        if (window.location.pathname === "/auth/callback") {
          let callback = callbacks.get(manager);
          if (!callback) {
            callback = manager.signinRedirectCallback();
            callbacks.set(manager, callback);
          }
          signedIn = await callback;
          if (active) navigateRef.current("/", { replace: true });
        } else signedIn = await manager.getUser();
        if (active && signedIn) {
          current = signedIn;
          if (signedIn.expired) {
            if (signedIn.refresh_token) await renew();
            else clear("Your session has expired. Please sign in again.");
          } else install(signedIn);
        }
      } catch {
        if (active) {
          clear(
            "Sign-in could not be completed. Start a new sign-in; no API access was granted.",
          );
          navigateRef.current("/", { replace: true });
        }
      } finally {
        if (active) setPending(false);
      }
    };
    void initialize();
    return () => {
      active = false;
      ended = true;
      setTokenProvider(() => null);
      manager.events.removeAccessTokenExpiring(expiring);
      manager.events.removeAccessTokenExpired(expired);
      manager.events.removeUserLoaded(install);
      manager.events.removeUserUnloaded(unloaded);
      window.removeEventListener("focus", resume);
      document.removeEventListener("visibilitychange", resume);
    };
  }, [manager, client]);
  if (config.mode === "local") return <>{children}</>;
  const signOut = () => {
    endSession.current();
    const url = new URL(`${config.domain}/logout`);
    url.searchParams.set("client_id", config.clientId);
    url.searchParams.set("logout_uri", `${config.appOrigin}/`);
    window.location.assign(url.href);
  };
  if (pending)
    return (
      <main className="error-state" role="status">
        <h1>
          {user ? "Renewing secure session" : "Completing secure sign-in"}
        </h1>
      </main>
    );
  if (!user)
    return (
      <main className="error-state">
        <p className="simulation-mini">NORTHSTAR AIRLINES · SIMULATED DATA</p>
        <h1>Governance console</h1>
        <p>
          Sign in with your invited Cognito account. Access is read-only and
          requires the governance reader group.
        </p>
        {error && <p role="alert">{error}</p>}
        <button
          className="button primary"
          onClick={() => {
            setError("");
            void manager
              ?.signinRedirect()
              .catch(() =>
                setError("Sign-in is unavailable. Please try again."),
              );
          }}
        >
          Sign in with Cognito
        </button>
      </main>
    );
  return (
    <Session.Provider value={{ mode: "cognito", signOut }}>
      {children}
    </Session.Provider>
  );
}
