"""Pinned immutable partition reads; no scans, writes, credentials, or client creation on import."""

import re

from backend.deployment.snapshot import decode
from backend.repository import GovernanceSnapshot


class DynamoSnapshotRepository:
    def __init__(self, table_name: str, snapshot_id: str, client_factory=None):
        if not re.fullmatch(r"[a-f0-9]{64}", snapshot_id):
            raise ValueError("A SHA-256 snapshot ID is required")
        if not re.fullmatch(r"northstar-[a-z0-9-]+", table_name):
            raise ValueError("Invalid governance table name")
        self.table_name, self.snapshot_id = table_name, snapshot_id
        self.client_factory = client_factory or self._client

    @staticmethod
    def _client():
        import boto3
        from botocore.config import Config

        return boto3.client(
            "dynamodb",
            region_name="eu-central-1",
            config=Config(
                connect_timeout=2, read_timeout=5, retries={"max_attempts": 3, "mode": "standard"}
            ),
        )

    def read_snapshot(self) -> GovernanceSnapshot:
        client = self.client_factory()
        request = {
            "TableName": self.table_name,
            "ConsistentRead": True,
            "KeyConditionExpression": "pk = :pk",
            "ExpressionAttributeValues": {":pk": {"S": f"SNAPSHOT#{self.snapshot_id}"}},
        }
        rows, seen = [], set()
        for _ in range(100):
            response = client.query(**request)
            rows.extend(response.get("Items", []))
            if len(rows) > 10_000:
                raise ValueError("Snapshot exceeds the POC read budget")
            last = response.get("LastEvaluatedKey")
            if not last:
                return decode(rows, self.snapshot_id)
            cursor = repr(sorted(last.items()))
            if cursor in seen:
                raise ValueError("Repeated DynamoDB cursor")
            seen.add(cursor)
            request["ExclusiveStartKey"] = last
        raise ValueError("Snapshot pagination budget exceeded")
