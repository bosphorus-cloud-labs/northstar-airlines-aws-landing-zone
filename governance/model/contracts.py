"""JSON Schema validation plus referential and temporal integrity checks."""

import json
from datetime import datetime
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "governance/contracts/v1.schema.json").read_text())


def timestamp(value: str) -> datetime:
    """Require an explicit timezone; never consult the system clock."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Timestamp must include a timezone")
    return parsed


def validate(kind: str, value: dict) -> None:
    schema = (
        SCHEMA
        if kind == "fleet"
        else {
            "$defs": SCHEMA["$defs"],
            "$ref": "#/$defs/" + kind,
        }
    )
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(value)


def unique(records: list[dict], key: str = "id") -> dict:
    indexed = {r[key]: r for r in records}
    if len(indexed) != len(records):
        raise ValueError(f"Duplicate {key}")
    return indexed


def validate_model(fleet: dict, policy: dict, environments: list[dict]) -> None:
    validate("fleet", fleet)
    validate("policy", policy)
    controls = unique(policy["controls"])
    for env in environments:
        validate("environment", env)
    envs = unique(environments)
    if set(envs) != {"production", "pre-production", "testing", "development"}:
        raise ValueError("Exactly four environment definitions required")
    for env in environments:
        requirements = unique(env["requirements"], "control_id")
        if set(requirements) != set(controls):
            raise ValueError("Environment must cover every policy control exactly once")
        for control_id, expected in policy["baseline_requirements"].items():
            if requirements[control_id]["expected"] != expected:
                raise ValueError("Environment weakens organization-wide baseline")
        if (env["policy_id"], env["policy_version"]) != (policy["id"], policy["version"]):
            raise ValueError("Unresolved environment policy")
    ous = unique(fleet["ous"])
    accounts = unique(fleet["accounts"])
    roots = [ou for ou in ous.values() if ou["parent_id"] is None]
    if len(roots) != 1 or roots[0]["environment"] != "root":
        raise ValueError("One root OU required")
    for ou in ous.values():
        seen = set()
        node = ou
        while node["parent_id"] is not None:
            if node["id"] in seen or node["parent_id"] not in ous:
                raise ValueError("Cyclic or unresolved OU relationship")
            seen.add(node["id"])
            node = ous[node["parent_id"]]
    for account in accounts.values():
        if (
            account["ou_id"] not in ous
            or ous[account["ou_id"]]["environment"] != account["environment"]
        ):
            raise ValueError("Account/environment OU mismatch")
        if account["desired_policy_version"] != envs[account["environment"]]["policy_version"]:
            raise ValueError("Unresolved desired policy revision")
    evidence_keys = set()
    for collection in ["evidence", "deployments", "drift", "exceptions", "events"]:
        unique(fleet[collection])
        for row in fleet[collection]:
            if row["account_id"] not in accounts:
                raise ValueError("Unresolved account reference")
            if "control_id" in row and row["control_id"] not in controls:
                raise ValueError("Unresolved control reference")
            for field in ["observed_at", "started_at", "created_at", "occurred_at"]:
                if field in row and timestamp(row[field]) < timestamp(
                    accounts[row["account_id"]]["created_at"]
                ):
                    raise ValueError("Record predates account")
            if collection == "evidence":
                key = (row["account_id"], row["control_id"], timestamp(row["observed_at"]))
                if key in evidence_keys:
                    raise ValueError("Ambiguous evidence timestamp")
                evidence_keys.add(key)
            if collection == "deployments":
                if row["completed_at"] and timestamp(row["completed_at"]) < timestamp(
                    row["started_at"]
                ):
                    raise ValueError("Deployment ends before start")
                if row["status"] == "pending" and row["completed_at"] is not None:
                    raise ValueError("Pending deployment cannot be completed")
                if row["status"] != "pending" and row["completed_at"] is None:
                    raise ValueError("Terminal deployment needs completion")
                if row["status"] == "failed" and not row["failure_reason"]:
                    raise ValueError("Failed deployment needs reason")
                if row["status"] == "succeeded" and (
                    row["observed_revision"] != row["desired_revision"] or row["failure_reason"]
                ):
                    raise ValueError("Successful deployment needs matching revision and no failure")
            if collection == "exceptions":
                if timestamp(row["expires_at"]) <= timestamp(row["created_at"]):
                    raise ValueError("Invalid exception lifetime")
                if row["status"] == "approved" and not (
                    row["approver"] and row["approval_reference"] and row["approved_at"]
                ):
                    raise ValueError("Approved exception needs approval metadata")
                if row["approved_at"] and not timestamp(row["created_at"]) <= timestamp(
                    row["approved_at"]
                ) < timestamp(row["expires_at"]):
                    raise ValueError("Approval outside exception lifetime")
                if row["status"] != "approved" and row["approved_at"] is not None:
                    raise ValueError("Unapproved exception has approval time")
                if row["status"] == "approved" and not any(
                    a["action"] == "approved"
                    and a["actor"] == row["approver"]
                    and timestamp(a["at"]) == timestamp(row["approved_at"])
                    for a in row["audit"]
                ):
                    raise ValueError("Approval lacks matching audit entry")
                if any(timestamp(a["at"]) < timestamp(row["created_at"]) for a in row["audit"]):
                    raise ValueError("Audit predates exception")
            if collection == "drift":
                expected = (
                    "unknown"
                    if row["observed_value"] is None
                    else "in-sync"
                    if row["observed_value"] == row["desired_value"]
                    else "drifted"
                )
                requirement = next(
                    r
                    for r in envs[accounts[row["account_id"]]["environment"]]["requirements"]
                    if r["control_id"] == row["control_id"]
                )
                if row["status"] != expected or row["desired_value"] != requirement["expected"]:
                    raise ValueError("Inconsistent drift state")
    subjects = {
        key: unique(fleet[key]) for key in ["accounts", "evidence", "deployments", "exceptions"]
    }
    for event in fleet["events"]:
        collection = {
            "account.created": "accounts",
            "evidence.recorded": "evidence",
            "deployment.failed": "deployments",
            "exception.approved": "exceptions",
        }[event["type"]]
        target = subjects[collection].get(event["subject_id"])
        if not target or target.get("account_id", target["id"]) != event["account_id"]:
            raise ValueError("Unresolved event subject")
        if event["type"] == "deployment.failed" and target["status"] != "failed":
            raise ValueError("Failure event requires failed deployment")
        if event["type"] == "exception.approved" and target["status"] != "approved":
            raise ValueError("Approval event requires approved exception")
        subject_time = (
            target.get("approved_at")
            if event["type"] == "exception.approved"
            else target.get("completed_at")
            if event["type"] == "deployment.failed"
            else target.get("observed_at", target.get("created_at"))
        )
        if subject_time and timestamp(event["occurred_at"]) < timestamp(subject_time):
            raise ValueError("Event predates its subject transition")
