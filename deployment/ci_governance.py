"""Small CI preflight/report helpers. No execution, cloud clients, or policy evaluation copy."""

import argparse
import json
import os
import re
from pathlib import Path

import hcl2
from hcl2.utils import SerializationOptions

from governance.simulation import rollout
from governance.simulation.terraform_plan import verify_plan

ROOT = rollout.ROOT
CONFIGS = ("terraform/simulation", "terraform/modules/simulated_governance")


def preflight(root=ROOT):
    """Reject cloud-capable Terraform before init/plan, including accidental extra files."""
    options = SerializationOptions(
        strip_string_quotes=True, explicit_blocks=False, with_comments=False
    )
    for directory in CONFIGS:
        path = root / directory
        files = sorted([*path.glob("*.tf"), *path.glob("*.tf.json")])
        if files != [path / "main.tf"]:
            raise ValueError("Only the reviewed main.tf files belong to the offline demo")
        config = hcl2.loads(files[0].read_text(), serialization_options=options)
        if set(config) - {"terraform", "variable", "locals", "module", "output"}:
            raise ValueError("Offline Terraform must have no resources, providers or data sources")
        for block in config.get("terraform", []):
            if set(block) - {"required_version"}:
                raise ValueError("No backend/cloud/provider configuration permitted")
        modules = config.get("module", [])
        if directory.endswith("simulated_governance") and modules:
            raise ValueError("The pure module must not import other modules")
        if directory == "terraform/simulation":
            if len(modules) != 1 or set(modules[0]) != {"account_governance"}:
                raise ValueError("Only the existing account-governance module is permitted")
            if modules[0]["account_governance"].get("source") != "../modules/simulated_governance":
                raise ValueError("Remote or POC module sources are forbidden")
    print(
        "Offline Terraform boundary verified: existing module only; no resources/providers/data/backend."
    )


def summary(run):
    state = rollout.load(run)
    verify_plan(json.loads((run / "v2.plan.json").read_text()), state)
    result = rollout.report(state)
    if state["phase"] != "onboarded" or json.loads((run / "report.json").read_text()) != result:
        raise ValueError("Expected a complete, matching simulated rollout report")
    source = (
        "GitHub Actions workflow job"
        if os.environ.get("GITHUB_ACTIONS") == "true"
        else "Local reproduction — NOT a GitHub Actions run"
    )
    sha = os.environ.get("GITHUB_SHA", "")
    revision = (
        sha if re.fullmatch(r"[a-f0-9]{40,64}", sha) else "local working tree (may be uncommitted)"
    )
    counts = result["current"]["finding_counts"]
    return f"""# NorthStar governance validation

Execution: **{source}**
Source revision: `{revision}`
Proposal digest: `{state["proposal_digest"]}`

| Real checks | Scope |
| --- | --- |
| Terraform fmt, init -backend=false, validate, plan | Provider-free `terraform/simulation`; no AWS resources |
| Terraform/Python parity | Full desired settings for ten synthetic accounts |
| Python governance/backend tests | Authentication, contracts, evaluation and version isolation |

## SIMULATED operations and results

Approval, canary, failure/retry, distribution, onboarding and evidence are **simulated**.
Evaluation timestamp: `{result["evaluated_at"]}`. Phase: `{result["phase"]}`.
Final fleet: **{result["current"]["accounts"]} synthetic accounts**.

| Compliant | Noncompliant | Unknown | Stale |
| ---: | ---: | ---: | ---: |
| {counts["compliant"]} | {counts["noncompliant"]} | {counts["unknown"]} | {counts["stale"]} |

Two inactive existing accounts remain deferred; distribution success does not prove compliance.
See `terraform-plan.txt`, `python-tests.txt`, `simulation.txt`, `report.json` and `findings.json` artifacts.

**No Terraform apply/destroy, AWS access, DynamoDB publication or dashboard deployment.**
CI does not update the presenter's local CURRENT marker or the AWS-hosted dashboard.
The local demo independently reuses the same policy/evaluator/module at the checked-out revision.
A reviewed PR is a source-review gate; simulated approval is not production authorization.
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["preflight", "summary"])
    parser.add_argument("--run-dir", type=Path, default=rollout.OUTPUT_ROOT / "ci")
    args = parser.parse_args()
    if args.command == "preflight":
        preflight()
    else:
        run = rollout.directory(args.run_dir)
        output = ROOT / "artifacts/ci/summary.md"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(summary(run))
        print(output)


if __name__ == "__main__":
    main()
