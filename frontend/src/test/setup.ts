import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, beforeEach, vi } from "vitest";
// Amplify injects production Cognito settings into its build environment.
// Each test starts in explicit local mode; authentication tests override it.
beforeEach(() => vi.stubEnv("VITE_AUTH_MODE", "local"));
afterEach(() => {
  cleanup();
  vi.unstubAllEnvs();
});
