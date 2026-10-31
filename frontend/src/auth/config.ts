export type RuntimeConfig =
  | { mode: "local"; apiBase: "" }
  | {
      mode: "cognito";
      apiBase: string;
      issuer: string;
      clientId: string;
      domain: string;
      appOrigin: string;
    };
export function readConfig(
  env: Record<string, unknown>,
  development: boolean,
): RuntimeConfig {
  const mode = env.VITE_AUTH_MODE;
  if (development && (mode === undefined || mode === "local"))
    return { mode: "local", apiBase: "" };
  if (mode !== "cognito")
    throw new Error(
      "A production build requires Cognito deployment configuration. Local-demo mode is development-only.",
    );
  const field = (key: string) => {
    const value = env[key];
    if (typeof value !== "string" || !value.trim())
      throw new Error(`Missing public deployment setting: ${key}`);
    return value;
  };
  const https = (key: string) => {
    const value = new URL(field(key));
    if (
      value.protocol !== "https:" ||
      value.username ||
      value.password ||
      value.search ||
      value.hash
    )
      throw new Error(`Invalid HTTPS setting: ${key}`);
    return value;
  };
  const api = https("VITE_API_BASE_URL");
  if (
    !/^[a-z0-9]+\.execute-api\.eu-central-1\.amazonaws\.com$/.test(
      api.hostname,
    ) ||
    api.pathname !== "/poc"
  )
    throw new Error(
      "Use the Frankfurt POC HTTP API URL from Terraform outputs.",
    );
  const issuer = https("VITE_COGNITO_ISSUER");
  if (
    issuer.hostname !== "cognito-idp.eu-central-1.amazonaws.com" ||
    !/^\/eu-central-1_[a-zA-Z0-9]+$/.test(issuer.pathname)
  )
    throw new Error("Invalid Frankfurt Cognito issuer.");
  const domain = https("VITE_COGNITO_DOMAIN");
  if (
    !/^[a-z0-9-]+\.auth\.eu-central-1\.amazoncognito\.com$/.test(
      domain.hostname,
    ) ||
    domain.pathname !== "/"
  )
    throw new Error("Invalid Cognito login domain.");
  const app = https("VITE_APP_ORIGIN");
  if (app.pathname !== "/")
    throw new Error("The SPA origin must not contain a path.");
  const clientId = field("VITE_COGNITO_CLIENT_ID");
  if (!/^[a-zA-Z0-9]{1,128}$/.test(clientId))
    throw new Error("Invalid public SPA client ID.");
  return {
    mode: "cognito",
    apiBase: api.href,
    issuer: issuer.href,
    domain: domain.origin,
    clientId,
    appOrigin: app.origin,
  };
}
export function runtimeConfig() {
  return readConfig(
    import.meta.env,
    import.meta.env.DEV || import.meta.env.MODE === "test",
  );
}
