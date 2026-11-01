"""The bootstrap plan may extend data-read access, never replace existing infrastructure."""

import copy
import json
import unittest

from scripts.inspect_delivery_plan import EXPECTED, check


def plan():
    changes = {
        key: {"actions": value, "before": {}, "after": {}} for key, value in EXPECTED.items()
    }
    function = {
        "function_name": "northstar-offline",
        "role": "existing-role",
        "environment": [{"variables": {"SNAPSHOT_ID": "a" * 64}}],
    }
    changes["module.compute.aws_lambda_function.api"].update(
        before=copy.deepcopy(function), after=copy.deepcopy(function)
    )
    changes["module.compute.aws_lambda_function.api"]["before"]["source_code_hash"] = "old"
    changes["module.compute.aws_lambda_function.api"]["after"]["source_code_hash"] = "new"
    changes["module.compute.aws_iam_role_policy.runtime"]["before"] = {
        "policy": json.dumps(
            {"Statement": [{"Action": ["dynamodb:Query"], "Resource": "single-table"}]}
        )
    }
    changes["module.compute.aws_iam_role_policy.runtime"]["after"] = {
        "policy": json.dumps(
            {
                "Statement": [
                    {"Action": ["dynamodb:Query", "dynamodb:GetItem"], "Resource": "single-table"}
                ]
            }
        )
    }
    changes["module.delivery[0].aws_iam_role_policy.publisher"]["after"] = {
        "policy": json.dumps(
            {
                "Statement": [
                    {
                        "Action": ["dynamodb:Query", "dynamodb:GetItem", "dynamodb:PutItem"],
                        "Resource": "single-table",
                    }
                ]
            }
        )
    }
    return {
        "resource_changes": [{"address": key, "change": value} for key, value in changes.items()]
    }


class DeliveryPlanTests(unittest.TestCase):
    def test_approved_initial_scope(self):
        self.assertEqual(check(plan()), EXPECTED)

    def test_replacements_and_reader_writes_rejected(self):
        value = plan()
        value["resource_changes"][0]["change"]["actions"] = ["delete", "create"]
        with self.assertRaises(ValueError):
            check(value)
        value = plan()
        next(
            r
            for r in value["resource_changes"]
            if r["address"] == "module.compute.aws_iam_role_policy.runtime"
        )["change"]["after"]["policy"] = json.dumps(
            {"Statement": [{"Action": ["dynamodb:PutItem"]}]}
        )
        with self.assertRaises(ValueError):
            check(value)

    def test_premature_reader_activation_rejected(self):
        value = plan()
        next(
            r
            for r in value["resource_changes"]
            if r["address"] == "module.compute.aws_lambda_function.api"
        )["change"]["after"]["environment"] = [
            {"variables": {"GOVERNANCE_CATALOG_MODE": "dynamodb"}}
        ]
        with self.assertRaises(ValueError):
            check(value)
