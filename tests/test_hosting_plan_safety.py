"""Reject unsafe live-plan actions before existing Amplify repository integration."""

import copy
import io
import runpy
import unittest
from contextlib import redirect_stdout
from pathlib import Path

GUARD = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "terraform/poc/tests/check_github_hosting_plans.py")
)


def example_plan():
    app = {
        "id": "synthetic-existing-app",
        "name": "northstar-governance-poc",
        "default_domain": "example.com",
        "repository": GUARD["REPOSITORY"],
        "build_spec": "old-build",
        "access_token": None,
        "custom_headers": "unchanged-headers",
        "enable_branch_auto_build": False,
    }
    identity = {
        "callback_urls": ["https://poc.example.com/auth/callback"],
        "logout_urls": ["https://poc.example.com/"],
    }
    cors = {
        "cors_configuration": [
            {
                "allow_origins": ["https://poc.example.com"],
                "allow_headers": ["authorization"],
                "allow_credentials": False,
            }
        ]
    }
    updates = {
        GUARD["IDENTITY"]: (
            identity,
            {
                "callback_urls": identity["callback_urls"]
                + ["https://main.example.com/auth/callback"],
                "logout_urls": identity["logout_urls"] + ["https://main.example.com/"],
            },
        ),
        GUARD["HTTP"]: (
            cors,
            {
                "cors_configuration": [
                    {
                        **cors["cors_configuration"][0],
                        "allow_origins": ["https://poc.example.com", "https://main.example.com"],
                    }
                ]
            },
        ),
    }
    return {
        "resource_changes": [
            {
                "address": GUARD["APP"],
                "change": {
                    "actions": ["no-op"],
                    "before": copy.deepcopy(app),
                    "after": copy.deepcopy(app),
                },
            }
        ]
        + [
            {
                "address": address,
                "change": {"actions": ["update"], "before": before, "after": after},
            }
            for address, (before, after) in updates.items()
        ]
        + [
            {
                "address": GUARD["BRANCH"],
                "change": {
                    "actions": ["create"],
                    "before": None,
                    "after": {
                        "app_id": app["id"],
                        "branch_name": "main",
                        "enable_auto_build": False,
                        "environment_variables": {
                            "VITE_AUTH_MODE": "cognito",
                            "VITE_GOVERNANCE_API_MODE": "baseline-v1",
                            "VITE_APP_ORIGIN": "https://main.example.com",
                        },
                    },
                },
            }
        ]
    }


class HostingPlanSafetyTests(unittest.TestCase):
    def check(self, plan):
        with redirect_stdout(io.StringIO()):
            return GUARD["check_live"](plan)

    def test_preserves_existing_app_and_input_plan(self):
        plan = example_plan()
        original = copy.deepcopy(plan)
        self.assertEqual(len(self.check(plan)), 3)
        self.assertEqual(plan, original)

    def test_replacement_or_unrelated_update_is_rejected(self):
        plan = example_plan()
        plan["resource_changes"][0]["change"]["actions"] = ["delete", "create"]
        with self.assertRaises(ValueError):
            self.check(plan)
        plan = example_plan()
        plan["resource_changes"].append(
            {
                "address": "module.compute.aws_lambda_function.api",
                "change": {"actions": ["update"], "before": {}, "after": {}},
            }
        )
        with self.assertRaises(ValueError):
            self.check(plan)

    def test_changed_app_id_or_security_headers_is_rejected(self):
        for key, value in (("id", "different-app"), ("custom_headers", "changed-headers")):
            with self.subTest(key=key):
                plan = example_plan()
                plan["resource_changes"][0]["change"]["after"][key] = value
                with self.assertRaises(ValueError):
                    self.check(plan)

    def test_removed_original_callback_or_cors_origin_is_rejected(self):
        plan = example_plan()
        plan["resource_changes"][1]["change"]["after"]["callback_urls"] = []
        with self.assertRaises(ValueError):
            self.check(plan)
        plan = example_plan()
        plan["resource_changes"][2]["change"]["after"]["cors_configuration"][0][
            "allow_origins"
        ] = []
        with self.assertRaises(ValueError):
            self.check(plan)

    def test_initial_automatic_build_is_rejected(self):
        plan = example_plan()
        plan["resource_changes"][-1]["change"]["after"]["enable_auto_build"] = True
        with self.assertRaises(ValueError):
            self.check(plan)

    def test_retirement_is_branch_only(self):
        plan = example_plan()
        plan["resource_changes"] = [
            plan["resource_changes"][0],
            {
                "address": GUARD["LEGACY"],
                "change": {
                    "actions": ["delete"],
                    "before": {"branch_name": "poc", "app_id": "synthetic-existing-app"},
                    "after": None,
                },
            },
        ]
        with redirect_stdout(io.StringIO()):
            self.assertEqual(len(GUARD["check_live"](plan, "retire_manual")), 1)
        plan["resource_changes"][0]["change"]["actions"] = ["update"]
        with self.assertRaises(ValueError), redirect_stdout(io.StringIO()):
            GUARD["check_live"](plan, "retire_manual")

    def test_connection_requires_changed_token_and_no_branch_operations(self):
        plan = example_plan()
        app = plan["resource_changes"][0]
        app["change"]["actions"] = ["update"]
        app["change"]["before"]["repository"] = ""
        plan["resource_changes"] = [app]
        with self.assertRaises(ValueError), redirect_stdout(io.StringIO()):
            GUARD["check_live"](plan, "connect_repository")
        app["change"]["after"]["access_token"] = "synthetic-offline-setup-input"
        with redirect_stdout(io.StringIO()):
            self.assertEqual(len(GUARD["check_live"](plan, "connect_repository")), 1)
        app["change"]["before"]["access_token"] = app["change"]["after"]["access_token"]
        with self.assertRaises(ValueError), redirect_stdout(io.StringIO()):
            GUARD["check_live"](plan, "connect_repository")
