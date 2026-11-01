"""Compare verbose mock Terraform test plans, never real state or AWS."""

import copy
import json
import sys
from pathlib import Path


def check(path):
    plans = {
        item["@testrun"]: item["test_plan"]
        for line in Path(path).read_text().splitlines()
        if (item := json.loads(line)).get("type") == "test_plan"
    }
    names = ("original_origin_unchanged", "second_origin_consistent")
    resources = [
        {item["address"]: item["change"] for item in plans[name]["resource_changes"]}
        for name in names
    ]
    if resources[0].keys() != resources[1].keys():
        raise ValueError("Origin change must not add or remove resource addresses")
    changed = set()
    for address in resources[0]:
        left, right = [copy.deepcopy(items[address]) for items in resources]
        if left != right:
            changed.add(address)
        for change in (left, right):
            for key in ("after", "after_unknown", "after_sensitive"):
                values = change.get(key, {})
                if address == "module.identity.aws_cognito_user_pool_client.spa":
                    values.pop("callback_urls", None)
                    values.pop("logout_urls", None)
                elif address == "module.http.aws_apigatewayv2_api.governance":
                    for cors in values.get("cors_configuration", []):
                        cors.pop("allow_origins", None)
        if left != right:
            raise ValueError(f"Unexpected non-origin configuration difference: {address}")
    if changed != {
        "module.identity.aws_cognito_user_pool_client.spa",
        "module.http.aws_apigatewayv2_api.governance",
    }:
        raise ValueError("Expected only Cognito client URLs and HTTP API CORS to differ")
    print("Mock plan comparison passed: only Cognito callback/logout and API CORS differ.")
    print("No live state inspected; a real AWS plan still requires separate authorization.")


if __name__ == "__main__":
    check(sys.argv[1])
