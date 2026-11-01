"""Verify mock-plan scope and read-only live-plan safety for existing-app integration."""

import copy
import json
import sys
from pathlib import Path

APP = "module.hosting.aws_amplify_app.console"
BRANCH = "aws_amplify_branch.github_main[0]"
LEGACY = "aws_amplify_branch.poc[0]"
IDENTITY = "module.identity.aws_cognito_user_pool_client.spa"
HTTP = "module.http.aws_apigatewayv2_api.governance"
REPOSITORY = "https://github.com/bosphorus-cloud-labs/northstar-airlines-aws-landing-zone"


def strip_allowed(change, address):
    for key in ("after", "after_unknown", "after_sensitive"):
        values = change.get(key, {})
        if address == APP:
            for attribute in ("repository", "access_token", "build_spec"):
                values.pop(attribute, None)
        elif address == IDENTITY:
            values.pop("callback_urls", None)
            values.pop("logout_urls", None)
        elif address == HTTP:
            for cors in values.get("cors_configuration", []):
                cors.pop("allow_origins", None)


def check(path):
    plans = {
        item["@testrun"]: {
            resource["address"]: resource["change"]
            for resource in item["test_plan"]["resource_changes"]
        }
        for line in Path(path).read_text().splitlines()
        if (item := json.loads(line)).get("type") == "test_plan"
        and item["@testfile"] == "tests/github_hosting.tftest.hcl"
    }
    baseline, staged = [
        plans[name] for name in ("github_hosting_disabled", "github_hosting_staged")
    ]
    if set(staged) - set(baseline) != {BRANCH} or set(baseline) - set(staged) != {LEGACY}:
        raise ValueError(
            "Expected manual branch retirement and main creation across separate checkpoints; never another app"
        )
    for address in baseline.keys() & staged.keys():
        before, after = [copy.deepcopy(plan[address]) for plan in (baseline, staged)]
        strip_allowed(before, address)
        strip_allowed(after, address)
        if before != after:
            raise ValueError(f"Unexpected existing-resource difference: {address}")
    app, branch = [staged[address]["after"] for address in (APP, BRANCH)]
    if not (
        app["repository"] == REPOSITORY
        and app["name"] == "northstar-governance-poc"
        and app["platform"] == "WEB"
        and app["build_spec"] == Path("amplify.yml").read_text()
        and app["access_token"] is None
        and not app["enable_branch_auto_build"]
        and branch["app_id"] == app["id"]
        and branch["branch_name"] == "main"
        and not branch["enable_auto_build"]
        and not branch["enable_pull_request_preview"]
    ):
        raise ValueError(
            "Use the existing app/main branch with the reviewed build and disabled triggers"
        )
    environment = branch["environment_variables"]
    environment_keys = set(environment) | set(
        staged[BRANCH].get("after_unknown", {}).get("environment_variables", {})
    )
    if {key for key in environment_keys if key.startswith("VITE_")} != {
        "VITE_AUTH_MODE",
        "VITE_API_BASE_URL",
        "VITE_COGNITO_ISSUER",
        "VITE_COGNITO_CLIENT_ID",
        "VITE_COGNITO_DOMAIN",
        "VITE_APP_ORIGIN",
        "VITE_GOVERNANCE_API_MODE",
    } or environment["VITE_APP_ORIGIN"] != "https://main.synthetic.amplifyapp.com":
        raise ValueError("Expected six public settings and the main-branch origin")
    if environment["VITE_GOVERNANCE_API_MODE"] != "baseline-v1":
        raise ValueError("Migration main must use the reviewed V1 compatibility mode")
    if (
        environment["VITE_AUTH_MODE"] != "cognito"
        or environment["AMPLIFY_MONOREPO_APP_ROOT"] != "frontend"
    ):
        raise ValueError("Never enable local-demo authentication in Amplify")
    if plans["github_auto_build_separately_enabled"][APP]["after"]["enable_branch_auto_build"]:
        raise ValueError("Do not enable app-wide default builds; activate main separately")
    retired = plans["retire_manual_checkpoint"]
    if set(baseline) - set(retired) != {LEGACY} or set(retired) - set(baseline):
        raise ValueError("Stage A mock configuration must remove only the manual branch")
    for address in retired:
        if retired[address] != baseline[address]:
            raise ValueError("Stage A must preserve all other mocked configuration")
    connected = plans["connect_repository_checkpoint"]
    if set(connected) != set(retired):
        raise ValueError("Stage B must not create any resource")
    for address in connected:
        left, right = [copy.deepcopy(items[address]) for items in (retired, connected)]
        if address == APP:
            strip_allowed(left, APP)
            strip_allowed(right, APP)
        if left != right:
            raise ValueError("Stage B changes must be limited to existing app connection")
    print(
        "Mock scope verified: one new main branch; existing app repository/build and identity/CORS only."
    )


def check_live(plan, stage="create_main"):
    """Accept parsed show -json in memory; never print tokens, plans or state."""
    changes = {
        item["address"]: item["change"]
        for item in plan["resource_changes"]
        if item["change"]["actions"] not in (["no-op"], ["read"])
    }
    expectations = {
        "retire_manual": {LEGACY: ["delete"]},
        "connect_repository": {APP: ["update"]},
        "create_main": {BRANCH: ["create"], IDENTITY: ["update"], HTTP: ["update"]},
    }
    expected = expectations[stage]
    if {address: change["actions"] for address, change in changes.items()} != expected:
        raise ValueError(
            "STOP: plan does not match the single migration checkpoint; do not combine retirement, connection and main creation"
        )
    app = next(item["change"] for item in plan["resource_changes"] if item["address"] == APP)
    if stage == "create_main" and app["before"] != app["after"]:
        raise ValueError("STOP: Stage C must preserve the already-connected app exactly")
    if stage == "retire_manual":
        if app["actions"] != ["no-op"]:
            raise ValueError("STOP: Stage A must not update or replace the app")
        retired = changes[LEGACY]["before"]
        if retired.get("branch_name") != "poc" or retired.get("app_id") != app["before"]["id"]:
            raise ValueError("STOP: Stage A may delete only poc on the existing app")
        print("Stage A verified: 0 creates, 0 updates, 1 destroy: manual poc branch only.")
        return changes
    if not app["before"]["id"] or app["before"]["id"] != app["after"]["id"]:
        raise ValueError("STOP: original app ID must be retained")
    allowed = {
        APP: {"repository", "access_token", "build_spec"},
        IDENTITY: {"callback_urls", "logout_urls"},
        HTTP: {"cors_configuration"},
    }
    for address, attributes in allowed.items():
        if address not in changes:
            continue
        change = changes[address]
        unknown = change.get("after_unknown", {})
        for key, value in change["before"].items():
            if key in attributes or unknown.get(key):
                continue
            if change["after"].get(key) != value:
                raise ValueError(f"STOP: unrelated change at {address}.{key}")
    if stage == "connect_repository":
        if app["after"]["repository"] != REPOSITORY or app["after"]["enable_branch_auto_build"]:
            raise ValueError("STOP: wrong repository or automatic app builds enabled")
        ready = bool(app["after"].get("access_token")) and app["before"].get("access_token") != app[
            "after"
        ].get("access_token")
        print("Stage B verified: existing app in-place update only. Token will be sent:", ready)
        if not ready:
            raise ValueError(
                "STOP: provider sends access_token only on change; valid changed setup input or an authorized UpdateApp alternative is required"
            )
        return changes
    for key in ("callback_urls", "logout_urls"):
        if not set(changes[IDENTITY]["before"][key]) <= set(changes[IDENTITY]["after"][key]):
            raise ValueError("STOP: existing Cognito URLs removed")
    before_cors = copy.deepcopy(changes[HTTP]["before"]["cors_configuration"])
    after_cors = copy.deepcopy(changes[HTTP]["after"]["cors_configuration"])
    if (
        not set(before_cors[0].pop("allow_origins")) <= set(after_cors[0].pop("allow_origins"))
        or before_cors != after_cors
    ):
        raise ValueError("STOP: existing origins removed or unrelated CORS settings changed")
    branch = changes[BRANCH]["after"]
    if (
        app["after"]["repository"] != REPOSITORY
        or branch["app_id"] != app["before"]["id"]
        or branch["branch_name"] != "main"
        or branch["enable_auto_build"]
        or app["after"]["enable_branch_auto_build"]
    ):
        raise ValueError("STOP: wrong app/repository/branch or automatic builds enabled")
    environment = branch.get("environment_variables", {})
    if (
        environment.get("VITE_AUTH_MODE") != "cognito"
        or environment.get("VITE_GOVERNANCE_API_MODE") != "baseline-v1"
        or environment.get("VITE_APP_ORIGIN") != "https://main." + app["before"]["default_domain"]
    ):
        raise ValueError("STOP: Stage C requires Cognito, its own origin and V1 compatibility mode")
    print("Stage C verified: 1 create, 2 in-place updates, 0 destroys; original app ID retained.")
    return changes


if __name__ == "__main__":
    check(sys.argv[1])
