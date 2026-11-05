"""Real conditional synthetic-data publication. No client construction or AWS calls on import."""

import re

from backend.deployment.dynamodb import DynamoSnapshotRepository
from backend.deployment.snapshot import digest
from backend.repository import FixtureRepository
from deployment.seed_governance import load
from governance.delivery import catalog
from governance.simulation.publication import validate_package


def verify(client, table, snapshot_id):
    return DynamoSnapshotRepository(
        table, snapshot_id, client_factory=lambda: client
    ).read_snapshot()


def deliver(
    client,
    table,
    *,
    baseline_id,
    source_commit,
    expected_generation,
    operation,
    action,
    target_digest,
    package=None,
):
    if (
        not re.fullmatch(r"[a-f0-9]{40}", source_commit)
        or not re.fullmatch(r"[a-f0-9]{64}", target_digest)
        or type(expected_generation) is not int
        or expected_generation < 0
    ):
        raise ValueError("Invalid reviewed commit, digest or generation")
    if baseline_id != digest(FixtureRepository().read_snapshot()):
        raise ValueError("Publisher baseline must match the reviewed immutable V1 source")
    previous = catalog.read(client, table, baseline_id)
    replay = (
        previous is not None
        and previous["current"] == target_digest
        and any(
            e["operation"] == operation
            and e["target"] == target_digest
            and e["action"] == action
            and e["approved_commit"] == source_commit
            for e in previous["history"]
        )
    )
    if not replay and (
        (previous is None) != (action == "bootstrap")
        or (previous["generation"] if previous else 0) != expected_generation
    ):
        raise ValueError("Stale generation or missing bootstrap; no publication attempted")
    if action == "bootstrap":
        if target_digest != baseline_id:
            raise ValueError("Bootstrap must preserve the deployed baseline")
        snapshot = verify(client, table, baseline_id)
        entry = {
            "descriptor": catalog.descriptor(snapshot, baseline_id),
            "source_commit": source_commit,
        }
    elif action == "publish":
        if package is None or package.get("source_commit") != source_commit:
            raise ValueError("Publication must be bound to the approved source commit")
        if set(package) != {"source_commit", "publication"}:
            raise ValueError("Invalid release envelope")
        prepared = package["publication"]
        snapshot = validate_package(prepared, target_digest)
        if target_digest == baseline_id:
            raise ValueError("V1 is read-only")
        # Validate *before* any writes, then manifest-last conditional/idempotent insertion.
        load(client, table, prepared)
        observed = verify(client, table, target_digest)
        if digest(observed) != digest(snapshot):
            raise ValueError("Read-back verification failed; Current unchanged")
        entry = {
            "descriptor": catalog.descriptor(observed, target_digest),
            "source_commit": source_commit,
        }
    elif action == "rollback":
        value = catalog.read(client, table, baseline_id)
        if value is None:
            raise ValueError("Registry is not bootstrapped")
        entry = next(
            (e for e in value["entries"] if e["descriptor"]["snapshot_id"] == target_digest), None
        )
        if entry is None:
            raise ValueError("Unknown rollback target")
        snapshot = verify(client, table, target_digest)
        if catalog.descriptor(snapshot, target_digest) != entry["descriptor"]:
            raise ValueError("Rollback descriptor mismatch")
    else:
        raise ValueError("Unsupported publication operation")
    return catalog.promote(
        client,
        table,
        baseline_id,
        entry,
        expected_generation=expected_generation,
        operation=operation,
        action=action,
        approved_commit=source_commit,
    )
