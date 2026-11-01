"""Replaceable read-only snapshot access; no cloud SDK or storage mutations."""

from dataclasses import dataclass
from typing import Protocol

from governance.model.evaluate import load_model


@dataclass(frozen=True)
class GovernanceSnapshot:
    fleet: dict
    policy: dict
    environments: list[dict]
    context: dict | None = None


class GovernanceRepository(Protocol):
    def read_snapshot(self) -> GovernanceSnapshot:
        """Return a consistent, request-owned snapshot; future stores must preserve this contract."""
        ...


class FixtureRepository:
    def read_snapshot(self) -> GovernanceSnapshot:
        # load_model parses fresh JSON objects: callers cannot mutate later requests.
        return GovernanceSnapshot(*load_model())
