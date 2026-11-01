"""Deterministic immutable snapshot encoding, shared by offline seed preparation and reads."""

import hashlib
import json

from backend.repository import GovernanceSnapshot
from governance.model.contracts import timestamp, validate_model


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def document(snapshot: GovernanceSnapshot) -> dict:
    value = {
        "fleet": snapshot.fleet,
        "policy": snapshot.policy,
        "environments": snapshot.environments,
    }
    if snapshot.context is not None:
        value["context"] = snapshot.context
    return value


def validate_snapshot(snapshot):
    context = snapshot.context
    profile = "v1" if context is None else context["profile"]
    if context is not None:
        if (
            set(context)
            != {
                "format_version",
                "profile",
                "policy_version",
                "evaluated_at",
                "generator",
                "simulated",
                "journal",
                "proposal_digest",
            }
            or context["format_version"] != "1.0.0"
            or context["simulated"] is not True
            or context["policy_version"] != snapshot.policy["version"]
            or context["generator"] != "northstar-policy-rollout-v1"
            or profile != "policy-v2"
        ):
            raise ValueError("Invalid versioned snapshot context")
        clock = timestamp(context["evaluated_at"])
        if any(
            timestamp(e["at"]) > clock or e.get("simulated") is not True for e in context["journal"]
        ):
            raise ValueError("Invalid simulated journal")
    validate_model(snapshot.fleet, snapshot.policy, snapshot.environments, profile=profile)
    return profile


def from_document(value):
    if set(value) not in (
        {"fleet", "policy", "environments"},
        {"fleet", "policy", "environments", "context"},
    ):
        raise ValueError("Invalid snapshot document")
    result = GovernanceSnapshot(**value)
    validate_snapshot(result)
    return result


def digest(snapshot: GovernanceSnapshot) -> str:
    return hashlib.sha256(canonical(document(snapshot)).encode()).hexdigest()


def encode(snapshot: GovernanceSnapshot) -> tuple[str, list[dict], dict]:
    validate_snapshot(snapshot)
    version = digest(snapshot)
    key = f"SNAPSHOT#{version}"
    rows = []
    for collection, values in snapshot.fleet.items():
        if collection == "schema_version":
            continue
        for index, record in enumerate(values):
            rows.append(
                {
                    "pk": {"S": key},
                    "sk": {"S": f"fleet/{collection}/{index:06}"},
                    "payload": {"S": canonical(record)},
                }
            )
    rows.append(
        {"pk": {"S": key}, "sk": {"S": "policy"}, "payload": {"S": canonical(snapshot.policy)}}
    )
    for index, env in enumerate(snapshot.environments):
        rows.append(
            {
                "pk": {"S": key},
                "sk": {"S": f"environment/{index:06}"},
                "payload": {"S": canonical(env)},
            }
        )
    if snapshot.context is not None:
        rows.append(
            {
                "pk": {"S": key},
                "sk": {"S": "context"},
                "payload": {"S": canonical(snapshot.context)},
            }
        )
    manifest = {
        "schema_version": "1.0.0",
        "simulated": True,
        "source": "northstar-synthetic-v1",
        "sha256": version,
        "item_count": len(rows),
        "fleet_schema_version": snapshot.fleet["schema_version"],
    }
    marker = {"pk": {"S": key}, "sk": {"S": "MANIFEST"}, "payload": {"S": canonical(manifest)}}
    for row in [*rows, marker]:
        if len(canonical(row).encode()) > 350_000:
            raise ValueError("Snapshot item exceeds the conservative DynamoDB item budget")
    return version, rows, marker


def decode(rows: list[dict], expected: str) -> GovernanceSnapshot:
    indexed = {r["sk"]["S"]: r for r in rows}
    if len(indexed) != len(rows) or any(r["pk"]["S"] != f"SNAPSHOT#{expected}" for r in rows):
        raise ValueError("Invalid snapshot keys")
    manifest = json.loads(indexed["MANIFEST"]["payload"]["S"])
    if (
        manifest.get("sha256") != expected
        or manifest.get("simulated") is not True
        or manifest.get("source") != "northstar-synthetic-v1"
        or manifest.get("schema_version") != "1.0.0"
        or manifest.get("item_count") != len(rows) - 1
    ):
        raise ValueError("Incomplete or invalid snapshot manifest")
    fleet = {
        name: []
        for name in ["ous", "accounts", "evidence", "deployments", "drift", "exceptions", "events"]
    }
    fleet["schema_version"] = manifest["fleet_schema_version"]
    envs = []
    policy = None
    context = None
    for key, row in sorted(indexed.items()):
        value = json.loads(row["payload"]["S"])
        if key == "MANIFEST":
            continue
        if key == "context":
            context = value
        elif key == "policy":
            policy = value
        elif key.startswith("environment/"):
            envs.append(value)
        elif key.startswith("fleet/"):
            _, collection, _ = key.split("/")
            fleet[collection].append(value)
        else:
            raise ValueError("Unexpected snapshot item")
    snapshot = GovernanceSnapshot(fleet, policy, envs, context)
    validate_snapshot(snapshot)
    if digest(snapshot) != expected:
        raise ValueError("Snapshot digest mismatch")
    return snapshot
