"""Version isolation, local rehearsal, immutable publication preparation and authentication."""

import copy
import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app import create_app
from backend.deployment.application import deployed_app
from backend.deployment.snapshot import decode, digest, document, encode, from_document
from backend.repository import FixtureRepository
from backend.versions import LocalCatalog, deployment_catalog
from governance.simulation import launcher, rollout
from governance.simulation.publication import candidate, immutable_file, validate_package
from governance.simulation.terraform_plan import desired


class VersionedDemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state = rollout.plan()
        rollout.approve(cls.state, "sim-security-reviewer")
        rollout.rollout(cls.state, fail_account="sim-account-005")
        rollout.rollout(cls.state)
        rollout.onboard(cls.state)
        cls.plan = {
            "planned_values": {
                "outputs": {"governance_desired": {"value": desired(cls.state, "2.0.0")}}
            }
        }
        cls.v2 = candidate(cls.state, cls.plan)

    def install(self, path):
        with patch.object(launcher, "INTERVIEW", path):
            entries = []
            launcher.install(FixtureRepository().read_snapshot(), entries)
            launcher.install(self.v2, entries)
            launcher.atomic_json(
                path / "catalog.json",
                {"format_version": "1.0.0", "simulated": True, "versions": entries},
            )
        return LocalCatalog(path / "catalog.json")

    def client(self, catalog, demo=True):
        return TestClient(
            create_app(local_demo=demo, catalog=catalog),
            base_url="http://127.0.0.1",
            client=("127.0.0.1", 50000),
        )

    def test_offline_publication_preflight_rejects_tampering_and_v1(self):
        version, rows, marker = encode(self.v2)
        package = {
            "format_version": "1.0.0",
            "simulated": True,
            "snapshot_id": version,
            "policy_version": "2.0.0",
            "rows": rows,
            "manifest": marker,
        }
        self.assertEqual(validate_package(package, version), self.v2)
        changed = copy.deepcopy(package)
        changed["rows"].pop()
        with self.assertRaises(ValueError):
            validate_package(changed, version)
        with self.assertRaises(ValueError):
            validate_package(package, "b" * 64)
        old, rows, marker = encode(FixtureRepository().read_snapshot())
        package.update(snapshot_id=old, policy_version="1.0.0", rows=rows, manifest=marker)
        with self.assertRaises(ValueError):
            validate_package(package, old)

    def test_occupied_ports_never_stop_existing_services(self):
        with (
            patch("socket.socket") as socket,
            patch("subprocess.Popen") as spawn,
            patch("os.killpg") as kill,
        ):
            socket.return_value.__enter__.return_value.connect_ex.return_value = 0
            with self.assertRaisesRegex(ValueError, "occupied"):
                launcher.serve(Path("unused"))
            spawn.assert_not_called()
            kill.assert_not_called()

    def test_current_marker_is_explicit_and_reset_preserves_readable_history(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(launcher, "INTERVIEW", Path(temp)):
            entries = []
            launcher.install(FixtureRepository().read_snapshot(), entries)
            launcher.install(self.v2, entries)
            launcher.promote(entries, "2.0.0", "run-0001")
            catalog = LocalCatalog(Path(temp) / "catalog.json")
            with self.client(catalog) as client:
                current = client.get("/api/v1/summary", params={"catalog": "true"}).json()["data"]
                self.assertEqual(current["current"]["policy_version"], "2.0.0")
                self.assertEqual(current["current_run"], "run-0001")
                launcher.rehearse("reset")
                current = client.get("/api/v1/summary", params={"catalog": "true"}).json()["data"]
                self.assertEqual(current["current"]["policy_version"], "1.0.0")
                self.assertEqual(len(current["versions"]), 2)
                self.assertEqual(
                    client.get("/api/v1/summary", params={"policy_version": "2.0.0"}).json()[
                        "data"
                    ]["account_count"],
                    11,
                )
            index = json.loads((Path(temp) / "catalog.json").read_text())
            index["current_policy_version"] = "9.0.0"
            (Path(temp) / "catalog.json").write_text(json.dumps(index))
            with self.assertRaises(ValueError):
                catalog.view()

    def test_owned_servers_are_reused_without_starting_or_stopping_processes(self):
        with (
            tempfile.TemporaryDirectory() as temp,
            patch.object(launcher, "INTERVIEW", Path(temp)),
            patch("socket.socket") as socket,
            patch("os.kill") as probe,
            patch("os.killpg") as kill,
            patch("subprocess.Popen") as spawn,
        ):
            catalog = Path(temp) / "catalog.json"
            launcher.atomic_json(
                Path(temp) / "servers.json",
                {"launcher": 12345, "children": [12346, 12347], "catalog": str(catalog.resolve())},
            )
            socket.return_value.__enter__.return_value.connect_ex.return_value = 0
            launcher.serve(catalog)
            self.assertEqual(probe.call_count, 3)
            self.assertTrue(all(call.args[1] == 0 for call in probe.call_args_list))
            kill.assert_not_called()
            spawn.assert_not_called()

    def test_legacy_v1_digest_and_new_version_context_roundtrip(self):
        v1 = FixtureRepository().read_snapshot()
        expected = json.loads((rollout.ROOT / "mock-data/snapshot.v1.manifest.json").read_text())[
            "sha256"
        ]
        self.assertEqual(digest(v1), expected)
        self.assertNotEqual(digest(self.v2), expected)
        for snapshot in [v1, self.v2]:
            version, rows, marker = encode(snapshot)
            self.assertEqual(decode([*rows, marker], version), snapshot)
        value = copy.deepcopy(document(self.v2))
        value["context"]["simulated"] = False
        with self.assertRaises(ValueError):
            from_document(value)

    def test_every_data_endpoint_version_metadata_and_unknown_account_isolation(self):
        with tempfile.TemporaryDirectory() as temp, self.client(self.install(Path(temp))) as client:
            for version, count, finding_counts in [
                ("1.0.0", 10, [31, 3, 6, 10]),
                ("2.0.0", 11, [43, 4, 9, 10]),
            ]:
                for endpoint in [
                    "summary",
                    "accounts",
                    "findings",
                    "deployments",
                    "drift",
                    "exceptions",
                    "accounts/sim-account-001",
                ]:
                    response = client.get(f"/api/v1/{endpoint}", params={"policy_version": version})
                    self.assertEqual(response.status_code, 200, response.text)
                    self.assertEqual(response.json()["metadata"]["policy_version"], version)
                    self.assertTrue(response.json()["metadata"]["simulated"])
                data = client.get("/api/v1/summary", params={"policy_version": version}).json()[
                    "data"
                ]
                self.assertEqual(data["account_count"], count)
                self.assertEqual(list(data["finding_counts"].values()), finding_counts)
            self.assertEqual(
                client.get(
                    "/api/v1/accounts/sim-account-011", params={"policy_version": "1.0.0"}
                ).status_code,
                404,
            )
            self.assertEqual(
                client.get(
                    "/api/v1/accounts/sim-account-011", params={"policy_version": "2.0.0"}
                ).status_code,
                200,
            )
            self.assertEqual(
                client.get(
                    "/api/v1/findings",
                    params={"policy_version": "2.0.0", "control_id": "audit-log-integrity"},
                ).json()["pagination"]["total"],
                11,
            )
            self.assertEqual(
                client.get("/api/v1/summary", params={"policy_version": "3.0.0"}).status_code, 404
            )
            self.assertEqual(
                client.get(
                    "/api/v1/summary", params={"policy_version": "../../secrets"}
                ).status_code,
                422,
            )
            self.assertEqual(client.post("/api/v1/summary").status_code, 405)

    def test_evidence_times_journal_default_compatibility_and_determinism(self):
        with tempfile.TemporaryDirectory() as temp, self.client(self.install(Path(temp))) as client:
            baseline = client.get("/api/v1/summary").json()
            self.assertEqual(
                set(baseline["metadata"]), {"api_version", "source", "simulated", "evaluated_at"}
            )
            params = {"policy_version": "2.0.0"}
            a = client.get("/api/v1/summary", params=params).json()
            self.assertEqual(a, client.get("/api/v1/summary", params=params).json())
            self.assertEqual(a["metadata"]["evaluated_at"], "2026-10-31T12:28:00Z")
            self.assertTrue(a["metadata"]["evidence_timestamps"])
            self.assertTrue(any(e["action"] == "rollout.blocked" for e in a["data"]["journal"]))
            self.assertEqual(
                len(
                    client.get("/api/v1/summary", params={"catalog": "true"}).json()["data"][
                        "versions"
                    ]
                ),
                2,
            )

    def test_unavailable_or_tampered_v2_never_falls_back_to_v1(self):
        with tempfile.TemporaryDirectory() as temp:
            catalog = self.install(Path(temp))
            file = catalog.entries()["2.0.0"].repository.path
            file.write_text("{}")
            with self.client(catalog) as client:
                self.assertEqual(
                    client.get("/api/v1/summary", params={"policy_version": "2.0.0"}).status_code,
                    500,
                )
                self.assertEqual(client.get("/api/v1/summary").status_code, 200)

    def test_catalogue_does_not_bypass_auth_or_create_sdk_client(self):
        with tempfile.TemporaryDirectory() as temp:
            catalog = self.install(Path(temp))
            with (
                patch("boto3.client", side_effect=AssertionError("AWS forbidden")),
                self.client(catalog, demo=False) as client,
            ):
                self.assertEqual(
                    client.get(
                        "/api/v1/summary", params={"policy_version": "2.0.0", "catalog": "true"}
                    ).status_code,
                    401,
                )
            config = {
                "GOVERNANCE_TABLE": "northstar-test-records",
                "SNAPSHOT_ID": "a" * 64,
                "GATEWAY_API_ID": "offline",
                "GATEWAY_STAGE": "poc",
                "COGNITO_ISSUER": "offline",
                "COGNITO_CLIENT_ID": "offline",
                "LOCAL_DEMO": "true",
                "GOVERNANCE_VERSIONS_JSON": json.dumps(
                    [{k: v for k, v in catalog.entries()["2.0.0"].descriptor().items()}]
                ),
            }
            with (
                patch("boto3.client", side_effect=AssertionError("AWS forbidden")),
                TestClient(deployed_app(config)) as client,
            ):
                self.assertEqual(
                    client.get("/api/v1/summary", params={"policy_version": "2.0.0"}).status_code,
                    401,
                )
            config["GOVERNANCE_VERSIONS_JSON"] = json.dumps(
                [
                    {
                        "policy_version": "1.0.0",
                        "profile": "v1",
                        "evaluated_at": rollout.REFERENCE_AT,
                        "generator": "northstar-synthetic-v1",
                        "snapshot_id": "b" * 64,
                    }
                ]
            )
            with self.assertRaises(ValueError):
                deployment_catalog(config, FixtureRepository())

    def test_preparation_requires_approval_completed_run_and_verified_desired_plan(self):
        bad = copy.deepcopy(self.plan)
        bad["planned_values"]["outputs"]["governance_desired"]["value"]["proposal_digest"] = "wrong"
        with self.assertRaises(ValueError):
            candidate(self.state, bad)
        with self.assertRaises(ValueError):
            candidate(rollout.plan(), self.plan)
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / "immutable.json"
            immutable_file(file, {"simulated": True})
            immutable_file(file, {"simulated": True})
            with self.assertRaises(ValueError):
                immutable_file(file, {"simulated": False})

    @unittest.skipUnless(shutil.which("terraform"), "Terraform required for one-command rehearsal")
    def test_launcher_replay_and_reset_retain_history_without_aws(self):
        with (
            tempfile.TemporaryDirectory() as temp,
            patch.object(launcher, "INTERVIEW", Path(temp)),
            patch.dict(
                os.environ,
                {
                    "TF_DATA_DIR": str(Path(temp) / "unrelated-cache"),
                    "TF_VAR_policy_version": "1.0.0",
                    "TF_CLI_ARGS_plan": "-target=must-never-be-used",
                },
            ),
            patch("boto3.client", side_effect=AssertionError("AWS forbidden")),
            redirect_stdout(io.StringIO()) as output,
        ):
            catalog = launcher.rehearse("v2")
            first = catalog.read_text()
            history = {p.name: p.read_bytes() for p in (Path(temp) / "snapshots").glob("*.json")}
            launcher.rehearse("v2")
            self.assertEqual(
                json.loads(catalog.read_text())["versions"], json.loads(first)["versions"]
            )
            self.assertEqual(json.loads(catalog.read_text())["current_run"], "run-0002")
            self.assertEqual(
                {p.name: p.read_bytes() for p in (Path(temp) / "snapshots").glob("*.json")}, history
            )
            launcher.rehearse("reset")
            self.assertEqual(set(LocalCatalog(catalog).entries()), {"1.0.0", "2.0.0"})
            self.assertEqual(LocalCatalog(catalog).view()[1:], ("1.0.0", "baseline"))
            self.assertEqual(
                {p.name: p.read_bytes() for p in (Path(temp) / "snapshots").glob("*.json")}, history
            )
            self.assertTrue((Path(temp) / "run-0001/state.json").exists())
            self.assertTrue((Path(temp) / "run-0002/state.json").exists())
            self.assertIn("REAL Terraform", output.getvalue())
            self.assertFalse((Path(temp) / "unrelated-cache").exists())
