"""Prepare an immutable synthetic snapshot by default; --execute requires separate authorization."""

import argparse
import json
from collections import Counter
from pathlib import Path

from backend.deployment.snapshot import decode, encode
from backend.repository import FixtureRepository


def prepare():
    snapshot = FixtureRepository().read_snapshot()
    counts = Counter(a["environment"] for a in snapshot.fleet["accounts"])
    if counts != {"production": 3, "pre-production": 2, "testing": 2, "development": 3}:
        raise ValueError("Expected the approved ten-account synthetic fleet")
    version, rows, marker = encode(snapshot)
    decode([*rows, marker], version)
    return {"snapshot_id": version, "rows": rows, "manifest": marker}


def load(client, table_name: str, prepared: dict) -> None:
    """Conditional immutable writes; retries may reuse only byte-identical existing items."""
    for item in [*prepared["rows"], prepared["manifest"]]:
        try:
            client.put_item(
                TableName=table_name,
                Item=item,
                ConditionExpression="attribute_not_exists(pk) AND attribute_not_exists(sk)",
            )
        except client.exceptions.ConditionalCheckFailedException:
            existing = client.get_item(
                TableName=table_name, Key={k: item[k] for k in ["pk", "sk"]}, ConsistentRead=True
            ).get("Item")
            if existing != item:
                raise ValueError("Immutable snapshot conflict; no items were overwritten") from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts/seed/snapshot.json"))
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--table-name")
    parser.add_argument("--confirm-table")
    args = parser.parse_args()
    prepared = prepare()
    if args.execute:
        import re

        if (
            not args.table_name
            or args.confirm_table != args.table_name
            or not re.fullmatch(r"northstar-[a-z0-9-]+", args.table_name)
        ):
            parser.error("Execution requires matching --table-name and --confirm-table")
        # This is the only credential/client boundary. Never reached by default/dry-run/tests.
        import boto3
        from botocore.config import Config

        client = boto3.client(
            "dynamodb",
            region_name="eu-central-1",
            config=Config(retries={"max_attempts": 5, "mode": "standard"}),
        )
        load(client, args.table_name, prepared)
        print("Published immutable synthetic snapshot", prepared["snapshot_id"])
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(prepared, indent=2) + "\n")
        print(
            "Offline only: prepared",
            len(prepared["rows"]),
            "records; snapshot",
            prepared["snapshot_id"],
        )


if __name__ == "__main__":
    main()
