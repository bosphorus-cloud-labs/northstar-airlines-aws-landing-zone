import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import type { User, UserManager } from "oidc-client-ts";
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
  const client = useQueryClient();
  const navigate = useNavigate();
  useEffect(() => {
    if (!manager) return;
    let active = true;
    const expire = () => {
      setTokenProvider(() => null);
      client.clear();
      setUser(null);
    };
    manager.events.addAccessTokenExpired(expire);
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
          if (active) navigate("/", { replace: true });
        } else signedIn = await manager.getUser();
        if (active && signedIn && !signedIn.expired) {
          setTokenProvider(() =>
            signedIn && !signedIn.expired ? signedIn.access_token : null,
          );
          setUser(signedIn);
        }
      } catch {
        if (active) {
          setTokenProvider(() => null);
          client.clear();
          setUser(null);
          setError(
            "Sign-in could not be completed. Start a new sign-in; no API access was granted.",
          );
          navigate("/", { replace: true });
        }
      } finally {
        if (active) setPending(false);
      }
    };
    void initialize();
    return () => {
      active = false;
      manager.events.removeAccessTokenExpired(expire);
    };
  }, [manager, client, navigate]);
  if (config.mode === "local") return <>{children}</>;
  const signOut = () => {
    setTokenProvider(() => null);
    client.clear();
    setUser(null);
    void manager?.removeUser();
    const url = new URL(`${config.domain}/logout`);
    url.searchParams.set("client_id", config.clientId);
    url.searchParams.set("logout_uri", `${config.appOrigin}/`);
    window.location.assign(url.href);
  };
  if (pending)
    return (
      <main className="error-state" role="status">
        <h1>Completing secure sign-in</h1>
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
