"""Offline immutable snapshot preparation only. There is deliberately no AWS execution path."""

import json
from pathlib import Path

from backend.deployment.snapshot import digest, document, encode, validate_snapshot
from backend.repository import FixtureRepository, GovernanceSnapshot
from governance.simulation import rollout
from governance.simulation.terraform_plan import verify_plan


def candidate(state, terraform_plan):
    rollout.verify(state)
    verify_plan(terraform_plan, state)
    if state["phase"] != "onboarded" or not state["approval"]:
        raise ValueError("Only a fully reviewed and completed demo can be prepared")
    value = state["candidate"]
    snapshot = GovernanceSnapshot(
        **value,
        context={
            "format_version": "1.0.0",
            "profile": "policy-v2",
            "policy_version": value["policy"]["version"],
            "evaluated_at": state["journal"][-1]["at"],
            "generator": rollout.SOURCE,
            "simulated": True,
            "journal": state["journal"],
            "proposal_digest": state["proposal_digest"],
        },
    )
    validate_snapshot(snapshot)
    if digest(snapshot) == digest(FixtureRepository().read_snapshot()):
        raise ValueError("V1 partition cannot be used for V2")
    return snapshot


def immutable_file(path, value):
    """Exclusive creation; accept byte-identical repetition only. Never replace a snapshot."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if path.is_symlink():
        raise ValueError("Immutable file cannot be a symlink")
    try:
        with path.open("x") as output:
            output.write(content)
    except FileExistsError:
        if path.read_text() != content:
            raise ValueError("Immutable artifact conflict") from None


def prepare(snapshot, directory):
    version, rows, marker = encode(snapshot)
    value = {
        "format_version": "1.0.0",
        "simulated": True,
        "snapshot_id": version,
        "policy_version": snapshot.policy["version"],
        "rows": rows,
        "manifest": marker,
    }
    immutable_file(Path(directory) / f"{version}.json", document(snapshot))
    immutable_file(Path(directory) / f"{version}.publication.json", value)
    return version


def validate_package(package, approved_snapshot_id):
    """Pure preflight for a future separately authorized operator; never creates a client."""
    from backend.deployment.snapshot import decode

    if (
        set(package)
        != {"format_version", "simulated", "snapshot_id", "policy_version", "rows", "manifest"}
        or package["format_version"] != "1.0.0"
        or package["simulated"] is not True
        or package["snapshot_id"] != approved_snapshot_id
        or len(package["rows"]) > 10000
    ):
        raise ValueError("Publication package does not match the approved artifact")
    snapshot = decode([*package["rows"], package["manifest"]], approved_snapshot_id)
    if snapshot.context is None or snapshot.policy["version"] != package["policy_version"]:
        raise ValueError(
            "This publication preflight accepts versioned candidates only; V1 is protected"
        )
    if approved_snapshot_id == digest(FixtureRepository().read_snapshot()):
        raise ValueError("V1 publication is prohibited")
    return snapshot
