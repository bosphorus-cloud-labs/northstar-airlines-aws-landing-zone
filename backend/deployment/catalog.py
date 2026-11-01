"""Read-only strongly consistent runtime catalogue; no publication permissions or writes."""

from backend.deployment.dynamodb import DynamoSnapshotRepository
from backend.versions import Version, validate_version
from governance.delivery.catalog import read


class DynamoCatalog:
    follow_current_by_default = True

    def __init__(self, table, baseline_id, client_factory=None):
        self.table, self.baseline_id = table, baseline_id
        self.client_factory = client_factory or DynamoSnapshotRepository._client

    def view(self):
        client = self.client_factory()
        value = read(client, self.table, self.baseline_id)
        if value is None:
            raise ValueError("Approved catalogue is unavailable; bootstrap before enabling reader")
        entries = {}
        for record in value["entries"]:
            d = record["descriptor"]
            v = Version(
                repository=DynamoSnapshotRepository(
                    self.table, d["snapshot_id"], client_factory=self.client_factory
                ),
                **d,
            )
            validate_version(v)
            entries[v.policy_version] = v
        current = next(
            e["descriptor"]["policy_version"]
            for e in value["entries"]
            if e["descriptor"]["snapshot_id"] == value["current"]
        )
        return entries, current, value["history"][-1]["operation"]

    def entries(self):
        return self.view()[0]
