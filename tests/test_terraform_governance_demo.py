"""Provider-free real Terraform planning and its binding to the simulated rollout proposal."""

import copy
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from governance.simulation import rollout
from governance.simulation.terraform_plan import desired, main, verify_plan

ROOT = Path(__file__).resolve().parents[1]


class TerraformGovernanceTests(unittest.TestCase):
    def setUp(self):
        self.state = rollout.plan()
        self.plan = {
            "planned_values": {
                "outputs": {"governance_desired": {"value": desired(self.state, "2.0.0")}}
            },
            "configuration": {"root_module": {}},
        }

    def test_projection_and_full_comparison_preserve_environment_differences(self):
        with patch("boto3.client", side_effect=AssertionError("AWS forbidden")):
            result = verify_plan(self.plan, self.state)
        self.assertEqual(len(result["accounts"]), 10)
        for version, size in [("1.0.0", 5), ("2.0.0", 6)]:
            values = desired(self.state, version)["accounts"]
            for account in values.values():
                self.assertEqual(len(account["requirements"]), size)
                self.assertEqual(account["desired_policy_version"], version)
                requirement = account["requirements"]["deployment-approval"]
                self.assertEqual(
                    requirement["expected"],
                    account["environment"] in {"production", "pre-production"},
                )
                self.assertEqual(
                    requirement["max_age_hours"],
                    {"production": 24, "pre-production": 48, "testing": 72, "development": 168}[
                        account["environment"]
                    ],
                )

    def test_mismatch_wrong_version_cloud_resources_or_provider_are_rejected(self):
        for mutate in [
            lambda p: p["planned_values"]["outputs"]["governance_desired"]["value"].update(
                proposal_digest="changed"
            ),
            lambda p: p["planned_values"]["outputs"]["governance_desired"]["value"]["accounts"].pop(
                "sim-account-001"
            ),
            lambda p: p["planned_values"]["outputs"]["governance_desired"]["value"]["accounts"][
                "sim-account-001"
            ]["requirements"]["logging"].update(expected=False),
            lambda p: p.update(resource_changes=[{"change": {"actions": ["create"]}}]),
            lambda p: p["configuration"].update(provider_config={"aws": {}}),
            lambda p: p["configuration"]["root_module"].update(
                module_calls={"hidden": {"module": {"resources": [{"type": "aws_s3_bucket"}]}}}
            ),
            lambda p: p.update(complete=False),
        ]:
            plan = copy.deepcopy(self.plan)
            mutate(plan)
            with self.assertRaises(ValueError):
                verify_plan(plan, self.state)
        with self.assertRaises(ValueError):
            verify_plan(self.plan, self.state, "1.0.0")

    def test_checker_is_read_only_and_does_not_advance_or_approve_rollout(self):
        with (
            tempfile.TemporaryDirectory() as temp,
            patch.object(rollout, "OUTPUT_ROOT", Path(temp)),
            redirect_stdout(io.StringIO()) as output,
        ):
            path = Path(temp) / "run"
            rollout.save(path, self.state)
            plan_file = path / "terraform.plan.json"
            plan_file.write_text(json.dumps(self.plan))
            before = (path / "state.json").read_bytes()
            self.assertEqual(main(["--run-dir", str(path), "--plan-json", str(plan_file)]), 0)
            self.assertEqual(before, (path / "state.json").read_bytes())
            self.assertEqual(rollout.load(path)["phase"], "planned")
            self.assertIn("REAL TERRAFORM PLAN VERIFIED", output.getvalue())
            with self.assertRaises(ValueError):
                rollout.rollout(self.state)

    @unittest.skipUnless(
        shutil.which("terraform"), "Terraform >=1.14 required for real offline plans"
    )
    def test_real_init_validate_v1_v2_plans_and_baseline_precondition(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = root / "terraform/simulation"
            shutil.copytree(
                ROOT / "terraform/simulation",
                config,
                ignore=shutil.ignore_patterns(".terraform", "*.tfstate*", "*.tfplan*"),
            )
            shutil.copytree(
                ROOT / "terraform/modules/simulated_governance",
                root / "terraform/modules/simulated_governance",
            )
            run = root / "run"
            rollout.save(run, self.state)
            env = {**os.environ, "CHECKPOINT_DISABLE": "1", "TF_IN_AUTOMATION": "1"}

            def terraform(*args, expected=0):
                command = ["terraform", f"-chdir={config}", *args]
                result = subprocess.run(
                    command, capture_output=True, text=True, env=env, timeout=30
                )
                self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
                return result.stdout + result.stderr if expected else result.stdout

            terraform("fmt", "-check", "-recursive")
            terraform("init", "-backend=false", "-input=false", "-no-color")
            terraform("validate", "-no-color")
            for version in ["1.0.0", "2.0.0"]:
                artifact = root / f"{version}.tfplan"
                terraform(
                    "plan",
                    "-input=false",
                    "-refresh=false",
                    "-no-color",
                    f"-var=run_directory={run}",
                    f"-var=policy_version={version}",
                    f"-out={artifact}",
                )
                plan = json.loads(terraform("show", "-json", str(artifact)))
                self.assertEqual(
                    verify_plan(plan, self.state, version), desired(self.state, version)
                )
                self.assertFalse(plan.get("resource_changes"))
            # Terraform itself rejects a weakened environment, independently of Python comparison.
            changed = copy.deepcopy(self.state)
            env_config = changed["proposal"]["environments"][0]
            next(r for r in env_config["requirements"] if r["control_id"] == "logging")[
                "expected"
            ] = False
            (run / "state.json").write_text(json.dumps({"payload": changed}))
            output = terraform(
                "plan",
                "-input=false",
                "-refresh=false",
                "-no-color",
                f"-var=run_directory={run}",
                expected=1,
            )
            self.assertIn("preserve the central baseline", " ".join(output.split()))
