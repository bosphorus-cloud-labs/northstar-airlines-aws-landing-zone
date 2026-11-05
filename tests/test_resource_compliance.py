"""Real provider-free Terraform integration and offline resource publication acceptance."""

import copy
import json
import tempfile
import unittest
from unittest.mock import Mock

from fastapi.testclient import TestClient

from backend.app import create_app
from backend.deployment.resources import DynamoResources, read_catalog
from compliance_engine.resources import ROOT, Document, digest, evaluate, load, validate
from deployment.resource_plan import prepare, verify
from governance.delivery.resource_publisher import publish
from governance.simulation import rollout
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

    def publish(self, document=None, operation=1):
        return publish(
            self.client,
            "northstar-offline-records",
            document or self.document,
            source_commit="a" * 39 + str(operation),
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
        first = self.publish()
        bad = load()
        bad["inventory"]["resources"][0]["configuration"]["metadata_options"]["http_tokens"] = (
            "optional"
        )
        changed, _, _ = prepare(bad, self.temporary.name + "/changed")
        second = self.publish(changed, 2)
        target = next(c for c in second["changes"] if c["resource_name"] == "Booking API")
        self.assertEqual((target["before"], target["after"]), ("compliant", "noncompliant"))
        stored = copy.deepcopy(self.client.rows)
        third = self.publish(self.document, 3)
        target = next(c for c in third["changes"] if c["resource_name"] == "Booking API")
        self.assertEqual((target["before"], target["after"]), ("noncompliant", "compliant"))
        catalog = read_catalog(self.client, "northstar-offline-records")
        self.assertEqual(catalog["generation"], 3)
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

    def test_schema_matches_actual_validated_contract(self):
        schema = json.loads(
            (ROOT / "governance/contracts/resource-compliance.schema.json").read_text()
        )
        self.assertEqual(schema, Document.model_json_schema())

    def test_invalid_input_and_weakened_rules_fail(self):
        for kind in ("account", "duplicate", "rule", "future", "extra", "region", "ou"):
            bad = load()
            if kind == "account":
                bad["inventory"]["resources"][0]["account_id"] = "sim-account-999"
            elif kind == "duplicate":
                bad["inventory"]["resources"].append(bad["inventory"]["resources"][0])
            elif kind == "rule":
                bad["controls"]["rules"][0]["expected"] = "optional"
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
