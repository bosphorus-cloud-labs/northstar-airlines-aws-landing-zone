"""Prepare a commit-bound release offline, or execute an explicitly approved DDB operation."""

import argparse
import json
import re
import subprocess
from pathlib import Path

from backend.deployment.dynamodb import DynamoSnapshotRepository
from governance.delivery.publisher import deliver
from governance.simulation import rollout
from governance.simulation.publication import candidate, prepare


def build(run, commit, output):
    if not re.fullmatch(r"[a-f0-9]{40}", commit):
        raise ValueError("An exact reviewed Git commit is required")
    if (
        subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip() != commit
        or subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=all"], text=True
        ).strip()
    ):
        raise ValueError(
            "Release preparation requires a clean checkout of the exact approved commit"
        )
    state = rollout.load(rollout.directory(run))
    snapshot = candidate(state, json.loads((run / "v2.plan.json").read_text()))
    snapshot_id = prepare(snapshot, output.parent)
    package = json.loads((output.parent / f"{snapshot_id}.publication.json").read_text())
    output.write_text(
        json.dumps({"source_commit": commit, "publication": package}, sort_keys=True) + "\n"
    )
    return snapshot_id


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["build", "check", "bootstrap", "publish", "rollback"])
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--run-dir", type=Path, default=Path("artifacts/policy-rollout/ci"))
    parser.add_argument("--release", type=Path, default=Path("artifacts/release/release.json"))
    parser.add_argument("--baseline-id")
    parser.add_argument("--approved-digest")
    parser.add_argument("--generation", type=int)
    parser.add_argument("--operation")
    parser.add_argument("--table")
    parser.add_argument("--confirm-table")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.action == "build":
        args.release.parent.mkdir(parents=True, exist_ok=True)
        print(build(args.run_dir, args.source_commit, args.release))
        return
    if (
        not args.execute
        or args.table != args.confirm_table
        or not re.fullmatch(r"northstar-[a-z0-9-]+", args.table or "")
        or args.generation is None
        or not args.operation
        or not args.baseline_id
        or not args.approved_digest
    ):
        parser.error(
            "Publication requires explicit execution, table confirmation, generation, operation and approved digests"
        )
    package = json.loads(args.release.read_text()) if args.action == "publish" else None
    value = deliver(
        DynamoSnapshotRepository._client(),
        args.table,
        baseline_id=args.baseline_id,
        source_commit=args.source_commit,
        expected_generation=args.generation,
        operation=args.operation,
        action=args.action,
        target_digest=args.approved_digest,
        package=package,
    )
    print(
        json.dumps(
            {
                "simulated": True,
                "current": value["current"],
                "generation": value["generation"],
                "operation": args.operation,
            }
        )
    )


if __name__ == "__main__":
    main()
