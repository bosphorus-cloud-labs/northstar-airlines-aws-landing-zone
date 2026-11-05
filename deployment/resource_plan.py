"""Run the existing provider-free module and verify its complete resource assignments."""

import json
import os
import subprocess
from pathlib import Path

from compliance_engine.resources import (
    ROOT,
    canonical,
    input_digest,
    resource_assignments,
    validate,
)
from deployment.ci_governance import preflight
from governance.simulation import rollout
from governance.simulation.terraform_plan import validate_plan_boundary


def verify(plan, state, document):
    rollout.verify(state)
    validate_plan_boundary(plan)
    expected = {
        "source": "northstar-terraform-resource-desired-v1",
        "simulated": True,
        "input_digest": input_digest(document),
        "accounts": resource_assignments(document),
    }
    actual = plan["planned_values"]["outputs"]["resource_governance_desired"]["value"]
    if canonical(actual) != canonical(expected) or plan.get("terraform_version") != "1.14.6":
        raise ValueError("Real Terraform output differs from the approved resource data/rules")
    return {**expected, "terraform_version": plan["terraform_version"]}


def prepare(document, directory):
    document = validate(document)
    directory = Path(directory).resolve()
    if (
        not directory.is_relative_to((ROOT / "artifacts/policy-rollout").resolve())
        or directory.exists()
    ):
        raise ValueError("Use a fresh ignored resource validation directory")
    preflight()
    directory.mkdir(parents=True)
    state = rollout.plan()
    rollout.save(directory, state)
    variables = {
        "run_directory": str(directory),
        "resource_controls_json": canonical(
            [
                {
                    **{k: v for k, v in rule.items() if k != "expected"},
                    "expected_json": canonical(rule["expected"]),
                }
                for rule in document["controls"]["rules"]
            ]
        ),
        "resource_accounts_json": canonical(document["accounts"]["accounts"]),
        "resource_source_digest": input_digest(document),
    }
    varfile = directory / "resources.tfvars.json"
    varfile.write_text(canonical(variables))
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("AWS_", "TF_VAR_", "TF_CLI_ARGS", "TF_LOG"))
    }
    env.update(
        AWS_EC2_METADATA_DISABLED="true",
        TF_IN_AUTOMATION="1",
        CHECKPOINT_DISABLE="1",
        TF_INPUT="0",
        TF_DATA_DIR=str(directory / "terraform-data"),
    )
    commands = [
        ["terraform", "fmt", "-check", "-recursive", "terraform/simulation"],
        ["terraform", "fmt", "-check", "-recursive", "terraform/modules/simulated_governance"],
        ["terraform", "-chdir=terraform/simulation", "init", "-backend=false", "-input=false"],
        ["terraform", "-chdir=terraform/simulation", "validate"],
        [
            "terraform",
            "-chdir=terraform/simulation",
            "plan",
            "-input=false",
            "-refresh=false",
            "-no-color",
            f"-var-file={varfile}",
            f"-out={directory / 'resource.tfplan'}",
        ],
    ]
    with (directory / "terraform-plan.txt").open("w") as log:
        for command in commands:
            subprocess.run(
                command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, check=True
            )
    result = subprocess.run(
        [
            "terraform",
            "-chdir=terraform/simulation",
            "show",
            "-json",
            str(directory / "resource.tfplan"),
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    plan = json.loads(result.stdout)
    (directory / "resource.plan.json").write_text(canonical(plan))
    document["terraform_validation"] = verify(plan, state, document)
    return validate(document), state, plan
