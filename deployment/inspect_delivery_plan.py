"""Review the initial delivery foundation plan without exposing raw plan/state or secrets."""

import argparse
import base64
import hashlib
import json
import os
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    "module.delivery[0].aws_iam_openid_connect_provider.github[0]": ["create"],
    "module.delivery[0].aws_iam_role.publisher": ["create"],
    "module.delivery[0].aws_iam_role_policy.publisher": ["create"],
    "module.compute.aws_iam_role_policy.runtime": ["update"],
    "module.compute.aws_lambda_function.api": ["update"],
}


def check(plan):
    changes = {
        r["address"]: r["change"]
        for r in plan["resource_changes"]
        if r["change"]["actions"] != ["no-op"]
    }
    if {key: value["actions"] for key, value in changes.items()} != EXPECTED:
        raise ValueError("Unexpected foundation scope/replacement; stop before applying")
    function = changes["module.compute.aws_lambda_function.api"]
    if (
        function["before"]["function_name"] != function["after"]["function_name"]
        or function["before"]["role"] != function["after"]["role"]
        or function["before"]["environment"] != function["after"]["environment"]
    ):
        raise ValueError("Do not activate the reader or change runtime identity before bootstrap")
    if function["before"].get("source_code_hash") == function["after"].get("source_code_hash"):
        raise ValueError("The initial foundation plan must actually upgrade the backend package")
    for key, value in function["before"].items():
        if key in {"filename", "source_code_hash"} or function.get("after_unknown", {}).get(key):
            continue
        if function["after"].get(key) != value:
            raise ValueError("Unapproved Lambda configuration change; package upgrade only")
    runtime_before = json.loads(
        changes["module.compute.aws_iam_role_policy.runtime"]["before"]["policy"]
    )
    original_resources = {statement["Resource"] for statement in runtime_before["Statement"]}
    runtime = json.loads(changes["module.compute.aws_iam_role_policy.runtime"]["after"]["policy"])
    actions = {a for statement in runtime["Statement"] for a in statement["Action"]}
    if not actions <= {
        "dynamodb:GetItem",
        "dynamodb:Query",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
    }:
        raise ValueError("Runtime must remain read-only")
    if not {statement["Resource"] for statement in runtime["Statement"]} <= original_resources:
        raise ValueError("Runtime may not access new resource ARNs")
    publisher = json.loads(
        changes["module.delivery[0].aws_iam_role_policy.publisher"]["after"]["policy"]
    )
    if {a for statement in publisher["Statement"] for a in statement["Action"]} != {
        "dynamodb:GetItem",
        "dynamodb:Query",
        "dynamodb:PutItem",
    } or any(statement["Resource"] == "*" for statement in publisher["Statement"]):
        raise ValueError("Publisher must be limited to table item publication")
    return {key: value["actions"] for key, value in changes.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    args = parser.parse_args()
    path = args.plan.resolve()
    if not path.is_relative_to((ROOT / "artifacts").resolve()):
        parser.error("Keep secret-bearing plans in ignored artifacts")
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith("TF_LOG") and k not in {"TF_CLI_ARGS", "TF_CLI_ARGS_show"}
    }
    result = subprocess.run(
        ["terraform", "-chdir=terraform/poc", "show", "-json", str(path)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise RuntimeError("Plan inspection failed; output suppressed")
    plan = json.loads(result.stdout)
    summary = check(plan)
    function = next(
        r["change"]["after"]
        for r in plan["resource_changes"]
        if r["address"] == "module.compute.aws_lambda_function.api"
    )
    package = (ROOT / "terraform/poc" / function["filename"]).resolve()
    if (
        not package.is_relative_to((ROOT / "artifacts").resolve())
        or base64.b64encode(hashlib.sha256(package.read_bytes()).digest()).decode()
        != function["source_code_hash"]
    ):
        raise ValueError("Plan/package hash mismatch or non-artifact package path")
    with zipfile.ZipFile(package) as archive:
        if (
            not {"backend/deployment/catalog.py", "governance/delivery/catalog.py"}
            <= set(archive.namelist())
            or "governance/delivery/publisher.py" in archive.namelist()
        ):
            raise ValueError("Reader package is missing catalogue code or includes the publisher")
    print(json.dumps(summary, indent=2))
    print("Verified 3 creates, 2 updates, 0 destroys/replacements. No apply performed.")


if __name__ == "__main__":
    main()
