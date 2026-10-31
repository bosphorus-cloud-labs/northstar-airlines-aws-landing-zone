// Access tokens are memory-only. This is populated by the OIDC callback, not by arbitrary input.
let provider: () => string | null = () => null;
export function setTokenProvider(next: () => string | null) {
  provider = next;
}
export function accessToken() {
  return provider();
}
