"""Resource release provenance checks run without constructing an AWS client."""

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from compliance_engine.resources import ROOT, canonical, digest, load
from deployment.resource_plan import prepare
from deployment.resource_release import check, checkout, main


class ResourceReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (ROOT / "artifacts/policy-rollout").mkdir(parents=True, exist_ok=True)
        cls.temp = tempfile.TemporaryDirectory(dir=ROOT / "artifacts/policy-rollout")
        cls.document, _, _ = prepare(load(), Path(cls.temp.name) / "terraform")

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_release_requires_matching_commit_content_and_verified_terraform(self):
        sha = "a" * 40
        release = {
            "source_commit": sha,
            "snapshot_id": digest(self.document),
            "document": self.document,
        }
        path = Path(self.temp.name) / "release.json"
        path.write_text(canonical(release))
        with patch("deployment.resource_release.checkout"):
            self.assertEqual(check(path, sha), release)
            for kind in ["commit", "digest", "receipt", "input"]:
                bad = copy.deepcopy(release)
                if kind == "commit":
                    bad["source_commit"] = "b" * 40
                elif kind == "digest":
                    bad["snapshot_id"] = "b" * 64
                elif kind == "receipt":
                    bad["document"]["terraform_validation"] = None
                    bad["snapshot_id"] = digest(bad["document"])
                else:
                    bad["document"]["inventory"]["resources"][0]["name"] = "Altered resource"
                path.write_text(json.dumps(bad))
                with self.subTest(kind=kind), self.assertRaises(ValueError):
                    check(path, sha)

    def test_dirty_or_different_checkout_cannot_build_release(self):
        with patch(
            "deployment.resource_release.subprocess.check_output",
            side_effect=["a" * 40, " M changed.json"],
        ):
            with self.assertRaises(ValueError):
                checkout("a" * 40)
        with patch("deployment.resource_release.subprocess.check_output", return_value="b" * 40):
            with self.assertRaises(ValueError):
                checkout("a" * 40)

    def test_cloud_execution_requires_explicit_flag(self):
        path = Path(self.temp.name) / "protected.json"
        path.write_text(
            canonical(
                {
                    "source_commit": "a" * 40,
                    "snapshot_id": digest(self.document),
                    "document": self.document,
                }
            )
        )
        with (
            patch("deployment.resource_release.checkout"),
            patch(
                "sys.argv",
                [
                    "resource_release",
                    "publish",
                    "--source-commit",
                    "a" * 40,
                    "--release",
                    str(path),
                ],
            ),
        ):
            with self.assertRaises(SystemExit):
                main()

    def test_runtime_checks_and_publisher_do_not_import_ci_only_dependencies(self):
        code = """
import builtins
original = builtins.__import__
def runtime_only(name, *args, **kwargs):
    if name == 'hcl2':
        raise ModuleNotFoundError('Terraform parser is CI-only')
    return original(name, *args, **kwargs)
builtins.__import__ = runtime_only
from deployment.resource_release import check
from governance.delivery.resource_publisher import publish
assert callable(check) and callable(publish)
"""
        subprocess.run(
            [sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, check=True
        )

    def test_receipt_output_preserves_clean_checkout_and_failures_cannot_be_masked(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def git(*args):
                return subprocess.check_output(
                    [
                        "git",
                        "-c",
                        "user.name=NorthStar test",
                        "-c",
                        "user.email=synthetic@example.invalid",
                        "-c",
                        "commit.gpgsign=false",
                        "-c",
                        "core.hooksPath=/dev/null",
                        *args,
                    ],
                    cwd=root,
                    text=True,
                ).strip()

            git("init", "-q", "--template=", "--initial-branch=main")
            (root / ".gitignore").write_text("artifacts/\n")
            git("add", ".gitignore")
            git("commit", "-qm", "Test fixture")
            sha = git("rev-parse", "HEAD")
            script = "import sys; sys.path.insert(0, sys.argv[1]); from deployment.resource_release import checkout; checkout(sys.argv[2])"
            command = [sys.executable, "-c", script, str(ROOT), sha]
            with (root / "receipt.json").open("w") as output:
                failed = subprocess.run(
                    command, cwd=root, stdout=output, stderr=subprocess.PIPE, text=True
                )
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn("clean checkout", failed.stderr)
            (root / "receipt.json").unlink()
            (root / "artifacts").mkdir()
            with (root / "artifacts/receipt.json").open("w") as output:
                subprocess.run(command, cwd=root, stdout=output, stderr=subprocess.PIPE, check=True)
            workflow = (ROOT / ".github/workflows/governance-cd.yml").read_text()
            self.assertIn("defaults:\n  run:\n    shell: bash", workflow)
            self.assertIn("> artifacts/resource-publication/receipt.json", workflow)
            self.assertNotIn("tee resource-publication.json", workflow)
            failed = subprocess.run(
                ["bash", "-e", "-o", "pipefail", "-c", "false | cat"], capture_output=True
            )
            self.assertNotEqual(failed.returncode, 0)
