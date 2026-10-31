"""Read-only simulation evaluator. Invoke with an explicit --at timestamp."""

import argparse
import json
from collections import Counter
from datetime import timedelta

from .contracts import ROOT, timestamp, validate, validate_model


def load_model() -> tuple[dict, dict, list[dict]]:
    def read(path):
        return json.loads(path.read_text())

    return (
        read(ROOT / "mock-data/fleet.v1.json"),
        read(ROOT / "governance/policies/v1.json"),
        [read(p) for p in sorted((ROOT / "governance/environments").glob("*.json"))],
    )


def evaluate(fleet: dict, policy: dict, environments: list[dict], *, at: str) -> list[dict]:
    validate_model(fleet, policy, environments)
    clock = timestamp(at)
    envs = {e["id"]: e for e in environments}
    findings = []
    for account in sorted(fleet["accounts"], key=lambda a: a["id"]):
        if timestamp(account["created_at"]) > clock:
            raise ValueError("Evaluation predates account creation")
        for requirement in sorted(
            envs[account["environment"]]["requirements"], key=lambda r: r["control_id"]
        ):
            cid = requirement["control_id"]
            candidates = [
                e
                for e in fleet["evidence"]
                if e["account_id"] == account["id"] and e["control_id"] == cid
            ]
            past = [e for e in candidates if timestamp(e["observed_at"]) <= clock]
            evidence = max(past, key=lambda e: timestamp(e["observed_at"])) if past else None
            status, reason = "unknown", "future-evidence" if candidates else "missing-evidence"
            if evidence:
                if clock - timestamp(evidence["observed_at"]) > timedelta(
                    hours=requirement["max_age_hours"]
                ):
                    status, reason = "stale", "stale-evidence"
                elif evidence["observed_policy_version"] != account["desired_policy_version"]:
                    reason = "revision-mismatch"
                elif evidence["observed_value"] == requirement["expected"]:
                    status, reason = "compliant", "match"
                else:
                    status, reason = "noncompliant", "mismatch"
            exceptions = []
            for exc in sorted(fleet["exceptions"], key=lambda e: e["id"]):
                if (exc["account_id"], exc["control_id"]) != (account["id"], cid):
                    continue
                state = exc["status"]
                if clock < timestamp(exc["created_at"]) or (
                    exc["approved_at"] and clock < timestamp(exc["approved_at"])
                ):
                    state = "not-yet-active"
                elif clock >= timestamp(exc["expires_at"]):
                    state = "expired"
                elif state == "approved":
                    state = "active"
                exceptions.append({"id": exc["id"], "state": state})
            finding = dict(
                schema_version="1.0.0",
                source="northstar-synthetic-v1",
                simulated=True,
                id=f"finding-{account['id']}-{cid}",
                account_id=account["id"],
                control_id=cid,
                evaluated_at=at,
                policy_version=account["desired_policy_version"],
                desired_value=requirement["expected"],
                observed_value=evidence["observed_value"] if evidence else None,
                evidence_id=evidence["id"] if evidence else None,
                status=status,
                reason=reason,
                exceptions=exceptions,
            )
            validate("finding", finding)
            findings.append(finding)
    return findings


def summarize(findings: list[dict]) -> dict:
    summary = {}
    for aid in sorted({f["account_id"] for f in findings}):
        rows = [f for f in findings if f["account_id"] == aid]
        counts = Counter(f["status"] for f in rows)
        # A known failure dominates; otherwise incomplete evidence prevents compliance.
        overall = next(s for s in ["noncompliant", "stale", "unknown", "compliant"] if counts[s])
        summary[aid] = {
            "status": overall,
            "controls": dict(sorted(counts.items())),
            "exceptions": [e for f in rows for e in f["exceptions"]],
        }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--at", required=True, help="Timezone-aware evaluation timestamp")
    parser.add_argument("--findings", action="store_true", help="Emit full validated findings")
    args = parser.parse_args()
    findings = evaluate(*load_model(), at=args.at)
    print(json.dumps(findings if args.findings else summarize(findings), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
