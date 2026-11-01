"""Versioned registry + Current pointer, atomically replaced using generation CAS."""

import copy
import json
import re

from backend.deployment.snapshot import canonical
from backend.versions import Version, validate_version

KEY = {"pk": {"S": "GOVERNANCE#CATALOG"}, "sk": {"S": "STATE"}}
DESCRIPTOR_KEYS = {"policy_version", "profile", "evaluated_at", "snapshot_id", "generator"}


def descriptor(snapshot, snapshot_id):
    context = snapshot.context or {}
    return {
        "policy_version": snapshot.policy["version"],
        "profile": context.get("profile", "v1"),
        "evaluated_at": context.get("evaluated_at", "2026-10-31T12:00:00Z"),
        "snapshot_id": snapshot_id,
        "generator": context.get("generator", "northstar-synthetic-v1"),
    }


def validate(value, baseline_id):
    if (
        set(value) != {"schema_version", "simulated", "generation", "entries", "current", "history"}
        or value["schema_version"] != "1.0.0"
        or value["simulated"] is not True
    ):
        raise ValueError("Invalid registry contract")
    if type(value["generation"]) is not int or value["generation"] < 1:
        raise ValueError("Invalid catalogue generation")
    entries = value["entries"]
    if not isinstance(entries, list) or not 1 <= len(entries) <= 16:
        raise ValueError("Invalid registry size")
    ids, versions = set(), set()
    for entry in entries:
        if (
            set(entry) != {"descriptor", "source_commit"}
            or set(entry["descriptor"]) != DESCRIPTOR_KEYS
        ):
            raise ValueError("Invalid registered revision")
        d = entry["descriptor"]
        validate_version(Version(repository=None, **d))
        if not re.fullmatch(r"[a-f0-9]{64}", d["snapshot_id"] or "") or not re.fullmatch(
            r"[a-f0-9]{40}", entry["source_commit"]
        ):
            raise ValueError("Invalid revision provenance")
        if d["snapshot_id"] in ids or d["policy_version"] in versions:
            raise ValueError("Cannot remap an immutable policy revision")
        ids.add(d["snapshot_id"])
        versions.add(d["policy_version"])
    baseline = next((e for e in entries if e["descriptor"]["policy_version"] == "1.0.0"), None)
    if (
        baseline is None
        or baseline["descriptor"]["snapshot_id"] != baseline_id
        or baseline["descriptor"]["evaluated_at"] != "2026-10-31T12:00:00Z"
        or value["current"] not in ids
    ):
        raise ValueError("Baseline/current registry mismatch")
    history = value["history"]
    if (
        not isinstance(history, list)
        or not 1 <= len(history) <= 128
        or len(history) != value["generation"]
    ):
        raise ValueError("Registry history budget exceeded or invalid generation")
    operations = set()
    previous = None
    for index, event in enumerate(history, 1):
        if (
            set(event)
            != {"operation", "generation", "action", "previous", "target", "approved_commit"}
            or event["generation"] != index
            or event["action"] not in {"bootstrap", "publish", "rollback"}
        ):
            raise ValueError("Invalid promotion audit record")
        if (
            not re.fullmatch(r"[A-Za-z0-9_.:-]{1,100}", event["operation"])
            or event["operation"] in operations
        ):
            raise ValueError("Invalid/duplicate operation ID")
        if (
            event["previous"] != previous
            or event["target"] not in ids
            or not re.fullmatch(r"[a-f0-9]{40}", event["approved_commit"])
        ):
            raise ValueError("Invalid promotion audit chain")
        if index == 1 and event["target"] != baseline_id:
            raise ValueError("Bootstrap must select the pinned V1 baseline")
        if (index == 1) != (event["action"] == "bootstrap"):
            raise ValueError("Bootstrap must be first")
        operations.add(event["operation"])
        previous = event["target"]
    if previous != value["current"] or len(canonical(value).encode()) > 300_000:
        raise ValueError("Invalid current pointer or oversized registry")
    return value


def read(client, table, baseline_id):
    item = client.get_item(TableName=table, Key=KEY, ConsistentRead=True).get("Item")
    if item is None:
        return None
    if set(item) != {"pk", "sk", "generation", "payload"} or {k: item[k] for k in KEY} != KEY:
        raise ValueError("Invalid registry item")
    value = validate(json.loads(item["payload"]["S"]), baseline_id)
    if item["generation"] != {"N": str(value["generation"])}:
        raise ValueError("Registry generation mismatch")
    return value


def promote(
    client, table, baseline_id, entry, *, expected_generation, operation, action, approved_commit
):
    """One conditional write atomically registers history and advances Current. No deletes."""
    old = read(client, table, baseline_id)
    target = entry["descriptor"]["snapshot_id"]
    if old:
        for event in old["history"]:
            if event["operation"] == operation:
                if (
                    event["target"] == target
                    and event["approved_commit"] == approved_commit
                    and event["action"] == action
                    and old["current"] == target
                ):
                    return old
                raise ValueError("Operation ID conflict or a newer promotion already occurred")
    generation = 0 if old is None else old["generation"]
    if generation != expected_generation or (old is None) != (action == "bootstrap"):
        raise ValueError("Stale promotion/rollback generation or invalid bootstrap")
    value = (
        copy.deepcopy(old)
        if old
        else {
            "schema_version": "1.0.0",
            "simulated": True,
            "generation": 0,
            "entries": [],
            "current": None,
            "history": [],
        }
    )
    existing = next((e for e in value["entries"] if e["descriptor"]["snapshot_id"] == target), None)
    if action == "rollback" and existing is None:
        raise ValueError("Rollback requires a registered immutable snapshot")
    if existing is None:
        value["entries"].append(entry)
    elif existing != entry:
        raise ValueError("Cannot overwrite revision provenance")
    value["generation"] += 1
    value["history"].append(
        {
            "operation": operation,
            "generation": value["generation"],
            "action": action,
            "previous": value["current"],
            "target": target,
            "approved_commit": approved_commit,
        }
    )
    value["current"] = target
    validate(value, baseline_id)
    request = {
        "TableName": table,
        "Item": {
            **KEY,
            "generation": {"N": str(value["generation"])},
            "payload": {"S": canonical(value)},
        },
    }
    if old is None:
        request["ConditionExpression"] = "attribute_not_exists(pk) AND attribute_not_exists(sk)"
    else:
        request.update(
            ConditionExpression="#g = :g",
            ExpressionAttributeNames={"#g": "generation"},
            ExpressionAttributeValues={":g": {"N": str(expected_generation)}},
        )
    try:
        client.put_item(**request)
    except client.exceptions.ConditionalCheckFailedException:
        if read(client, table, baseline_id) != value:
            raise ValueError("Concurrent promotion won; Current was not overwritten") from None
    # Strong read-back also handles SDK retry success/conditional failure on a lost response.
    observed = read(client, table, baseline_id)
    if observed != value:
        raise ValueError("Concurrent promotion occurred; inspect Current before retrying")
    return observed
