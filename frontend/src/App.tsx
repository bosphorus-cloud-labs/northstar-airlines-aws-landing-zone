import { governanceApiMode } from "./api/capabilities";
import { LegacyConsole } from "./LegacyConsole";
import { ResourceConsole } from "./ResourceConsole";

// Activation is staged after backend and protected data publication are verified.
export function App() {
  return governanceApiMode() === "resources" ? (
    <ResourceConsole />
  ) : (
    <LegacyConsole />
  );
}
