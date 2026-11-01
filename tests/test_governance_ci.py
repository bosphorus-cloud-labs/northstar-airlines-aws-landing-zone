"""CI-specific cloud boundary and truthful report checks; no hosted CI/AWS operations."""

import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from governance.simulation import rollout
from governance.simulation.terraform_plan import desired
from scripts.ci_governance import CONFIGS, preflight, summary


class GovernanceCITests(unittest.TestCase):
    def test_current_terraform_is_resource_provider_backend_free(self):
        with redirect_stdout(io.StringIO()):
            preflight()

    def test_cloud_blocks_extra_files_and_remote_modules_rejected_before_init(self):
        original = {name: (rollout.ROOT / name / "main.tf").read_text() for name in CONFIGS}
        for block in [
            '\nresource "terraform_data" "unsafe" {}\n',
            '\nprovider "aws" {}\n',
            '\ndata "aws_caller_identity" "current" {}\n',
            '\nterraform { backend "s3" {} }\n',
            '\nterraform { required_providers { aws = { source = "hashicorp/aws" } } }\n',
        ]:
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                for name, text in original.items():
                    path = root / name / "main.tf"
                    path.parent.mkdir(parents=True)
                    path.write_text(text + (block if name == CONFIGS[0] else ""))
                with self.assertRaises(ValueError):
                    preflight(root)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name, text in original.items():
                path = root / name / "main.tf"
                path.parent.mkdir(parents=True)
                path.write_text(
                    text.replace(
                        "../modules/simulated_governance", "git::https://example.invalid/module"
                    )
                )
            with self.assertRaises(ValueError):
                preflight(root)
            (root / CONFIGS[0] / "extra.tf.json").write_text("{}")
            with self.assertRaises(ValueError):
                preflight(root)

    def test_summary_preserves_simulation_and_local_ci_distinction_without_mutation(self):
        state = rollout.plan()
        rollout.approve(state, "sim-security-reviewer")
        rollout.rollout(state, fail_account="sim-account-005")
        rollout.rollout(state)
        rollout.onboard(state)
        before = copy.deepcopy(state)
        # Unit-test projection only; actual CI creates this file using terraform show.
        plan = {
            "planned_values": {
                "outputs": {"governance_desired": {"value": desired(state, "2.0.0")}}
            }
        }
        with (
            tempfile.TemporaryDirectory() as temp,
            patch.dict("os.environ", {"GITHUB_ACTIONS": "false", "GITHUB_SHA": ""}),
        ):
            path = Path(temp)
            rollout.save(path, state)
            (path / "v2.plan.json").write_text(json.dumps(plan))
            text = summary(path)
            self.assertIn("NOT a GitHub Actions run", text)
            self.assertIn("11 synthetic accounts", text)
            self.assertIn("43 | 4 | 9 | 10", text)
            self.assertIn("does not update", text)
            self.assertIn("simulated", text)
            self.assertEqual(state, before)
            report = json.loads((path / "report.json").read_text())
            report["current"]["finding_counts"]["compliant"] = 999
            (path / "report.json").write_text(json.dumps(report))
            with self.assertRaises(ValueError):
                summary(path)
