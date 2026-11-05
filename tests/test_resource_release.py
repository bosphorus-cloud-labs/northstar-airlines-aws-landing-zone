"""Resource release provenance checks run without constructing an AWS client."""

import copy
import json
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
