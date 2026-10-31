"""Offline API integration, security and contract tests. No cloud calls."""

import copy
import unittest
from collections import Counter
from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.api.models import Account, Envelope, Finding, Page, Summary
from backend.app import create_app
from backend.auth import Principal
from backend.lambda_handler import handler
from backend.repository import FixtureRepository
from governance.model.evaluate import evaluate, load_model

AT = "2026-10-31T12:00:00Z"
PATHS = [
    "/api/v1/health",
    "/api/v1/summary",
    "/api/v1/accounts",
    "/api/v1/accounts/sim-account-002",
    "/api/v1/findings",
    "/api/v1/deployments",
    "/api/v1/drift",
    "/api/v1/exceptions",
    "/docs",
    "/openapi.json",
]


def client(app, host="127.0.0.1"):
    return TestClient(
        app, base_url="http://127.0.0.1", client=(host, 50000), raise_server_exceptions=False
    )


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(local_demo=True)
        self.client = client(self.app)
        self.addCleanup(self.client.close)

    def test_all_endpoints_and_simulation_metadata(self):
        for path in PATHS[:8]:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(
                    response.json()["metadata"],
                    {
                        "api_version": "v1",
                        "source": "northstar-synthetic-v1",
                        "simulated": True,
                        "evaluated_at": AT,
                    },
                )
                self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(
            self.client.get(PATHS[0]).json()["data"]["authentication_mode"], "local-demo"
        )

    def test_default_denies_all_surfaces_and_tokens(self):
        with client(create_app()) as locked:
            for path in PATHS:
                for headers in [{}, {"Authorization": "Bearer arbitrary-not-a-jwt"}]:
                    with self.subTest(path=path, headers=headers):
                        self.assertEqual(locked.get(path, headers=headers).status_code, 401)

    def test_demo_rejects_tokens_remote_clients_and_bad_hosts(self):
        self.assertEqual(
            self.client.get(PATHS[1], headers={"Authorization": "Bearer arbitrary"}).status_code,
            401,
        )
        self.assertEqual(
            self.client.get(PATHS[1], headers={"Host": "untrusted.invalid"}).status_code, 403
        )
        with client(create_app(local_demo=True), host="192.0.2.10") as remote:
            self.assertEqual(
                remote.get(PATHS[1], headers={"X-Forwarded-For": "127.0.0.1"}).status_code, 403
            )

    def test_demo_rejects_malformed_or_duplicate_host(self):
        for host in [
            "localhost@untrusted.invalid",
            "localhost/path",
            "untrusted.invalid/localhost",
            "127.0.0.1#untrusted.invalid",
        ]:
            with self.subTest(host=host):
                self.assertEqual(self.client.get(PATHS[1], headers={"Host": host}).status_code, 403)
        response = self.client.get(
            PATHS[1], headers=[("Host", "127.0.0.1"), ("Host", "untrusted.invalid")]
        )
        self.assertEqual(response.status_code, 403)
        for host in ["localhost", "127.0.0.1:8000", "[::1]:8000"]:
            with self.subTest(host=host):
                self.assertEqual(self.client.get(PATHS[1], headers={"Host": host}).status_code, 200)

    def test_server_side_scope_check(self):
        class NoReadPermission:
            def authenticate(self, request):
                return Principal("test-user", frozenset())

        with client(create_app(authenticator=NoReadPermission())) as forbidden:
            for path in PATHS:
                self.assertEqual(forbidden.get(path).status_code, 403)
        with self.assertRaises(ValueError):
            create_app(local_demo=True, authenticator=NoReadPermission())

    def test_all_methods_and_unknown_paths_require_auth(self):
        with client(create_app()) as locked:
            for method in ["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]:
                for path in [PATHS[1], "/not-an-endpoint"]:
                    with self.subTest(method=method, path=path):
                        response = locked.request(method, path)
                        self.assertEqual(response.status_code, 401)
                        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_untrusted_authenticator_error_is_sanitized(self):
        class BrokenAuthenticator:
            def authenticate(self, request):
                raise RuntimeError("/private/identity/key sensitive-detail")

        with client(create_app(authenticator=BrokenAuthenticator())) as broken:
            response = broken.get(PATHS[1])
            self.assertEqual(response.status_code, 500)
            self.assertEqual(response.json()["error"]["message"], "An internal error occurred")
            self.assertNotIn("private", response.text)

    def test_summary_known_totals(self):
        payload = self.client.get(PATHS[1]).json()
        Envelope[Summary].model_validate(payload)
        self.assertEqual(
            payload["data"],
            {
                "account_count": 10,
                "finding_count": 50,
                "account_counts": {"compliant": 3, "noncompliant": 3, "unknown": 2, "stale": 2},
                "finding_counts": {"compliant": 31, "noncompliant": 3, "unknown": 6, "stale": 10},
                "environment_counts": {
                    "production": 3,
                    "pre-production": 2,
                    "testing": 2,
                    "development": 3,
                },
            },
        )

    def test_accounts_filters_and_pagination(self):
        for env, count in [
            ("production", 3),
            ("pre-production", 2),
            ("testing", 2),
            ("development", 3),
        ]:
            page = self.client.get(PATHS[2], params={"environment": env}).json()
            self.assertEqual(page["pagination"]["total"], count)
            self.assertTrue(all(row["account"]["environment"] == env for row in page["data"]))
        r = self.client.get(PATHS[2], params={"lifecycle_status": "onboarding"}).json()
        self.assertEqual(r["data"][0]["account"]["id"], "sim-account-007")
        r = self.client.get(PATHS[2], params={"compliance_status": "noncompliant"}).json()
        self.assertEqual(r["pagination"]["total"], 3)
        first = self.client.get(PATHS[2], params={"limit": 3}).json()
        second = self.client.get(
            PATHS[2], params={"limit": 3, "offset": first["pagination"]["next_offset"]}
        ).json()
        self.assertEqual(
            first["pagination"], {"total": 10, "limit": 3, "offset": 0, "next_offset": 3}
        )
        self.assertTrue(
            set(r["account"]["id"] for r in first["data"]).isdisjoint(
                r["account"]["id"] for r in second["data"]
            )
        )
        empty = self.client.get(PATHS[2], params={"offset": 100}).json()
        self.assertEqual(empty["data"], [])
        self.assertIsNone(empty["pagination"]["next_offset"])

    def test_account_details_keep_violation_and_exception(self):
        result = self.client.get(PATHS[3]).json()["data"]
        self.assertEqual(result["ou"]["environment"], "production")
        self.assertEqual(result["compliance"]["status"], "noncompliant")
        self.assertEqual(result["compliance"]["exceptions"], [{"id": "exc-002", "state": "active"}])
        self.assertEqual(len(result["findings"]), 5)
        self.assertEqual(
            next(f for f in result["findings"] if f["control_id"] == "baseline-encryption")[
                "status"
            ],
            "noncompliant",
        )

    def test_findings_filters_and_contracts(self):
        params = {
            "account_id": "sim-account-002",
            "environment": "production",
            "control_id": "baseline-encryption",
            "status": "noncompliant",
        }
        result = self.client.get(PATHS[4], params=params)
        Page[Finding].model_validate(result.json())
        self.assertEqual(result.json()["pagination"]["total"], 1)
        for status, count in [
            ("compliant", 31),
            ("noncompliant", 3),
            ("unknown", 6),
            ("stale", 10),
        ]:
            page = self.client.get(PATHS[4], params={"status": status, "limit": 100}).json()
            self.assertEqual(page["pagination"]["total"], count)
            self.assertTrue(all(f["status"] == status for f in page["data"]))
        self.assertEqual(
            self.client.get(
                PATHS[4], params={"account_id": "sim-account-002", "environment": "testing"}
            ).json()["data"],
            [],
        )

    def test_record_endpoints_filters_and_pagination(self):
        for path, count in [(PATHS[5], 10), (PATHS[6], 1), (PATHS[7], 2)]:
            with self.subTest(path=path):
                payload = self.client.get(path, params={"limit": 1}).json()
                self.assertEqual(payload["pagination"]["total"], count)
                self.assertEqual(len(payload["data"]), 1)
                rows = self.client.get(
                    path, params={"environment": "production", "account_id": "sim-account-002"}
                ).json()["data"]
                for row in rows:
                    self.assertEqual(row.get("exception", row)["account_id"], "sim-account-002")
                self.assertEqual(self.client.get(path, params={"offset": 100}).json()["data"], [])
        failure = next(
            d for d in self.client.get(PATHS[5]).json()["data"] if d["status"] == "failed"
        )
        self.assertTrue(failure["simulated"])
        self.assertNotEqual(failure["observed_revision"], failure["desired_revision"])

    def test_exception_expiration_states_reuse_evaluator(self):
        rows = self.client.get(PATHS[7]).json()["data"]
        self.assertEqual([r["expiration_state"]["state"] for r in rows], ["active", "expired"])
        rows = self.client.get(PATHS[7], params={"at": "2026-11-15T00:00:00Z"}).json()["data"]
        self.assertEqual([r["expiration_state"]["state"] for r in rows], ["expired", "expired"])
        violation = self.client.get("/api/v1/accounts/sim-account-008").json()["data"]["compliance"]
        self.assertEqual(violation["status"], "noncompliant")

    def test_unknown_and_malformed_ids(self):
        self.assertEqual(self.client.get("/api/v1/accounts/sim-account-999").status_code, 404)
        self.assertEqual(self.client.get("/api/v1/accounts/not-an-account").status_code, 422)
        for path in PATHS[4:8]:
            self.assertEqual(
                self.client.get(path, params={"account_id": "sim-account-999"}).status_code, 404
            )
            self.assertEqual(
                self.client.get(path, params={"account_id": "not-an-account"}).status_code, 422
            )

    def test_invalid_filters_pagination_timestamp_and_unknown_parameters(self):
        cases = [
            (PATHS[0], {"unexpected": "ignored?"}),
            (PATHS[2], {"limit": 0}),
            (PATHS[2], {"limit": 101}),
            (PATHS[2], {"offset": -1}),
            (PATHS[2], {"offset": 1000001}),
            (PATHS[2], {"environment": "unknown"}),
            (PATHS[2], {"lifecycle_status": "unknown"}),
            (PATHS[2], {"compliance_status": "unknown-status"}),
            (PATHS[4], {"control_id": "unknown"}),
            (PATHS[4], {"status": "passing"}),
            (PATHS[1], {"at": "2026-10-31T12:00:00"}),
            (PATHS[1], {"at": "not-time"}),
            (PATHS[1], {"at": "9999-12-31T23:59:59-12:00"}),
            (PATHS[1], {"at": "0001-01-01T00:00:00+12:00"}),
            (PATHS[1], {"at": "1793448000"}),
            (PATHS[1], {"at": "2026-09-01T12:00:00Z"}),
            (PATHS[2], {"unexpected": "ignored?"}),
        ]
        for path, params in cases:
            with self.subTest(path=path, params=params):
                response = self.client.get(path, params=params)
                self.assertEqual(response.status_code, 422, response.text)
                self.assertNotIn("ignored?", response.text)
        self.assertEqual(self.client.get(PATHS[2] + "?limit=1&limit=2").status_code, 422)

    def test_determinism_and_phase_one_parity(self):
        params = {"limit": 100, "at": AT}
        a = self.client.get(PATHS[4], params=params)
        b = self.client.get(PATHS[4], params=params)
        self.assertEqual(a.content, b.content)
        self.assertEqual(a.json()["data"], evaluate(*load_model(), at=AT))
        equivalent = self.client.get(
            PATHS[4], params={"limit": 100, "at": "2026-10-31T15:00:00+03:00"}
        )
        self.assertEqual(a.content, equivalent.content)
        self.assertEqual(
            Counter(f["status"] for f in a.json()["data"]),
            {"compliant": 31, "noncompliant": 3, "unknown": 6, "stale": 10},
        )

    def test_safe_error_handling(self):
        class BrokenRepository:
            def read_snapshot(self):
                raise RuntimeError("/private/sensitive/path secret-detail")

        with client(create_app(local_demo=True, repository=BrokenRepository())) as broken:
            r = broken.get(PATHS[1])
            self.assertEqual(r.status_code, 500)
            self.assertEqual(
                r.json(),
                {"error": {"code": "internal_error", "message": "An internal error occurred"}},
            )
            self.assertNotIn("private", r.text)
        self.assertEqual(self.client.get("/not-an-endpoint").status_code, 404)
        self.assertEqual(self.client.post(PATHS[2], json={}).status_code, 405)

    def test_bad_data_is_internal_error_not_client_error(self):
        class InvalidRepository(FixtureRepository):
            def read_snapshot(self):
                snapshot = super().read_snapshot()
                snapshot.fleet["accounts"][0]["ou_id"] = "missing-ou"
                return snapshot

        with client(create_app(local_demo=True, repository=InvalidRepository())) as broken:
            self.assertEqual(broken.get(PATHS[1]).status_code, 500)

    def test_response_schema_rejects_bad_records(self):
        account = copy.deepcopy(load_model()[0]["accounts"][0])
        account["simulated"] = False
        with self.assertRaises(ValidationError):
            Account.model_validate(account)
        finding = evaluate(*load_model(), at=AT)[0]
        finding["unexpected"] = True
        with self.assertRaises(ValidationError):
            Finding.model_validate(finding)

    def test_repository_request_isolation(self):
        repository = FixtureRepository()
        first = repository.read_snapshot()
        first.fleet["accounts"].clear()
        self.assertEqual(len(repository.read_snapshot().fleet["accounts"]), 10)

    def test_openapi_documentation_and_schemas(self):
        schema = self.client.get("/openapi.json").json()
        self.assertEqual(len(schema["paths"]), 8)
        self.assertIn("pagination", str(schema["components"]["schemas"]))
        self.assertEqual(self.client.get("/docs").status_code, 200)
        self.assertNotIn("post", schema["paths"][PATHS[2]])

    def test_launcher_is_loopback_and_demo_is_opt_in(self):
        from backend.__main__ import main

        for args, expected in [
            (["backend"], "disabled"),
            (["backend", "--local-demo"], "local-demo"),
        ]:
            with patch("sys.argv", args), patch("backend.__main__.uvicorn.run") as run:
                main()
                self.assertEqual(run.call_args.kwargs["host"], "127.0.0.1")
                self.assertFalse(run.call_args.kwargs["proxy_headers"])
                self.assertEqual(run.call_args.args[0].state.authentication_mode, expected)

    def test_lambda_entry_point_is_fail_closed(self):
        event = {
            "version": "2.0",
            "routeKey": "GET /api/v1/summary",
            "rawPath": "/api/v1/summary",
            "rawQueryString": "",
            "headers": {"host": "example.invalid"},
            "requestContext": {
                "http": {
                    "method": "GET",
                    "path": "/api/v1/summary",
                    "sourceIp": "127.0.0.1",
                    "protocol": "HTTP/1.1",
                },
                "stage": "$default",
            },
            "isBase64Encoded": False,
        }
        # Warm invocations and attacker-controlled headers cannot activate demo identity.
        for headers in [{}, {"authorization": "Bearer arbitrary", "x-forwarded-for": "127.0.0.1"}]:
            event["headers"].update(headers)
            with patch.dict("os.environ", {"LOCAL_DEMO": "true", "NORTHSTAR_LOCAL_DEMO": "true"}):
                response = handler(event, {})
            self.assertEqual(response["statusCode"], 401)


if __name__ == "__main__":
    unittest.main()
