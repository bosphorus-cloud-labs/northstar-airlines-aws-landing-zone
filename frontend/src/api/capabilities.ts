export type GovernanceApiMode = "catalog" | "baseline-v1" | "resources";

export function governanceApiMode(): GovernanceApiMode {
  const mode = import.meta.env.VITE_GOVERNANCE_API_MODE ?? "catalog";
  if (mode !== "catalog" && mode !== "baseline-v1" && mode !== "resources")
    throw new Error("Unsupported governance API compatibility mode.");
  return mode;
}
