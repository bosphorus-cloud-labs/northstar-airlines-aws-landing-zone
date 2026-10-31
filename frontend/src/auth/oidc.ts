import {
  InMemoryWebStorage,
  UserManager,
  WebStorageStateStore,
  type UserManagerSettings,
} from "oidc-client-ts";
import type { RuntimeConfig } from "./config";
export function oidcSettings(
  config: Extract<RuntimeConfig, { mode: "cognito" }>,
): UserManagerSettings {
  return {
    authority: config.issuer,
    client_id: config.clientId,
    redirect_uri: `${config.appOrigin}/auth/callback`,
    post_logout_redirect_uri: `${config.appOrigin}/`,
    response_type: "code",
    scope: "openid email profile northstar-governance/read",
    disablePKCE: false,
    automaticSilentRenew: false,
    loadUserInfo: false,
    userStore: new WebStorageStateStore({ store: new InMemoryWebStorage() }),
    stateStore: new WebStorageStateStore({
      store: window.sessionStorage,
      prefix: "northstar.pkce.",
    }),
    metadata: {
      issuer: config.issuer,
      authorization_endpoint: `${config.domain}/oauth2/authorize`,
      token_endpoint: `${config.domain}/oauth2/token`,
      jwks_uri: `${config.issuer}/.well-known/jwks.json`,
    },
  };
}
export const createManager = (
  config: Extract<RuntimeConfig, { mode: "cognito" }>,
) => new UserManager(oidcSettings(config));
