"""Application reads and presentation; compliance rules stay in governance.model."""

from collections import Counter
from dataclasses import dataclass

from backend.deployment.snapshot import digest, validate_snapshot
from backend.versions import DEMO_AT, UnknownVersion, Version
from governance.model.contracts import timestamp
from governance.model.evaluate import evaluate, summarize

from .repository import GovernanceRepository, GovernanceSnapshot


class AccountNotFound(Exception):
    pass


class InvalidEvaluationTime(Exception):
    pass


@dataclass
class Evaluation:
    snapshot: GovernanceSnapshot
    findings: list[dict]
    accounts: dict
    at: str
    version: Version | None = None
    catalog_view: tuple | None = None

    def require_account(self, account_id: str | None) -> None:
        if account_id is not None and account_id not in self.accounts:
            raise AccountNotFound

    def inventory(self) -> list[dict]:
        return [
            {"account": a, "compliance": self.accounts[a["id"]]}
            for a in sorted(self.snapshot.fleet["accounts"], key=lambda a: a["id"])
        ]

    def account_detail(self, account_id: str) -> dict:
        self.require_account(account_id)
        view = next(a for a in self.inventory() if a["account"]["id"] == account_id)
        return {
            **view,
            "ou": next(
                ou for ou in self.snapshot.fleet["ous"] if ou["id"] == view["account"]["ou_id"]
            ),
            "findings": [f for f in self.findings if f["account_id"] == account_id],
        }

    def summary(self) -> dict:
        return {
            "account_count": len(self.accounts),
            "finding_count": len(self.findings),
            "account_counts": dict(Counter(a["status"] for a in self.accounts.values())),
            "finding_counts": dict(Counter(f["status"] for f in self.findings)),
            "environment_counts": dict(
                Counter(a["environment"] for a in self.snapshot.fleet["accounts"])
            ),
        }

    def records(self, collection: str) -> list[dict]:
        records = sorted(self.snapshot.fleet[collection], key=lambda r: r["id"])
        if collection == "exceptions":
            # Reuse evaluator exception states, including expiry boundaries, without duplicating rules.
            states = {e["id"]: e for f in self.findings for e in f["exceptions"]}
            return [{"exception": e, "expiration_state": states[e["id"]]} for e in records]
        return records

    def filter_records(self, rows: list[dict], *, account_id=None, environment=None) -> list[dict]:
        self.require_account(account_id)
        environments = {a["id"]: a["environment"] for a in self.snapshot.fleet["accounts"]}
        return [
            r
            for r in rows
            if (account_id is None or r.get("exception", r)["account_id"] == account_id)
            and (
                environment is None
                or environments[r.get("exception", r)["account_id"]] == environment
            )
        ]


class GovernanceService:
    def __init__(self, repository: GovernanceRepository, catalog=None):
        self.repository = repository
        self.catalog = catalog

    def versions(self):
        if self.catalog is not None:
            return self.catalog.entries()
        return {
            "1.0.0": Version(
                "1.0.0",
                "v1",
                DEMO_AT,
                self.repository,
                getattr(self.repository, "snapshot_id", None),
            )
        }

    def catalogue(self):
        if self.catalog is not None:
            return self.catalog.view()
        return self.versions(), "1.0.0", None

    def evaluate(self, at: str | None, policy_version: str | None = None) -> Evaluation:
        current_view = None
        if (
            policy_version is None
            and at is None
            and getattr(self.catalog, "follow_current_by_default", False)
        ):
            current_view = self.catalog.view()
            entries, current, _ = current_view
            version = entries[current]
        else:
            version = self.versions().get(policy_version or "1.0.0")
        if version is None:
            raise UnknownVersion
        snapshot = version.repository.read_snapshot()
        profile = validate_snapshot(snapshot)
        if profile != version.profile or snapshot.policy["version"] != version.policy_version:
            raise ValueError("Snapshot selection/profile mismatch")
        if version.snapshot_id and digest(snapshot) != version.snapshot_id:
            raise ValueError("Snapshot selection digest mismatch")
        if snapshot.context and (
            snapshot.context["evaluated_at"] != version.evaluated_at
            or snapshot.context["generator"] != version.generator
        ):
            raise ValueError("Snapshot reference metadata mismatch")
        at = at or version.evaluated_at
        if any(timestamp(a["created_at"]) > timestamp(at) for a in snapshot.fleet["accounts"]):
            raise InvalidEvaluationTime
        findings = evaluate(
            snapshot.fleet, snapshot.policy, snapshot.environments, at=at, profile=profile
        )
        return Evaluation(
            snapshot,
            findings,
            summarize(findings),
            at,
            version if policy_version is not None or current_view is not None else None,
            current_view,
        )
