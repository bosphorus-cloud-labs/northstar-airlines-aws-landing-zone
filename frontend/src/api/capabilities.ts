export type GovernanceApiMode = "catalog" | "baseline-v1";

export function governanceApiMode(): GovernanceApiMode {
  const mode = import.meta.env.VITE_GOVERNANCE_API_MODE ?? "catalog";
  if (mode !== "catalog" && mode !== "baseline-v1")
    throw new Error("Unsupported governance API compatibility mode.");
  return mode;
}
