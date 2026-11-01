"""Offline delivery failure, CAS, history, authorization and reader integration tests."""

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
from jsonschema.exceptions import ValidationError

from backend.app import create_app
from backend.deployment.catalog import DynamoCatalog
from backend.deployment.dynamodb import DynamoSnapshotRepository
from backend.deployment.snapshot import digest, encode
from backend.repository import FixtureRepository
from governance.delivery import catalog
from governance.delivery.publisher import deliver
from tests.fixture_versions import catalogue


class ConditionalFailure(Exception):
    pass


class MemoryDynamo:
    exceptions = SimpleNamespace(ConditionalCheckFailedException=ConditionalFailure)

    def __init__(self, rows):
        self.rows = {(r["pk"]["S"], r["sk"]["S"]): copy.deepcopy(r) for r in rows}
        self.writes = []
        self.fail_after = None
        self.corrupt_reads = False
        self.lose_catalog_response = False
        self.race = False

    def get_item(self, **request):
        assert request["ConsistentRead"] is True
        key = request["Key"]
        item = self.rows.get((key["pk"]["S"], key["sk"]["S"]))
        return {"Item": copy.deepcopy(item)} if item else {}

    def query(self, **request):
        assert request["ConsistentRead"] is True
        pk = request["ExpressionAttributeValues"][":pk"]["S"]
        rows = [copy.deepcopy(r) for (key, _), r in self.rows.items() if key == pk]
        if self.corrupt_reads and rows:
            rows = rows[:-1]
        return {"Items": rows}

    def put_item(self, **request):
        if self.fail_after is not None and len(self.writes) >= self.fail_after:
            raise RuntimeError("Injected transport failure")
        item = request["Item"]
        key = (item["pk"]["S"], item["sk"]["S"])
        old = self.rows.get(key)
        condition = request["ConditionExpression"]
        if self.race and key[0] == "GOVERNANCE#CATALOG":
            self.race = False
            raise ConditionalFailure()
        if condition.startswith("attribute_not_exists") and old:
            raise ConditionalFailure()
        if condition == "#g = :g" and (
            not old or old["generation"] != request["ExpressionAttributeValues"][":g"]
        ):
            raise ConditionalFailure()
        self.rows[key] = copy.deepcopy(item)
        self.writes.append(key)
        if self.lose_catalog_response and key[0] == "GOVERNANCE#CATALOG":
            self.lose_catalog_response = False
            raise ConditionalFailure()


class GovernanceDeliveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.v1 = FixtureRepository().read_snapshot()
        cls.v2 = catalogue().entries()["2.0.0"].repository.read_snapshot()
        cls.baseline_id, cls.baseline_rows, cls.baseline_manifest = encode(cls.v1)
        cls.target, rows, manifest = encode(cls.v2)
        cls.commit = "a" * 40
        cls.release = {
            "source_commit": cls.commit,
            "publication": {
                "format_version": "1.0.0",
                "simulated": True,
                "snapshot_id": cls.target,
                "policy_version": "2.0.0",
                "rows": rows,
                "manifest": manifest,
            },
        }

    def test_release_check_cli_is_offline_and_rejects_mismatched_source_or_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "release.json"
            path.write_text(json.dumps(self.release))
            for commit, digest_value, expected in [
                (self.commit, self.target, 0),
                ("d" * 40, self.target, 1),
                (self.commit, "e" * 64, 1),
            ]:
                result = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "scripts.governance_release",
                        "check",
                        "--source-commit",
                        commit,
                        "--approved-digest",
                        digest_value,
                        "--release",
                        str(path),
                    ],
                    capture_output=True,
                    text=True,
                    env={"PATH": "/usr/bin:/bin", "AWS_EC2_METADATA_DISABLED": "true"},
                )
                self.assertEqual(result.returncode, expected)
                if expected == 0:
                    self.assertEqual(json.loads(result.stdout)["snapshot_id"], self.target)

    def setUp(self):
        self.client = MemoryDynamo([*self.baseline_rows, self.baseline_manifest])

    def execute(self, action, generation, operation, target=None, package=None):
        return deliver(
            self.client,
            "northstar-offline-records",
            baseline_id=self.baseline_id,
            source_commit=self.commit,
            expected_generation=generation,
            operation=operation,
            action=action,
            target_digest=target or self.target,
            package=self.release if package is None and action == "publish" else package,
        )

    def bootstrap(self):
        return self.execute("bootstrap", 0, "bootstrap-1", self.baseline_id)

    def current(self):
        return catalog.read(self.client, "northstar-offline-records", self.baseline_id)

    def test_complete_publication_manifest_last_history_and_rollback(self):
        self.bootstrap()
        original = copy.deepcopy(
            [self.client.rows[(r["pk"]["S"], r["sk"]["S"])] for r in self.baseline_rows]
        )
        value = self.execute("publish", 1, "publish-1")
        self.assertEqual(value["current"], self.target)
        snapshot_writes = [sk for pk, sk in self.client.writes if pk.startswith("SNAPSHOT#")]
        self.assertEqual(snapshot_writes[-1], "MANIFEST")
        self.assertEqual(len(value["entries"]), 2)
        self.assertEqual(
            original, [self.client.rows[(r["pk"]["S"], r["sk"]["S"])] for r in self.baseline_rows]
        )
        value = self.execute("rollback", 2, "rollback-1", self.baseline_id)
        self.assertEqual(value["current"], self.baseline_id)
        self.assertEqual(len(value["entries"]), 2)
        self.assertEqual(
            digest(
                DynamoSnapshotRepository(
                    "northstar-offline-records", self.target, lambda: self.client
                ).read_snapshot()
            ),
            self.target,
        )

    def test_failed_partial_publication_never_promotes_and_retry_is_idempotent(self):
        self.bootstrap()
        self.client.fail_after = 5
        with self.assertRaises(RuntimeError):
            self.execute("publish", 1, "publish-1")
        self.assertEqual(self.current()["current"], self.baseline_id)
        self.client.fail_after = None
        first = self.execute("publish", 1, "publish-1")
        second = self.execute("publish", 1, "publish-1")
        self.assertEqual(first, second)
        self.assertEqual(second["generation"], 2)

    def test_digest_commit_and_manifest_mismatch_fail_before_promotion(self):
        self.bootstrap()
        for change in ("source_commit", "row", "manifest"):
            bad = copy.deepcopy(self.release)
            if change == "source_commit":
                bad["source_commit"] = "b" * 40
            elif change == "row":
                bad["publication"]["rows"][0]["payload"]["S"] = "{}"
            else:
                bad["publication"]["manifest"]["payload"]["S"] = "{}"
            with (
                self.subTest(change=change),
                self.assertRaises((ValueError, KeyError, ValidationError)),
            ):
                self.execute("publish", 1, "publish-1", package=bad)
            self.assertEqual(self.current()["current"], self.baseline_id)

    def test_conflicting_immutable_record_is_not_overwritten(self):
        self.bootstrap()
        row = copy.deepcopy(self.release["publication"]["rows"][0])
        row["payload"]["S"] = "{}"
        key = (row["pk"]["S"], row["sk"]["S"])
        self.client.rows[key] = row
        with self.assertRaises(ValueError):
            self.execute("publish", 1, "publish-1")
        self.assertEqual(self.client.rows[key], row)
        self.assertEqual(self.current()["current"], self.baseline_id)

    def test_missing_or_corrupt_readback_blocks_promotion(self):
        self.bootstrap()
        self.client.corrupt_reads = True
        with self.assertRaises((ValueError, KeyError, ValidationError)):
            self.execute("publish", 1, "publish-1")
        self.client.corrupt_reads = False
        self.assertEqual(self.current()["current"], self.baseline_id)

    def test_stale_generation_and_cas_conflict_do_not_overwrite_current(self):
        self.bootstrap()
        with self.assertRaises(ValueError):
            self.execute("publish", 0, "publish-1")
        self.client.race = True
        with self.assertRaises(ValueError):
            self.execute("publish", 1, "publish-1")
        self.assertEqual(self.current()["current"], self.baseline_id)

    def test_lost_conditional_response_is_resolved_with_strong_read(self):
        self.bootstrap()
        self.client.lose_catalog_response = True
        self.assertEqual(self.execute("publish", 1, "publish-1")["current"], self.target)

    def test_dynamic_http_current_history_and_authorization(self):
        self.bootstrap()
        reader = DynamoCatalog("northstar-offline-records", self.baseline_id, lambda: self.client)
        repo = DynamoSnapshotRepository(
            "northstar-offline-records", self.baseline_id, lambda: self.client
        )
        with TestClient(
            create_app(local_demo=True, repository=repo, catalog=reader),
            base_url="http://127.0.0.1",
            client=("127.0.0.1", 50000),
        ) as http:
            self.assertEqual(
                http.get("/api/v1/summary?catalog=true").json()["data"]["current"][
                    "policy_version"
                ],
                "1.0.0",
            )
            self.execute("publish", 1, "publish-1")
            self.assertEqual(
                http.get("/api/v1/summary?catalog=true").json()["data"]["current"][
                    "policy_version"
                ],
                "2.0.0",
            )
            latest = http.get("/api/v1/summary").json()
            self.assertEqual(latest["data"]["account_count"], 11)
            self.assertEqual(latest["metadata"]["policy_version"], "2.0.0")
            legacy = http.get("/api/v1/summary?at=2026-10-31T12:00:00Z").json()
            self.assertEqual(legacy["data"]["account_count"], 10)
            result = http.get("/api/v1/summary?policy_version=2.0.0").json()
            self.assertEqual(
                result["data"]["finding_counts"],
                {"compliant": 43, "noncompliant": 4, "unknown": 9, "stale": 10},
            )
            self.assertEqual(result["metadata"]["snapshot_id"], self.target)
            self.assertEqual(
                http.get("/api/v1/summary?policy_version=1.0.0").json()["data"]["finding_counts"][
                    "compliant"
                ],
                31,
            )
            self.execute("rollback", 2, "rollback-1", self.baseline_id)
            self.assertEqual(
                http.get("/api/v1/summary?catalog=true").json()["data"]["current"][
                    "policy_version"
                ],
                "1.0.0",
            )
            self.assertEqual(http.get("/api/v1/accounts?policy_version=9.0.0").status_code, 404)
        with TestClient(create_app(repository=repo, catalog=reader)) as http:
            self.assertEqual(http.get("/api/v1/summary?catalog=true").status_code, 401)

    def test_missing_catalog_is_fail_closed_and_unregistered_rollback_rejected(self):
        reader = DynamoCatalog("northstar-offline-records", self.baseline_id, lambda: self.client)
        with self.assertRaises(ValueError):
            reader.view()
        self.bootstrap()
        with self.assertRaises(ValueError):
            self.execute("rollback", 1, "rollback-1")

    def test_registry_rejects_version_remap_and_audit_tampering(self):
        value = self.bootstrap()
        bad = copy.deepcopy(value)
        bad["history"][0]["target"] = self.target
        with self.assertRaises(ValueError):
            catalog.validate(bad, self.baseline_id)
        entry = {
            "descriptor": catalog.descriptor(self.v2, self.target),
            "source_commit": self.commit,
        }
        entry["descriptor"]["policy_version"] = "1.0.0"
        with self.assertRaises(ValueError):
            catalog.promote(
                self.client,
                "northstar-offline-records",
                self.baseline_id,
                entry,
                expected_generation=1,
                operation="bad",
                action="publish",
                approved_commit=self.commit,
            )

    def test_deployed_dynamic_configuration_is_lazy_and_cannot_mix_static_selection(self):
        from unittest.mock import patch

        from backend.versions import deployment_catalog

        config = {
            "GOVERNANCE_TABLE": "northstar-offline-records",
            "SNAPSHOT_ID": self.baseline_id,
            "GOVERNANCE_CATALOG_MODE": "dynamodb",
        }
        with patch.object(
            DynamoSnapshotRepository, "_client", side_effect=AssertionError("No SDK on composition")
        ):
            self.assertIsInstance(deployment_catalog(config, None), DynamoCatalog)
        with self.assertRaises(ValueError):
            deployment_catalog({**config, "CURRENT_POLICY_VERSION": "1.0.0"}, None)

    def test_extra_undigested_row_attributes_are_rejected_before_writes(self):
        self.bootstrap()
        bad = copy.deepcopy(self.release)
        bad["publication"]["rows"][0]["unexpected"] = {"S": "not covered by the snapshot document"}
        before = len(self.client.writes)
        with self.assertRaises(ValueError):
            self.execute("publish", 1, "bad-row", package=bad)
        self.assertEqual(len(self.client.writes), before)
