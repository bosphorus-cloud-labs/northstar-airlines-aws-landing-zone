import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, beforeEach, vi } from "vitest";
// Amplify injects production Cognito settings into its build environment.
// Isolate test defaults from production baseline mode; individual suites override them.
beforeEach(() => {
  vi.stubEnv("VITE_AUTH_MODE", "local");
  vi.stubEnv("VITE_GOVERNANCE_API_MODE", "catalog");
});
afterEach(() => {
  cleanup();
  vi.unstubAllEnvs();
});
