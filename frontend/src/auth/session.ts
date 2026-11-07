// Credentials remain in memory. Only the OIDC-established session supplies tokens.
let provider: () => string | null = () => null;
let prepare: (() => Promise<string | null>) | undefined;
let reject: (() => void) | undefined;
export function setTokenProvider(
  next: () => string | null,
  ensureFresh?: () => Promise<string | null>,
  unauthorized?: () => void,
) {
  provider = next;
  prepare = ensureFresh;
  reject = unauthorized;
}
export function accessToken() {
  return provider();
}
export async function freshAccessToken() {
  return prepare ? prepare() : provider();
}
export function rejectSession() {
  reject?.();
  setTokenProvider(() => null);
}
