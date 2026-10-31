"""Offline deployment foundation tests. SDK clients are injected or blocked; no AWS requests."""

import copy
import importlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import hcl2
from fastapi import HTTPException
from fastapi.testclient import TestClient
from hcl2.utils import SerializationOptions
from starlette.requests import Request

from backend.deployment.application import deployed_app
from backend.deployment.dynamodb import DynamoSnapshotRepository
from backend.deployment.identity import GatewayIdentity
from backend.deployment.snapshot import decode, digest
from backend.repository import FixtureRepository
from governance.model.evaluate import evaluate
from scripts.frontend_config import render
from scripts.package_lambda import package, runtime_pins
from scripts.seed_governance import load, main, prepare

ROOT = Path(__file__).resolve().parents[1]
ISSUER = "https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_offline"
CONFIG = {
    "GOVERNANCE_TABLE": "northstar-offline-records",
    "SNAPSHOT_ID": prepare()["snapshot_id"],
    "GATEWAY_API_ID": "offline-api",
    "GATEWAY_STAGE": "poc",
    "COGNITO_ISSUER": ISSUER,
    "COGNITO_CLIENT_ID": "offlinepublicclient",
}


def verified_event():
    return {
        "version": "2.0",
        "requestContext": {
            "apiId": "offline-api",
            "stage": "poc",
            "authorizer": {
                "jwt": {
                    "claims": {
                        "iss": ISSUER,
                        "client_id": "offlinepublicclient",
                        "token_use": "access",
                        "sub": "synthetic-reader",
                        "scope": "openid northstar-governance/read",
                        "cognito:groups": "[governance-readers]",
                    }
                }
            },
        },
    }


def request(event=None, headers=None):
    scope = {
        "type": "http",
        "headers": headers or [],
        "aws.context": SimpleNamespace(aws_request_id="offline"),
    }
    if event is not None:
        scope["aws.event"] = event
    return Request(scope)


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.auth = GatewayIdentity("offline-api", "poc", ISSUER, "offlinepublicclient")

    def test_verified_access_scope_and_group_grant_read_only(self):
        principal = self.auth.authenticate(request(verified_event()))
        self.assertEqual(principal.permissions, frozenset({"governance:read"}))

    def test_headers_cannot_supply_gateway_identity(self):
        with self.assertRaises(HTTPException) as error:
            self.auth.authenticate(
                request(
                    headers=[
                        (b"authorization", b"Bearer arbitrary"),
                        (b"x-cognito-groups", b"governance-readers"),
                    ]
                )
            )
        self.assertEqual(error.exception.status_code, 401)

    def test_wrong_gateway_stage_issuer_client_or_id_token_denied(self):
        for location, field, value in [
            ("context", "apiId", "other"),
            ("context", "stage", "other"),
            ("claims", "iss", "untrusted"),
            ("claims", "client_id", "other"),
            ("claims", "token_use", "id"),
        ]:
            event = verified_event()
            target = (
                event["requestContext"]
                if location == "context"
                else event["requestContext"]["authorizer"]["jwt"]["claims"]
            )
            target[field] = value
            with self.subTest(field=field), self.assertRaises(HTTPException) as error:
                self.auth.authenticate(request(event))
            self.assertEqual(error.exception.status_code, 401)

    def test_scope_and_group_checked_independently(self):
        for field, value in [("scope", "openid"), ("cognito:groups", "[unrelated]")]:
            event = verified_event()
            event["requestContext"]["authorizer"]["jwt"]["claims"][field] = value
            with self.assertRaises(HTTPException) as error:
                self.auth.authenticate(request(event))
            self.assertEqual(error.exception.status_code, 403)
        for groups in [["governance-readers"], '["governance-readers"]', "governance-readers"]:
            event = verified_event()
            event["requestContext"]["authorizer"]["jwt"]["claims"]["cognito:groups"] = groups
            self.assertEqual(self.auth.authenticate(request(event)).subject, "synthetic-reader")

    def test_configured_app_denies_without_context_before_sdk_use(self):
        with patch("boto3.client", side_effect=AssertionError("AWS client forbidden")):
            with TestClient(deployed_app(CONFIG)) as client:
                self.assertEqual(
                    client.get(
                        "/api/v1/summary", headers={"Authorization": "Bearer arbitrary"}
                    ).status_code,
                    401,
                )
            for config in [{}, {**CONFIG, "COGNITO_ISSUER": "", "LOCAL_DEMO": "true"}]:
                with TestClient(deployed_app(config)) as client:
                    self.assertEqual(client.get("/api/v1/summary").status_code, 401)

    def test_verified_gateway_integration_uses_snapshot_adapter_and_existing_engine(self):
        app = deployed_app(CONFIG)

        async def trusted_gateway(scope, receive, send):
            scope = {
                **scope,
                "aws.event": verified_event(),
                "aws.context": SimpleNamespace(aws_request_id="offline"),
            }
            await app(scope, receive, send)

        with patch.object(
            DynamoSnapshotRepository,
            "read_snapshot",
            return_value=FixtureRepository().read_snapshot(),
        ):
            with TestClient(trusted_gateway) as client:
                response = client.get("/api/v1/summary")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    response.json()["data"]["finding_counts"],
                    {"compliant": 31, "noncompliant": 3, "unknown": 6, "stale": 10},
                )

    def test_real_mangum_handler_routes_named_stage_and_denies_untrusted_events(self):
        from backend import lambda_handler

        event = verified_event()
        event.update(
            routeKey="GET /api/v1/summary",
            rawPath="/poc/api/v1/summary",
            rawQueryString="",
            headers={"host": "offline.execute-api.eu-central-1.amazonaws.com"},
            isBase64Encoded=False,
        )
        event["requestContext"]["http"] = {
            "method": "GET",
            "path": "/poc/api/v1/summary",
            "sourceIp": "192.0.2.1",
            "protocol": "HTTP/1.1",
        }
        try:
            with patch.dict("os.environ", {**CONFIG, "LOCAL_DEMO": "true"}, clear=True):
                importlib.reload(lambda_handler)
                with patch.object(
                    DynamoSnapshotRepository,
                    "read_snapshot",
                    return_value=FixtureRepository().read_snapshot(),
                ) as read:
                    for path in ["/poc/api/v1/summary", "/api/v1/summary"]:
                        event["requestContext"]["http"]["path"] = path
                        response = lambda_handler.handler(event, SimpleNamespace())
                        self.assertEqual(response["statusCode"], 200)
                        self.assertEqual(
                            json.loads(response["body"])["data"]["finding_counts"],
                            {"compliant": 31, "noncompliant": 3, "unknown": 6, "stale": 10},
                        )
                    read.reset_mock()
                    event["requestContext"]["authorizer"] = {}
                    response = lambda_handler.handler(event, SimpleNamespace())
                    self.assertEqual(response["statusCode"], 401)
                    read.assert_not_called()
        finally:
            importlib.reload(lambda_handler)


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.prepared = prepare()
        self.all_rows = [*self.prepared["rows"], self.prepared["manifest"]]

    def test_round_trip_provenance_digest_and_determinism(self):
        version = self.prepared["snapshot_id"]
        restored = decode(self.all_rows, version)
        original = FixtureRepository().read_snapshot()
        self.assertEqual(restored, original)
        self.assertEqual(prepare(), self.prepared)
        self.assertEqual(
            json.loads((ROOT / "mock-data/snapshot.v1.manifest.json").read_text())["sha256"],
            digest(original),
        )
        self.assertEqual(
            evaluate(
                restored.fleet, restored.policy, restored.environments, at="2026-10-31T12:00:00Z"
            ),
            evaluate(
                original.fleet, original.policy, original.environments, at="2026-10-31T12:00:00Z"
            ),
        )

    def test_partial_duplicate_or_tampered_snapshot_rejected(self):
        for rows in [self.all_rows[:-1], self.all_rows[1:], self.all_rows + [self.all_rows[0]]]:
            with self.assertRaises((KeyError, ValueError)):
                decode(rows, self.prepared["snapshot_id"])
        rows = copy.deepcopy(self.all_rows)
        record = json.loads(rows[0]["payload"]["S"])
        record["id"] = "tampered"
        rows[0]["payload"]["S"] = json.dumps(record)
        with self.assertRaises(ValueError):
            decode(rows, self.prepared["snapshot_id"])

    def test_paginated_consistent_query_without_scans(self):
        rows = self.all_rows
        calls = []

        class Client:
            def query(self, **kwargs):
                calls.append(kwargs)
                return (
                    {"Items": rows[:30], "LastEvaluatedKey": {"pk": {"S": "cursor"}}}
                    if len(calls) == 1
                    else {"Items": rows[30:]}
                )

        repository = DynamoSnapshotRepository(
            CONFIG["GOVERNANCE_TABLE"], self.prepared["snapshot_id"], lambda: Client()
        )
        self.assertEqual(repository.read_snapshot(), FixtureRepository().read_snapshot())
        self.assertTrue(all(c["ConsistentRead"] for c in calls))
        self.assertIn("ExclusiveStartKey", calls[1])
        self.assertEqual(
            calls[0]["ExpressionAttributeValues"][":pk"]["S"],
            f"SNAPSHOT#{self.prepared['snapshot_id']}",
        )

    def test_sdk_not_created_by_repository_constructor(self):
        with patch("boto3.client", side_effect=AssertionError("AWS forbidden")):
            DynamoSnapshotRepository(CONFIG["GOVERNANCE_TABLE"], CONFIG["SNAPSHOT_ID"])
        with self.assertRaises(ValueError):
            DynamoSnapshotRepository("unrelated", CONFIG["SNAPSHOT_ID"])

    def test_unseeded_partial_or_unavailable_data_returns_sanitized_error(self):
        async def trusted_gateway(scope, receive, send):
            await app(
                {
                    **scope,
                    "aws.event": verified_event(),
                    "aws.context": SimpleNamespace(),
                },
                receive,
                send,
            )

        for response in [
            {"Items": []},
            {"Items": self.all_rows[:-1]},
            RuntimeError("private-path"),
        ]:
            fake = SimpleNamespace()
            if isinstance(response, Exception):
                fake.query = Mock(side_effect=response)
            else:
                fake.query = Mock(return_value=response)
            with patch.object(DynamoSnapshotRepository, "_client", return_value=fake):
                app = deployed_app(CONFIG)
                with TestClient(trusted_gateway) as client:
                    result = client.get("/api/v1/summary")
                    self.assertEqual(result.status_code, 500)
                    self.assertEqual(
                        result.json(),
                        {
                            "error": {
                                "code": "internal_error",
                                "message": "An internal error occurred",
                            }
                        },
                    )

    def test_loader_conditional_idempotent_and_manifest_last(self):
        class Conflict(Exception):
            pass

        class Client:
            exceptions = SimpleNamespace(ConditionalCheckFailedException=Conflict)

            def __init__(self):
                self.items, self.order = {}, []

            def put_item(self, **kwargs):
                self.assert_condition = kwargs["ConditionExpression"]
                item = kwargs["Item"]
                key = item["sk"]["S"]
                if key in self.items:
                    raise Conflict
                self.items[key] = item
                self.order.append(key)

            def get_item(self, **kwargs):
                return {"Item": self.items[kwargs["Key"]["sk"]["S"]]}

        client = Client()
        load(client, CONFIG["GOVERNANCE_TABLE"], self.prepared)
        self.assertEqual(client.order[-1], "MANIFEST")
        load(client, CONFIG["GOVERNANCE_TABLE"], self.prepared)
        self.assertEqual(len(client.items), len(self.all_rows))
        self.assertIn("attribute_not_exists", client.assert_condition)
        first = next(iter(client.items))
        client.items[first] = {**client.items[first], "payload": {"S": "different"}}
        with self.assertRaises(ValueError):
            load(client, CONFIG["GOVERNANCE_TABLE"], self.prepared)

    def test_interrupted_loader_never_publishes_manifest(self):
        class Client:
            exceptions = SimpleNamespace(
                ConditionalCheckFailedException=type("Conflict", (Exception,), {})
            )

            def put_item(self, **kwargs):
                raise RuntimeError("simulated interruption")

        with self.assertRaises(RuntimeError):
            load(Client(), CONFIG["GOVERNANCE_TABLE"], self.prepared)

    def test_default_seed_is_offline_and_execute_needs_confirmation(self):
        with (
            tempfile.TemporaryDirectory() as temp,
            patch("boto3.client", side_effect=AssertionError("AWS forbidden")),
        ):
            output = Path(temp) / "seed.json"
            with patch("sys.argv", ["seed", "--output", str(output)]):
                main()
            self.assertEqual(json.loads(output.read_text())["snapshot_id"], CONFIG["SNAPSHOT_ID"])
            with (
                patch(
                    "sys.argv", ["seed", "--execute", "--table-name", "northstar-offline-records"]
                ),
                self.assertRaises(SystemExit),
            ):
                main()


class PackagingAndTerraformTests(unittest.TestCase):
    def test_reproducible_zip_and_no_fixtures_or_credentials(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name, version in runtime_pins().items():
                dist = root / "vendor" / (name.replace("-", "_") + "-offline.dist-info")
                dist.mkdir(parents=True)
                (dist / "METADATA").write_text(f"Name: {name}\nVersion: {version}\n")
                (dist / "WHEEL").write_text("Tag: cp313-cp313-manylinux2014_aarch64\n")
            vendor_tests = root / "vendor/example/tests"
            vendor_tests.mkdir(parents=True)
            (vendor_tests / "test_example.py").write_text("TEST_ONLY = True\n")
            first = package(root / "vendor", root / "a.zip")
            second = package(root / "vendor", root / "b.zip")
            self.assertEqual(first, second)
            with zipfile.ZipFile(root / "a.zip") as archive:
                self.assertIn("backend/lambda_handler.py", archive.namelist())
                self.assertIn("governance/contracts/v1.schema.json", archive.namelist())
                self.assertFalse(
                    any(n.startswith(("mock-data/", "tests/", ".aws/")) for n in archive.namelist())
                )
                self.assertNotIn("example/tests/test_example.py", archive.namelist())
            (root / "vendor/pydantic_core-offline.dist-info/WHEEL").write_text(
                "Tag: cp313-cp313-macosx_11_0_arm64\n"
            )
            with self.assertRaises(ValueError):
                package(root / "vendor", root / "bad.zip")

    def test_public_configuration_export_has_no_secret_surface(self):
        settings = {
            "VITE_AUTH_MODE": "cognito",
            "VITE_API_BASE_URL": "https://offline.execute-api.eu-central-1.amazonaws.com/poc",
            "VITE_COGNITO_ISSUER": ISSUER,
            "VITE_COGNITO_CLIENT_ID": "offlinepublicclient",
            "VITE_COGNITO_DOMAIN": "https://offline.auth.eu-central-1.amazoncognito.com",
            "VITE_APP_ORIGIN": "https://poc.example.invalid",
        }
        self.assertIn("VITE_AUTH_MODE", render(settings))
        for invalid in [
            {**settings, "AWS_SECRET_ACCESS_KEY": "forbidden"},
            {**settings, "VITE_API_BASE_URL": "http://insecure.invalid"},
            {
                **settings,
                "VITE_API_BASE_URL": "https://offline.execute-api.us-east-1.amazonaws.com/poc",
            },
        ]:
            with self.assertRaises(ValueError):
                render(invalid)

    def test_hcl_security_boundaries_and_no_enterprise_resources(self):
        resources = {}
        for path in (ROOT / "terraform").rglob("*.tf"):
            if ".terraform" in path.parts:
                continue
            config = hcl2.loads(
                path.read_text(),
                serialization_options=SerializationOptions(
                    strip_string_quotes=True, explicit_blocks=False, with_comments=False
                ),
            )
            self.assertNotIn("data", config, path)
            for item in config.get("resource", []):
                for kind, names in item.items():
                    resources.update({(kind, name): value for name, value in names.items()})
        forbidden = [
            "aws_vpc",
            "aws_nat_gateway",
            "aws_organizations_organization",
            "aws_ec2_transit_gateway",
            "aws_lambda_function_url",
        ]
        self.assertFalse(any(kind in forbidden for kind, _ in resources))
        routes = resources["aws_apigatewayv2_route", "reads"]
        self.assertEqual(routes["authorization_type"], "JWT")
        self.assertEqual(routes["authorization_scopes"], ["northstar-governance/read"])
        spa = resources["aws_cognito_user_pool_client", "spa"]
        self.assertFalse(spa["generate_secret"])
        self.assertEqual(spa["allowed_oauth_flows"], ["code"])
        table = resources["aws_dynamodb_table", "governance"]
        self.assertEqual(table["billing_mode"], "PAY_PER_REQUEST")
        self.assertTrue(table["server_side_encryption"][0]["enabled"])
        self.assertTrue(table["deletion_protection_enabled"])
        runtime = resources["aws_iam_role_policy", "runtime"]["policy"]
        self.assertIn("dynamodb:Query", runtime)
        self.assertNotIn("dynamodb:PutItem", runtime)
        self.assertNotIn("dynamodb:Scan", runtime)
        self.assertNotIn(
            "AWS_ACCESS_KEY", resources["aws_lambda_function", "api"]["environment"][0]["variables"]
        )


if __name__ == "__main__":
    unittest.main()
