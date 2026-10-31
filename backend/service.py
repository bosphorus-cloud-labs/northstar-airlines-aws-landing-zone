"""Application reads and presentation; compliance rules stay in governance.model."""

from collections import Counter
from dataclasses import dataclass

from governance.model.contracts import timestamp, validate_model
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
    def __init__(self, repository: GovernanceRepository):
        self.repository = repository

    def evaluate(self, at: str) -> Evaluation:
        snapshot = self.repository.read_snapshot()
        # Check input time separately; dataset errors must remain internal errors.
        validate_model(snapshot.fleet, snapshot.policy, snapshot.environments)
        if any(timestamp(a["created_at"]) > timestamp(at) for a in snapshot.fleet["accounts"]):
            raise InvalidEvaluationTime
        findings = evaluate(snapshot.fleet, snapshot.policy, snapshot.environments, at=at)
        return Evaluation(snapshot, findings, summarize(findings), at)
