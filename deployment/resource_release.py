"""Commit-bound resource release; cloud writes only in the protected publisher job."""

import argparse
import datetime as dt
import json
import os
import re
import subprocess
from pathlib import Path

from compliance_engine.resources import canonical, digest, evaluate, input_digest, load, validate
from deployment import delivery_gate
from deployment.resource_plan import prepare


def checkout(commit):
    if not re.fullmatch(r"[a-f0-9]{40}", commit):
        raise ValueError("Exact source commit required")
    if subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip() != commit:
        raise ValueError("Checkout differs from validated source commit")
    if subprocess.check_output(["git", "status", "--porcelain"], text=True).strip():
        raise ValueError("Release requires a clean checkout")


def check(path, commit):
    checkout(commit)
    release = json.loads(Path(path).read_text())
    if (
        set(release) != {"source_commit", "snapshot_id", "document"}
        or release["source_commit"] != commit
    ):
        raise ValueError("Release commit mismatch")
    document = validate(release["document"])
    if not document["terraform_validation"] or digest(document) != release["snapshot_id"]:
        raise ValueError("Verified Terraform receipt and matching content required")
    if input_digest(document) != input_digest(load()):
        raise ValueError("Release does not match checked-out resource inputs")
    return release


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["build", "check", "publish"])
    parser.add_argument("--source-commit", required=True)
    parser.add_argument(
        "--release", type=Path, default=Path("artifacts/resource-release/release.json")
    )
    parser.add_argument(
        "--run-dir", type=Path, default=Path("artifacts/policy-rollout/resources-ci")
    )
    parser.add_argument("--validation-run-id")
    parser.add_argument("--table")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.action == "build":
        checkout(args.source_commit)
        document, _, _ = prepare(load(), args.run_dir)
        args.release.parent.mkdir(parents=True, exist_ok=True)
        args.release.write_text(
            canonical(
                {
                    "source_commit": args.source_commit,
                    "snapshot_id": digest(document),
                    "document": document,
                }
            )
            + "\n"
        )
        evaluation = evaluate(document)
        report = {
            "source_commit": args.source_commit,
            "simulated": True,
            "real_terraform": "fmt/init/validate/plan and full desired-state parity passed",
            "compliance": evaluation["summary"],
            "findings": evaluation["findings"],
        }
        (args.release.parent / "report.json").write_text(json.dumps(report, indent=2) + "\n")

        def cell(value):
            return str(value).replace("|", "\\|").replace("\n", " ")

        lines = [
            "# Synthetic resource compliance",
            "",
            "Real provider-free Terraform fmt/init/validate/plan and complete assignment parity passed. No AWS provisioning or remediation.",
            "",
            "| Resource | Account | Environment | Control | Desired | Observed | Status | Reason |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        names = {
            resource["id"]: resource["name"] for resource in document["inventory"]["resources"]
        }
        for finding in evaluation["findings"]:
            fields = [
                finding[key]
                for key in [
                    "resource_id",
                    "account_id",
                    "environment",
                    "control",
                    "expected",
                    "observed",
                    "status",
                    "reason",
                ]
            ]
            fields[0] = names[finding["resource_id"]] + " (" + finding["resource_id"] + ")"
            lines.append("| " + " | ".join(cell(value) for value in fields) + " |")
        (args.release.parent / "summary.md").write_text("\n".join(lines) + "\n")
        print(json.dumps({key: value for key, value in report.items() if key != "findings"}))
        return
    release = check(args.release, args.source_commit)
    if args.action == "check":
        print(json.dumps({"source_commit": args.source_commit, "valid": True, "simulated": True}))
        return
    if not args.execute or not re.fullmatch(r"northstar-[a-z0-9-]+", args.table or ""):
        parser.error("Publication requires explicit execution and a NorthStar table")

    def guard():
        delivery_gate.verify(
            args.source_commit, release["snapshot_id"], validation_run_id=args.validation_run_id
        )
        root = f"repos/{delivery_gate.REPOSITORY}"
        if delivery_gate.api(f"{root}/git/ref/heads/main")["object"]["sha"] != args.source_commit:
            raise ValueError("Main advanced; revalidate before publication")

    guard()
    from backend.deployment.dynamodb import DynamoSnapshotRepository
    from governance.delivery.resource_publisher import publish

    result = publish(
        DynamoSnapshotRepository._client(),
        args.table,
        release["document"],
        source_commit=args.source_commit,
        actor=os.environ["GITHUB_ACTOR"],
        operation=f"gh-{os.environ['GITHUB_RUN_ID']}-{os.environ['GITHUB_RUN_ATTEMPT']}",
        published_at=dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        before_write=guard,
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
