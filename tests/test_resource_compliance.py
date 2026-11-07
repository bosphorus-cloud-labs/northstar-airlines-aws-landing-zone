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
        target = next(c for c in second["changes"] if c["resource_name"] == "NorthStar EC2 01")
        self.assertEqual((target["before"], target["after"]), ("compliant", "noncompliant"))
        stored = copy.deepcopy(self.client.rows)
        git("revert", "--no-edit", change_commit)
        revert_commit = git("rev-parse", "HEAD")
        self.assertEqual(git("status", "--porcelain"), "")
        reverted, _, _ = prepare(load(working), self.temporary.name + "/git-reverted")
        self.assertEqual(digest(reverted), digest(self.document))
        third = self.publish(reverted, 3, commit=revert_commit)
        target = next(c for c in third["changes"] if c["resource_name"] == "NorthStar EC2 01")
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


class HundredAccountTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from deployment.generate_synthetic_fleet import extend

        cls.generated = extend(load())
        rollout.OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
        cls.temp = tempfile.TemporaryDirectory(dir=rollout.OUTPUT_ROOT)
        cls.document, _, cls.plan = prepare(cls.generated, Path(cls.temp.name) / "hundred")

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_deterministic_fleet_preserves_original_accounts_and_observations(self):
        from collections import Counter

        from deployment.generate_synthetic_fleet import extend

        baseline = load()
        self.assertEqual(self.generated, extend(baseline))
        self.assertEqual(self.generated, extend(self.generated))
        self.assertEqual(
            self.generated["accounts"]["accounts"][:10], baseline["accounts"]["accounts"]
        )
        self.assertEqual(
            self.generated["inventory"]["resources"][:10], baseline["inventory"]["resources"]
        )
        self.assertEqual(
            Counter(a["environment"] for a in self.generated["accounts"]["accounts"]),
            {"production": 30, "pre-production": 20, "testing": 20, "development": 30},
        )
        self.assertEqual(
            evaluate(self.document)["summary"],
            {
                "accounts": 100,
                "resources": 100,
                "controls": 3,
                "compliant": 77,
                "noncompliant": 9,
                "unknown": 7,
                "stale": 7,
            },
        )
        # Actual editable input is validated independently from fixed unit scenarios.
        current = evaluate(load_current())
        self.assertEqual(current["summary"]["accounts"], 100)
        self.assertEqual(current["summary"]["resources"], 100)
        self.assertEqual(
            {f["status"] for f in current["findings"]},
            {"compliant", "noncompliant", "unknown", "stale"},
        )

    def test_real_terraform_assignments_cover_every_account_and_environment(self):
        self.assertFalse(self.plan.get("resource_changes"))
        receipt = self.document["terraform_validation"]["accounts"]
        self.assertEqual(set(receipt), {f"sim-account-{i:03}" for i in range(1, 101)})
        limits = {"production": 24, "pre-production": 48, "testing": 72, "development": 168}
        for assignment in receipt.values():
            self.assertEqual(
                assignment["approval_required"],
                assignment["environment"] in {"production", "pre-production"},
            )
            self.assertEqual(len(assignment["requirements"]), 3)
            for requirement in assignment["requirements"].values():
                self.assertEqual(requirement["max_age_hours"], limits[assignment["environment"]])

    def test_central_policy_changes_propagate_across_hundred_account_fleet(self):
        for scope in ("production", "organization"):
            changed = copy.deepcopy(self.generated)
            rule = next(r for r in changed["controls"]["rules"] if r["id"] == "ebs-encryption")
            for environment, hours in list(rule["max_age_hours"].items()):
                if scope == "organization" or environment == "production":
                    rule["max_age_hours"][environment] = hours // 2
            planned, _, plan = prepare(changed, Path(self.temp.name) / ("central-" + scope))
            self.assertFalse(plan.get("resource_changes"))
            for account_id, assignment in planned["terraform_validation"]["accounts"].items():
                self.assertEqual(
                    assignment["requirements"]["ebs-encryption"]["max_age_hours"],
                    rule["max_age_hours"][assignment["environment"]],
                )
                self.assertEqual(
                    assignment["requirements"]["ec2-imdsv2"],
                    self.document["terraform_validation"]["accounts"][account_id]["requirements"][
                        "ec2-imdsv2"
                    ],
                )
            findings = evaluate(planned)["findings"]
            production_ebs = next(f for f in findings if f["resource_id"] == "sim-ebs-003")
            self.assertEqual(production_ebs["status"], "stale")
            self.assertIs(production_ebs["observed"], True)

    def test_existing_history_survives_expansion_regression_and_restoration(self):
        from backend.deployment.resources import read_snapshot, view

        client = MemoryDynamo([])
        baseline, _, _ = prepare(load(), Path(self.temp.name) / "ten")
        documents = [baseline, self.document]
        bad = copy.deepcopy(self.generated)
        ec2_instance = next(r for r in bad["inventory"]["resources"] if r["id"] == "sim-ec2-001")
        ec2_instance["configuration"]["metadata_options"]["http_tokens"] = "optional"
        regression, _, _ = prepare(bad, Path(self.temp.name) / "regression")
        documents.extend([regression, self.document])
        with TestClient(
            create_app(
                local_demo=True,
                resource_repository=DynamoResources(
                    "northstar-offline-records", client_factory=lambda: client
                ),
            ),
            base_url="http://127.0.0.1",
            client=("127.0.0.1", 50000),
        ) as api:
            exceptions_before = api.get("/api/v1/exceptions").json()
            for number, document in enumerate(documents, 1):
                publish(
                    client,
                    "northstar-offline-records",
                    document,
                    source_commit=f"{number:040x}",
                    actor="synthetic-reviewer",
                    operation=f"gh-{number}-1",
                    published_at="2026-11-05T12:00:00Z",
                )
                current = api.get("/api/v1/summary?view=resources").json()["data"]
                finding = next(f for f in current["findings"] if f["resource_id"] == "sim-ec2-001")
                resource = next(r for r in current["resources"] if r["id"] == "sim-ec2-001")
                negative = number == 3
                expected_status = "noncompliant" if negative else "compliant"
                self.assertEqual(finding["status"], expected_status)
                self.assertEqual(resource["status"], expected_status)
                self.assertEqual(finding["observed"], "optional" if negative else "required")
                self.assertEqual(finding["expected"], "required")
                self.assertEqual(current["activity"][0]["operation"], f"gh-{number}-1")
                self.assertEqual(current["activity"][0]["source_commit"], f"{number:040x}")
                if number >= 2:
                    self.assertEqual(current["summary"]["compliant"], 76 if negative else 77)
                    self.assertEqual(current["summary"]["noncompliant"], 10 if negative else 9)
                    imds = [f for f in current["findings"] if f["control_id"] == "ec2-imdsv2"]
                    self.assertEqual(
                        sum(f["status"] == "compliant" for f in imds), 27 if negative else 28
                    )
                    self.assertEqual(
                        sum(f["status"] == "noncompliant" for f in imds), int(negative)
                    )
                self.assertEqual(api.get("/api/v1/exceptions").json(), exceptions_before)
        catalogue = read_catalog(client, "northstar-offline-records")
        self.assertEqual(catalogue["generation"], 4)
        self.assertEqual(catalogue["current"], digest(self.document))
        for event in catalogue["history"]:
            read_snapshot(client, "northstar-offline-records", event["target"])
        self.assertEqual(catalogue["history"][2]["changes"][0]["before"], "compliant")
        self.assertEqual(catalogue["history"][3]["changes"][0]["after"], "compliant")
        with TestClient(
            create_app(
                local_demo=True,
                resource_repository=DynamoResources(
                    "northstar-offline-records", client_factory=lambda: client
                ),
            ),
            base_url="http://127.0.0.1",
            client=("127.0.0.1", 50000),
        ) as api:
            response = api.get("/api/v1/summary?view=resources")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.json()["data"]["accounts"]), 100)
            self.assertEqual(response.json()["data"]["summary"]["compliant"], 77)
            self.assertLess(len(response.content), 2_000_000)
        self.assertLess(len(json.dumps(view(self.document, catalogue)).encode()), 2_000_000)
        # DynamoDB's 400 KiB item and 1 MiB Query page limits have ample headroom.
        self.assertTrue(
            all(len(json.dumps(row).encode()) < 400_000 for row in client.rows.values())
        )

    def test_bounded_capacity_rejects_excess_and_oversized_input(self):
        bad = copy.deepcopy(self.generated)
        extra = {**bad["accounts"]["accounts"][-1], "id": "sim-account-101"}
        bad["accounts"]["accounts"].append(extra)
        with self.assertRaises(ValueError):
            validate(bad)
        for i in range(101, 201):
            extra = {**bad["inventory"]["resources"][0], "id": f"sim-ec2-extra-{i}"}
            bad["inventory"]["resources"].append(extra)
        bad["accounts"]["accounts"].pop()
        validate(bad)  # 100 accounts / 200 resources is allowed, subject to byte budgets.
        bad["inventory"]["resources"].append({**extra, "id": "sim-ec2-extra-201"})
        with self.assertRaises(ValueError):
            validate(bad)
        bad["inventory"]["resources"].pop()
        for account in bad["accounts"]["accounts"]:
            account["name"] = "✈" * 100
        for resource in bad["inventory"]["resources"]:
            resource["name"] = "✈" * 100
        with self.assertRaises(ValueError):
            validate(bad)
