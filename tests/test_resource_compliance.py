"""Real provider-free Terraform integration and offline resource publication acceptance."""

import copy
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from fastapi.testclient import TestClient

from backend.app import create_app
from backend.deployment.resources import DynamoResources, read_catalog
from compliance_engine.resources import ROOT, Document, digest, evaluate, validate
from compliance_engine.resources import load as load_current
from deployment.resource_plan import prepare, verify
from governance.delivery.resource_publisher import publish
from governance.simulation import rollout
from tests.resource_fixtures import load
from tests.test_governance_delivery import MemoryDynamo


class ResourceComplianceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rollout.OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
        cls.temporary = tempfile.TemporaryDirectory(dir=rollout.OUTPUT_ROOT)
        cls.document, cls.state, cls.plan = prepare(load(), cls.temporary.name + "/verified")

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def setUp(self):
        self.client = MemoryDynamo([])

    def publish(self, document=None, operation=1, commit=None):
        return publish(
            self.client,
            "northstar-offline-records",
            document or self.document,
            source_commit=commit or "a" * 39 + str(operation),
            actor="bosphorus-cloud-labs",
            operation=f"gh-{operation}-1",
            published_at="2026-11-05T12:00:00Z",
        )

    def test_real_terraform_covers_accounts_environments_and_central_controls(self):
        receipt = self.document["terraform_validation"]
        self.assertEqual(len(receipt["accounts"]), 10)
        environments = {a["environment"] for a in receipt["accounts"].values()}
        self.assertEqual(environments, {"production", "pre-production", "testing", "development"})
        for account in receipt["accounts"].values():
            self.assertEqual(
                account["approval_required"],
                account["environment"] in {"production", "pre-production"},
            )
            self.assertEqual(len(account["requirements"]), 3)
            expected_age = {
                "production": 24,
                "pre-production": 48,
                "testing": 72,
                "development": 168,
            }[account["environment"]]
            self.assertEqual(account["requirements"]["ec2-imdsv2"]["max_age_hours"], expected_age)
        self.assertFalse(self.plan.get("resource_changes"))

    def test_wrong_terraform_values_and_input_digest_are_rejected(self):
        for field in ("input_digest", "accounts"):
            bad = copy.deepcopy(self.plan)
            bad["planned_values"]["outputs"]["resource_governance_desired"]["value"][field] = (
                "forged"
            )
            with self.subTest(field=field), self.assertRaises(ValueError):
                verify(bad, self.state, load())
        changed = copy.deepcopy(self.document)
        changed["inventory"]["resources"][0]["configuration"]["metadata_options"]["http_tokens"] = (
            "optional"
        )
        with self.assertRaises(ValueError):
            validate(changed)

    def test_compliant_noncompliant_and_git_revert_preserve_immutable_history(self):
        working = Path(self.temporary.name) / "git-rehearsal"
        working.mkdir()
        for name, key in [
            ("mock-aws-resources/accounts.json", "accounts"),
            ("mock-aws-resources/resources.json", "inventory"),
            ("compliance-rules/resource-controls.json", "controls"),
        ]:
            target = working / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(self.document[key], indent=2) + "\n")
        env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}

        def git(*args):
            return subprocess.check_output(
                [
                    "git",
                    "-c",
                    "user.name=NorthStar offline test",
                    "-c",
                    "user.email=synthetic@example.invalid",
                    "-c",
                    "commit.gpgsign=false",
                    "-c",
                    "core.hooksPath=" + os.devnull,
                    *args,
                ],
                cwd=working,
                env=env,
                text=True,
                stderr=subprocess.STDOUT,
            ).strip()

        git("init", "--initial-branch=main", "--template=", "-q")
        git("add", ".")
        git("commit", "-qm", "Synthetic baseline")
        baseline_commit = git("rev-parse", "HEAD")
        first = self.publish(commit=baseline_commit)
        path = working / "mock-aws-resources/resources.json"
        bad = json.loads(path.read_text())
        bad["resources"][0]["configuration"]["metadata_options"]["http_tokens"] = "optional"
        path.write_text(json.dumps(bad, indent=2) + "\n")
        git("add", "mock-aws-resources/resources.json")
        git("commit", "-qm", "Synthetic metadata regression")
        change_commit = git("rev-parse", "HEAD")
        changed, _, _ = prepare(load(working), self.temporary.name + "/changed")
        second = self.publish(changed, 2, commit=change_commit)
        target = next(c for c in second["changes"] if c["resource_name"] == "Booking API")
        self.assertEqual((target["before"], target["after"]), ("compliant", "noncompliant"))
        stored = copy.deepcopy(self.client.rows)
        git("revert", "--no-edit", change_commit)
        revert_commit = git("rev-parse", "HEAD")
        self.assertEqual(git("status", "--porcelain"), "")
        reverted, _, _ = prepare(load(working), self.temporary.name + "/git-reverted")
        self.assertEqual(digest(reverted), digest(self.document))
        third = self.publish(reverted, 3, commit=revert_commit)
        target = next(c for c in third["changes"] if c["resource_name"] == "Booking API")
        self.assertEqual((target["before"], target["after"]), ("noncompliant", "compliant"))
        catalog = read_catalog(self.client, "northstar-offline-records")
        self.assertEqual(catalog["generation"], 3)
        self.assertEqual(
            [event["source_commit"] for event in catalog["history"]],
            [baseline_commit, change_commit, revert_commit],
        )
        self.assertEqual(catalog["current"], digest(self.document))
        self.assertEqual(first["generation"], 1)
        for key, value in stored.items():
            if key[0].startswith("SNAPSHOT#"):
                self.assertEqual(self.client.rows[key], value)
        writes = len(self.client.writes)
        self.assertEqual(self.publish(operation=4)["status"], "unchanged")
        self.assertEqual(writes, len(self.client.writes))

    def test_noncompliant_unknown_and_stale_do_not_count_as_passing(self):
        result = evaluate(self.document)
        self.assertEqual(
            result["summary"],
            {
                "accounts": 10,
                "resources": 10,
                "controls": 3,
                "compliant": 7,
                "noncompliant": 1,
                "unknown": 1,
                "stale": 1,
            },
        )
        self.assertEqual(result, evaluate(self.document))

    def test_operator_inputs_validate_without_requiring_a_compliant_dataset(self):
        document = load_current()
        result = evaluate(document)
        self.assertEqual(
            sum(
                result["summary"][key] for key in ["compliant", "noncompliant", "unknown", "stale"]
            ),
            len(document["inventory"]["resources"]),
        )
        self.assertEqual(result, evaluate(document))

    def test_schema_matches_actual_validated_contract(self):
        schema = json.loads(
            (ROOT / "governance/contracts/resource-compliance.schema.json").read_text()
        )
        self.assertEqual(schema, Document.model_json_schema())

    def test_invalid_input_and_weakened_rules_fail(self):
        for kind in (
            "account",
            "duplicate",
            "rule",
            "freshness",
            "future",
            "extra",
            "region",
            "ou",
        ):
            bad = load()
            if kind == "account":
                bad["inventory"]["resources"][0]["account_id"] = "sim-account-999"
            elif kind == "duplicate":
                bad["inventory"]["resources"].append(bad["inventory"]["resources"][0])
            elif kind == "rule":
                bad["controls"]["rules"][0]["expected"] = "optional"
            elif kind == "freshness":
                bad["controls"]["rules"][0]["max_age_hours"]["production"] = 25
            elif kind == "future":
                bad["inventory"]["resources"][0]["observed_at"] = "2026-12-01T12:00:00Z"
            elif kind == "extra":
                bad["inventory"]["resources"][0]["compliant"] = True
            elif kind == "region":
                bad["inventory"]["resources"][0]["region"] = "us-east-1"
            elif kind == "ou":
                bad["accounts"]["accounts"][0]["ou_id"] = "sim-ou-testing"
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                validate(bad)

    def test_new_synthetic_account_inherits_terraform_baseline(self):
        document = load()
        document["accounts"]["accounts"].append(
            {
                "id": "sim-account-011",
                "name": "New development account",
                "environment": "development",
                "ou_id": "sim-ou-development",
                "lifecycle_status": "onboarding",
            }
        )
        result, _, _ = prepare(document, self.temporary.name + "/onboarding")
        self.assertEqual(len(result["terraform_validation"]["accounts"]), 11)
        account = next(a for a in evaluate(result)["accounts"] if a["id"] == "sim-account-011")
        self.assertEqual(account["status"], "unknown")
        self.assertFalse(
            result["terraform_validation"]["accounts"]["sim-account-011"]["approval_required"]
        )

    def test_failed_or_superseded_publication_does_not_promote(self):
        self.client.fail_after = 1
        with self.assertRaises(RuntimeError):
            self.publish()
        self.assertIsNone(read_catalog(self.client, "northstar-offline-records"))
        self.client.fail_after = None
        self.publish()
        self.client.corrupt_reads = True
        with self.assertRaises(ValueError):
            DynamoResources("northstar-offline-records", client_factory=lambda: self.client).read()

    def test_unvalidated_terraform_or_failed_prewrite_gate_cannot_publish(self):
        with self.assertRaises(ValueError):
            self.publish(load())
        self.assertEqual(self.client.writes, [])

        def deny():
            raise ValueError("Main advanced")

        with self.assertRaises(ValueError):
            publish(
                self.client,
                "northstar-offline-records",
                self.document,
                source_commit="a" * 40,
                actor="bosphorus-cloud-labs",
                operation="gh-99-1",
                published_at="2026-11-05T12:00:00Z",
                before_write=deny,
            )
        self.assertEqual(self.client.writes, [])

    def test_central_environment_change_is_planned_across_existing_accounts(self):
        document = load()
        for rule in document["controls"]["rules"]:
            rule["max_age_hours"]["production"] = 12
        result, _, _ = prepare(document, self.temporary.name + "/central-change")
        before = next(r for r in evaluate(load())["resources"] if r["id"] == "sim-ebs-003")
        after = next(r for r in evaluate(result)["resources"] if r["id"] == "sim-ebs-003")
        self.assertEqual((before["status"], after["status"]), ("compliant", "stale"))
        for account in result["terraform_validation"]["accounts"].values():
            for requirement in account["requirements"].values():
                expected = (
                    12
                    if account["environment"] == "production"
                    else {"pre-production": 48, "testing": 72, "development": 168}[
                        account["environment"]
                    ]
                )
                self.assertEqual(requirement["max_age_hours"], expected)
        self.assertEqual(len(result["terraform_validation"]["accounts"]), 10)

    def test_organization_wide_change_targets_every_account_and_environment(self):
        document = load()
        rule = next(
            rule for rule in document["controls"]["rules"] if rule["id"] == "ebs-encryption"
        )
        limits = {environment: hours // 2 for environment, hours in rule["max_age_hours"].items()}
        rule["max_age_hours"] = limits
        result, _, plan = prepare(document, self.temporary.name + "/organization-wide-change")
        assignments = result["terraform_validation"]["accounts"]
        self.assertEqual(
            set(assignments), {account["id"] for account in document["accounts"]["accounts"]}
        )
        self.assertEqual({account["environment"] for account in assignments.values()}, set(limits))
        for account in assignments.values():
            requirement = account["requirements"]["ebs-encryption"]
            self.assertEqual(
                requirement,
                {"expected_json": "true", "max_age_hours": limits[account["environment"]]},
            )
            baseline = self.document["terraform_validation"]["accounts"][account["account_id"]]
            self.assertEqual(
                account["requirements"]["ec2-imdsv2"], baseline["requirements"]["ec2-imdsv2"]
            )
        self.assertFalse(plan.get("resource_changes"))
        self.assertTrue(
            any(finding["status"] != "compliant" for finding in evaluate(result)["findings"])
        )

    def test_legacy_catalogue_never_changes(self):
        self.client.rows[("GOVERNANCE#CATALOG", "STATE")] = {"preserved": "legacy catalogue"}
        self.publish()
        self.assertEqual(
            self.client.rows[("GOVERNANCE#CATALOG", "STATE")], {"preserved": "legacy catalogue"}
        )
        self.assertTrue(all(sk != "STATE" for _, sk in self.client.writes))

    def test_resource_read_api_requires_authentication_and_never_writes(self):
        with TestClient(create_app()) as client:
            self.assertEqual(client.get("/api/v1/summary?view=resources").status_code, 401)
        with TestClient(
            create_app(local_demo=True), base_url="http://127.0.0.1", client=("127.0.0.1", 50000)
        ) as client:
            response = client.get("/api/v1/summary?view=resources")
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()["metadata"]["simulated"])
            self.assertEqual(
                client.get("/api/v1/summary?view=resources&policy_version=2.0.0").status_code, 422
            )
            self.assertEqual(
                client.get(
                    "/api/v1/summary?view=resources", headers={"Authorization": "Bearer fake"}
                ).status_code,
                401,
            )
            self.assertEqual(client.post("/api/v1/summary?view=resources").status_code, 405)
        unavailable = Mock()
        unavailable.read.side_effect = RuntimeError("/private/secret/path")
        with TestClient(
            create_app(local_demo=True, resource_repository=unavailable),
            base_url="http://127.0.0.1",
            client=("127.0.0.1", 50000),
        ) as client:
            response = client.get("/api/v1/summary?view=resources")
            self.assertEqual(response.status_code, 503)
            self.assertNotIn("/private", response.text)
