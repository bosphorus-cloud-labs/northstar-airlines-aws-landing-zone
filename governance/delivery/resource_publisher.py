"""Protected resource publication only. Reverts reuse content and append new audit events."""

import copy
import re

from backend.deployment.resources import (
    FORMAT,
    KEY,
    encode,
    read_catalog,
    read_snapshot,
    validate_catalog,
)
from compliance_engine.resources import canonical, evaluate
from deployment.seed_governance import load


def changes(before, after):
    old = {r["resource_id"]: r for r in evaluate(before)["findings"]} if before else {}
    new = {r["resource_id"]: r for r in evaluate(after)["findings"]}
    names = {r["id"]: r["name"] for r in after["inventory"]["resources"]}
    if before:
        names.update(
            {r["id"]: r["name"] for r in before["inventory"]["resources"] if r["id"] not in names}
        )
    result = []
    for rid in sorted(set(old) | set(new)):
        a, b = old.get(rid), new.get(rid)
        if a != b:
            result.append(
                {
                    "resource_id": rid,
                    "resource_name": names[rid],
                    "control": (b or a)["control"],
                    "before": a["status"] if a else None,
                    "after": b["status"] if b else None,
                    "old_value": a["observed"] if a else None,
                    "new_value": b["observed"] if b else None,
                    "reason": b["reason"]
                    if b
                    else "Resource removed from the synthetic inventory.",
                }
            )
    return result


def publish(
    client,
    table,
    document,
    *,
    source_commit,
    actor,
    operation,
    published_at,
    before_write=lambda: None,
):
    if not re.fullmatch(r"[a-f0-9]{40}", source_commit):
        raise ValueError("Exact source commit required")
    if not document.get("terraform_validation"):
        raise ValueError("Verified Terraform desired-state receipt required for publication")
    prepared = encode(document)
    identifier = prepared["snapshot_id"]
    old = read_catalog(client, table)
    if old and old["current"] == identifier:
        read_snapshot(client, table, identifier)
        return {"status": "unchanged", "generation": old["generation"], "changes": []}
    if old and any(e["operation"] == operation for e in old["history"]):
        raise ValueError("Publication operation conflict")
    previous = read_snapshot(client, table, old["current"]) if old else None
    value = (
        copy.deepcopy(old)
        if old
        else {"format": FORMAT, "simulated": True, "generation": 0, "current": None, "history": []}
    )
    value["generation"] += 1
    event = {
        "operation": operation,
        "generation": value["generation"],
        "source_commit": source_commit,
        "actor": actor,
        "published_at": published_at,
        "previous": value["current"],
        "target": identifier,
        "changes": changes(previous, document),
    }
    value["history"].append(event)
    value["current"] = identifier
    validate_catalog(value)  # Full preflight before any writes, including history budget.
    before_write()
    load(client, table, prepared)
    read_snapshot(client, table, identifier)
    before_write()  # Reject a main revision superseded during approval/publication.
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
            ExpressionAttributeValues={":g": {"N": str(old["generation"])}},
        )
    try:
        client.put_item(**request)
    except client.exceptions.ConditionalCheckFailedException:
        if read_catalog(client, table) != value:
            raise ValueError("Concurrent publication won; Current was not overwritten") from None
    if read_catalog(client, table) != value:
        raise ValueError("Current changed; inspect the audit before retrying")
    return {"status": "published", "generation": value["generation"], "changes": event["changes"]}
