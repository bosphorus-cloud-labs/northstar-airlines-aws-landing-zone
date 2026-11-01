"""Test-only deterministic HTTP fixtures, generated from real services/evaluator; never shipped."""

from copy import deepcopy
from types import SimpleNamespace

from backend.deployment.snapshot import digest
from backend.repository import FixtureRepository
from backend.versions import ConfiguredCatalog, Version
from governance.simulation import rollout
from governance.simulation.publication import candidate
from governance.simulation.terraform_plan import desired


def catalogue():
    state = rollout.plan()
    rollout.approve(state, "sim-security-reviewer")
    rollout.rollout(state, fail_account="sim-account-005")
    rollout.rollout(state)
    rollout.onboard(state)
    # Fixture-only semantic projection; this does not claim a Terraform process was executed.
    plan = {
        "planned_values": {"outputs": {"governance_desired": {"value": desired(state, "2.0.0")}}}
    }
    v2 = candidate(state, plan)
    v1 = FixtureRepository().read_snapshot()
    return ConfiguredCatalog(
        {
            "1.0.0": Version(
                "1.0.0",
                "v1",
                rollout.REFERENCE_AT,
                SimpleNamespace(read_snapshot=lambda: deepcopy(v1)),
                digest(v1),
            ),
            "2.0.0": Version(
                "2.0.0",
                "policy-v2",
                v2.context["evaluated_at"],
                SimpleNamespace(read_snapshot=lambda: deepcopy(v2)),
                digest(v2),
                rollout.SOURCE,
            ),
        },
        current_policy_version="2.0.0",
        current_run="run-0001",
    )
