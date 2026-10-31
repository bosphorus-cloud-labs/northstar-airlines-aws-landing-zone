"""Compare a provider-free Terraform plan to the CLI's frozen proposal; no writes or execution."""

import argparse
import json
from pathlib import Path

from jsonschema import ValidationError

from governance.simulation import rollout


def desired(state, policy_version):
    rollout.verify(state)
    proposal = state["proposal"]
    if policy_version == "1.0.0":
        policy = proposal["baseline"]["policy"]
        envs = proposal["baseline"]["environments"]
    elif policy_version == "2.0.0":
        policy, envs = proposal["policy"], proposal["environments"]
    else:
        raise ValueError("Unsupported policy revision")
    environments = {e["id"]: e for e in envs}
    controls = {c["id"]: c for c in policy["controls"]}
    accounts = {}
    for account in proposal["baseline"]["fleet"]["accounts"]:
        env = environments[account["environment"]]
        accounts[account["id"]] = {
            "account_id": account["id"],
            "environment": account["environment"],
            "ou_id": account["ou_id"],
            "lifecycle_status": account["lifecycle_status"],
            "policy_id": policy["id"],
            "desired_policy_version": policy["version"],
            "baseline_requirements": policy["baseline_requirements"],
            "requirements": {
                r["control_id"]: {
                    "expected": r["expected"],
                    "max_age_hours": r["max_age_hours"],
                    "category": controls[r["control_id"]]["category"],
                }
                for r in env["requirements"]
            },
        }
    return {
        "source": "northstar-terraform-desired-v1",
        "simulated": True,
        "proposal_digest": state["proposal_digest"],
        "policy_version": policy_version,
        "accounts": accounts,
    }


def no_resources(module):
    if not isinstance(module, dict):
        raise ValueError("Invalid Terraform module structure")
    if module.get("resources"):
        raise ValueError("This demonstration must contain no resources or data sources")
    for child in module.get("child_modules", []):
        no_resources(child)
    for child in module.get("module_calls", {}).values():
        no_resources(child.get("module", {}))


def verify_plan(plan, state, policy_version="2.0.0"):
    if not isinstance(plan, dict):
        raise ValueError("Invalid Terraform plan structure")
    if (
        plan.get("errored") is True
        or plan.get("complete") is False
        or plan.get("resource_changes")
        or plan.get("resource_drift")
        or plan.get("configuration", {}).get("provider_config")
    ):
        raise ValueError("Expected a complete, successful provider-free output-only plan")
    no_resources(plan.get("planned_values", {}).get("root_module", {}))
    no_resources(plan.get("configuration", {}).get("root_module", {}))
    actual = plan["planned_values"]["outputs"]["governance_desired"]["value"]
    expected = desired(state, policy_version)
    # Canonical JSON also distinguishes true from 1, unlike Python dict equality.
    if rollout.canonical(actual) != rollout.canonical(expected):
        raise ValueError("Terraform desired configuration does not match the frozen CLI proposal")
    return expected


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=rollout.OUTPUT_ROOT / "demo")
    parser.add_argument("--plan-json", type=Path, required=True)
    parser.add_argument("--policy-version", choices=["1.0.0", "2.0.0"], default="2.0.0")
    args = parser.parse_args(argv)
    try:
        path = args.plan_json.resolve()
        if not path.is_relative_to(rollout.OUTPUT_ROOT.resolve()) or not path.is_file():
            raise ValueError("Read only a saved JSON plan below artifacts/policy-rollout/")
        state = rollout.load(rollout.directory(args.run_dir))
        result = verify_plan(json.loads(path.read_text()), state, args.policy_version)
        print(
            f"REAL TERRAFORM PLAN VERIFIED: policy {args.policy_version}, {len(result['accounts'])} synthetic desired assignments"
        )
        print("Proposal:", result["proposal_digest"])
        for env in ["production", "pre-production", "testing", "development"]:
            account = next(a for a in result["accounts"].values() if a["environment"] == env)
            approval = account["requirements"]["deployment-approval"]
            print(
                f"{env}: {len(account['requirements'])} controls; approval={approval['expected']}; evidence age={approval['max_age_hours']}h"
            )
        print(
            "NO RESOURCES / NO DEPLOYMENT / NO COMPLIANCE MEASUREMENT. Python rollout remains simulated."
        )
        return 0
    except (ValueError, KeyError, TypeError, OSError, ValidationError):
        print(
            "Terraform/CLI comparison rejected. Check the saved plan, run state and requested policy version."
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
