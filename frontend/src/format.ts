import type { Environment } from "./api/client";

export const environments: Environment[] = [
  "production",
  "pre-production",
  "testing",
  "development",
];
export const statuses = [
  "compliant",
  "noncompliant",
  "unknown",
  "stale",
] as const;
export const controlNames: Record<string, string> = {
  "deployment-approval": "Deployment approval",
  "baseline-encryption": "Baseline encryption",
  "public-access": "Public access restrictions",
  logging: "Audit logging",
  "audit-log-integrity": "Audit log integrity validation",
  "security-monitoring": "Security monitoring",
};
export const label = (value: string) =>
  value.startsWith("sim-")
    ? value
    : value === "aft"
      ? "AFT"
      : value === "pre-production"
        ? "Pre-Production"
        : value === "noncompliant"
          ? "Noncompliant"
          : value.replace(/(^|[ -])\w/g, (char) => char.toUpperCase());
export const date = (value: string | null) =>
  value
    ? new Intl.DateTimeFormat("en-GB", {
        day: "2-digit",
        month: "short",
        year: "numeric",
        timeZone: "UTC",
      }).format(new Date(value))
    : "Not recorded";
export const accountName = (
  accounts: { account: { id: string; name: string } }[],
  id: string,
) => accounts.find((a) => a.account.id === id)?.account.name ?? id;
