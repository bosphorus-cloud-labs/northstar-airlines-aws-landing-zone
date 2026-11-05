import { useState } from "react";
import { governanceApiMode } from "./api/capabilities";
import { LegacyConsole } from "./LegacyConsole";
import { ResourceConsole } from "./ResourceConsole";

// Activation is staged after backend and protected data publication are verified.
export function App() {
  const [preview, setPreview] = useState(false);
  return governanceApiMode() === "resources" || preview ? (
    <ResourceConsole />
  ) : (
    <LegacyConsole onPreview={() => setPreview(true)} />
  );
}
