"""Reproduce the 100-account synthetic extension; no AWS operations or generated evidence claims."""

import argparse
import copy
import json
from pathlib import Path

from compliance_engine.resources import ROOT, load, validate


def extend(document):
    """Retain the original ten records verbatim; generate ninety deterministic observations."""
    result = copy.deepcopy(document)
    result["terraform_validation"] = None
    accounts = [a for a in result["accounts"]["accounts"] if int(a["id"].rsplit("-", 1)[1]) <= 10]
    original_ids = {a["id"] for a in accounts}
    if original_ids != {f"sim-account-{i:03}" for i in range(1, 11)}:
        raise ValueError("The original ten accounts must be present")
    resources = [r for r in result["inventory"]["resources"] if r["account_id"] in original_ids]
    workloads = [
        "Reservations",
        "Flight Operations",
        "Baggage",
        "Cargo",
        "Crew",
        "Loyalty",
        "Finance",
        "Airport Services",
        "Customer Care",
    ]
    index = 11
    for env, added in [
        ("production", 27),
        ("pre-production", 18),
        ("testing", 18),
        ("development", 27),
    ]:
        for offset in range(added):
            number = f"{index:03}"
            workload = workloads[offset % len(workloads)]
            accounts.append(
                {
                    "id": f"sim-account-{number}",
                    "name": f"NorthStar {workload} {env} {number}",
                    "environment": env,
                    "ou_id": f"sim-ou-{env}",
                    "lifecycle_status": "onboarding" if index % 23 == 0 else "active",
                }
            )
            kind, resource_type, config = [
                (
                    "ec2",
                    "ec2_instance",
                    {"metadata_options": {"http_endpoint": "enabled", "http_tokens": "required"}},
                ),
                ("s3", "s3_bucket", {"public_access_blocked": True}),
                ("ebs", "ebs_volume", {"encrypted": True}),
            ][(index - 11) % 3]
            # Each environment contains valid failures, missing observations and stale evidence.
            scenario = offset % 10
            observed = (
                "2026-10-20T12:00:00Z" if scenario == 9 else result["inventory"]["evaluated_at"]
            )
            if scenario in {7, 8}:
                value = None if scenario == 8 else ("optional" if kind == "ec2" else False)
                if kind == "ec2":
                    config["metadata_options"]["http_tokens"] = value
                else:
                    config[next(iter(config))] = value
            resources.append(
                {
                    "id": f"sim-{kind}-{number}",
                    "name": f"{workload} {kind.upper()} {number}",
                    "account_id": f"sim-account-{number}",
                    "environment": env,
                    "region": "eu-central-1",
                    "resource_type": resource_type,
                    "source": "northstar-synthetic-resources",
                    "simulated": True,
                    "observed_at": observed,
                    "configuration": config,
                }
            )
            index += 1
    result["accounts"]["accounts"] = accounts
    result["inventory"]["resources"] = resources
    return validate(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-directory", type=Path, default=ROOT / "artifacts/synthetic-fleet")
    args = parser.parse_args()
    document = extend(load())
    args.output_directory.mkdir(parents=True, exist_ok=True)
    for name, key in [("accounts.json", "accounts"), ("resources.json", "inventory")]:
        (args.output_directory / name).write_text(json.dumps(document[key], indent=2) + "\n")
    print("Prepared 100 synthetic accounts locally. No AWS operations or publication performed.")


if __name__ == "__main__":
    main()
