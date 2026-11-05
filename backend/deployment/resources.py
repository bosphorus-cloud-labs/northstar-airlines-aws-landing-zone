"""Read-only resource snapshots. Catalogue keys are server-controlled, never browser input."""

import copy
import json
import re

from backend.deployment.dynamodb import DynamoSnapshotRepository
from compliance_engine.resources import canonical, digest, evaluate, load, timestamp, validate

KEY = {"pk": {"S": "GOVERNANCE#CATALOG"}, "sk": {"S": "RESOURCE-COMPLIANCE"}}
FORMAT = "resource-compliance/1"


def encode(document):
    document = validate(document)
    identifier = digest(document)
    key = {"S": "SNAPSHOT#" + identifier}
    return {
        "snapshot_id": identifier,
        "rows": [
            {"pk": key, "sk": {"S": "resource-compliance"}, "payload": {"S": canonical(document)}}
        ],
        "manifest": {
            "pk": key,
            "sk": {"S": "MANIFEST"},
            "payload": {"S": canonical({"format": FORMAT, "sha256": identifier, "rows": 1})},
        },
    }


def validate_catalog(value):
    if (
        set(value) != {"format", "simulated", "generation", "current", "history"}
        or value["format"] != FORMAT
        or value["simulated"] is not True
    ):
        raise ValueError("Invalid resource catalogue")
    history = value["history"]
    if (
        type(value["generation"]) is not int
        or not isinstance(history, list)
        or not 1 <= len(history) <= 128
        or value["generation"] != len(history)
    ):
        raise ValueError("Invalid audit generation/history budget")
    previous, operations = None, set()
    for index, event in enumerate(history, 1):
        if (
            set(event)
            != {
                "operation",
                "generation",
                "source_commit",
                "actor",
                "published_at",
                "previous",
                "target",
                "changes",
            }
            or event["generation"] != index
            or event["previous"] != previous
        ):
            raise ValueError("Invalid publication audit chain")
        if (
            not re.fullmatch(r"[a-f0-9]{64}", event["target"])
            or not re.fullmatch(r"[a-f0-9]{40}", event["source_commit"])
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", event["actor"])
            or not re.fullmatch(r"gh-[0-9]+-[0-9]+", event["operation"])
            or event["operation"] in operations
        ):
            raise ValueError("Invalid trusted publication identity")
        timestamp(event["published_at"])
        if not isinstance(event["changes"], list) or len(event["changes"]) > 200:
            raise ValueError("Invalid resource change budget")
        for change in event["changes"]:
            if (
                set(change)
                != {
                    "resource_id",
                    "resource_name",
                    "control",
                    "before",
                    "after",
                    "old_value",
                    "new_value",
                    "reason",
                }
                or change["before"] not in {None, "compliant", "noncompliant", "unknown", "stale"}
                or change["after"] not in {None, "compliant", "noncompliant", "unknown", "stale"}
            ):
                raise ValueError("Invalid audited resource change")
        previous = event["target"]
        operations.add(event["operation"])
    if previous != value["current"] or len(canonical(value).encode()) > 300_000:
        raise ValueError("Resource catalogue integrity/budget failure")
    return value


def read_catalog(client, table):
    item = client.get_item(TableName=table, Key=KEY, ConsistentRead=True).get("Item")
    if item is None:
        return None
    if set(item) != {"pk", "sk", "generation", "payload"} or {k: item[k] for k in KEY} != KEY:
        raise ValueError("Invalid resource catalogue item")
    value = validate_catalog(json.loads(item["payload"]["S"]))
    if item["generation"] != {"N": str(value["generation"])}:
        raise ValueError("Resource generation mismatch")
    return value


def read_snapshot(client, table, identifier):
    if not re.fullmatch(r"[a-f0-9]{64}", identifier):
        raise ValueError("Invalid resource release")
    result = client.query(
        TableName=table,
        ConsistentRead=True,
        KeyConditionExpression="pk = :pk",
        ExpressionAttributeValues={":pk": {"S": "SNAPSHOT#" + identifier}},
    )
    if result.get("LastEvaluatedKey") or len(result.get("Items", [])) != 2:
        raise ValueError("Incomplete or oversized resource snapshot")
    rows = {r["sk"]["S"]: r for r in result["Items"]}
    if set(rows) != {"MANIFEST", "resource-compliance"} or any(
        set(row) != {"pk", "sk", "payload"} or row["pk"] != {"S": "SNAPSHOT#" + identifier}
        for row in rows.values()
    ):
        raise ValueError("Invalid resource rows")
    document = validate(json.loads(rows["resource-compliance"]["payload"]["S"]))
    if digest(document) != identifier or json.loads(rows["MANIFEST"]["payload"]["S"]) != {
        "format": FORMAT,
        "sha256": identifier,
        "rows": 1,
    }:
        raise ValueError("Resource snapshot digest mismatch")
    return document


def view(document, catalog=None):
    result = evaluate(document)
    latest = catalog["history"][-1] if catalog else None
    return {
        "metadata": {
            "api_version": "v1",
            "source": "northstar-synthetic-resources",
            "simulated": True,
            "evaluated_at": result["evaluated_at"],
            "published_at": latest["published_at"] if latest else None,
            "source_commit": latest["source_commit"] if latest else None,
            "workflow_run": latest["operation"] if latest else None,
        },
        "data": {
            **result,
            "terraform_validation": document.get("terraform_validation"),
            "activity": list(reversed(copy.deepcopy(catalog["history"]))) if catalog else [],
        },
    }


class FixtureResources:
    def read(self):
        return view(load())


class DynamoResources:
    def __init__(self, table, client_factory=None):
        if not re.fullmatch(r"northstar-[a-z0-9-]+", table):
            raise ValueError("Invalid resource table")
        self.table = table
        self.client_factory = client_factory or DynamoSnapshotRepository._client

    def read(self):
        client = self.client_factory()
        catalog = read_catalog(client, self.table)
        if catalog is None:
            raise ValueError("Resource data has not been published")
        return view(read_snapshot(client, self.table, catalog["current"]), catalog)
