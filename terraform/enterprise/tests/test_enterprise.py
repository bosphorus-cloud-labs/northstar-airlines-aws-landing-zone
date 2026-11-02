#!/usr/bin/env python3
import json
import pathlib
import re
import subprocess
import tempfile
import unittest

from render_aft_templates import render_directory

ROOT = pathlib.Path(__file__).resolve().parents[1]


class EnterpriseReferenceTests(unittest.TestCase):
    def test_aft_templates_render_with_supported_role_variables(self):
        repositories = {
            "account-requests/terraform": "aft_admin_role_arn",
            "global-customizations/terraform": "target_admin_role_arn",
            "account-customizations/production/terraform": "target_admin_role_arn",
            "account-customizations/development/terraform": "target_admin_role_arn",
        }
        with tempfile.TemporaryDirectory() as directory:
            output_root = pathlib.Path(directory)
            for relative, expected_role_variable in repositories.items():
                source = ROOT / relative
                provider_template = (source / "aft-providers.jinja").read_text()
                self.assertIn(f"{{{{ {expected_role_variable} }}}}", provider_template)
                output = output_root / relative.replace("/", "-")
                render_directory(source, output)
                rendered = "\n".join(path.read_text() for path in output.glob("*.tf"))
                self.assertNotIn("{{", rendered)
                self.assertNotIn("{%", rendered)
                subprocess.run(
                    ["terraform", "fmt", "-check", str(output)],
                    check=True,
                    capture_output=True,
                    text=True,
                )

    def test_policy_json_is_valid(self):
        for policy in (ROOT / "organizations" / "policies").glob("*.json"):
            document = json.loads(policy.read_text())
            self.assertEqual(document["Version"], "2012-10-17")
            self.assertTrue(document["Statement"])

    def test_scp_region_and_repair_semantics(self):
        common = json.loads((ROOT / "organizations/policies/common-regions.json").read_text())
        statement = common["Statement"][0]
        self.assertNotIn("kms:*", statement["NotAction"])
        self.assertNotIn("config:*", statement["NotAction"])
        repair_arns = statement["Condition"]["ArnNotLike"]["aws:PrincipalArn"]
        self.assertIn("arn:aws:iam::*:role/AWSControlTowerExecution", repair_arns)
        self.assertIn("arn:aws:iam::*:role/NorthStarEmergencyRepair", repair_arns)

        production = json.loads((ROOT / "organizations/policies/production-protection.json").read_text())
        security_deny = next(item for item in production["Statement"] if item["Sid"] == "DenyDisablingSecurityServices")
        self.assertEqual(security_deny["Effect"], "Deny")
        self.assertIn("ArnNotLike", security_deny["Condition"])

    def test_environment_policy_targets_are_separate(self):
        source = (ROOT / "organizations" / "main.tf").read_text()
        self.assertRegex(source, r'production\s*=.*target\s*= var\.production_ou_id')
        self.assertRegex(source, r'development\s*=.*target\s*= var\.development_ou_id')
        self.assertIn('common_production', source)
        self.assertIn('common_development', source)

    def test_aft_bootstrap_starts_in_control_tower_management(self):
        provider = (ROOT / "aft-bootstrap/providers.tf").read_text()
        self.assertIn("allowed_account_ids = [var.control_tower_management_account_id]", provider)
        self.assertNotIn("assume_role", provider)
        module = (ROOT / "aft-bootstrap/main.tf").read_text()
        for required_input in (
            "aft_management_account_id",
            "audit_account_id",
            "ct_management_account_id",
            "log_archive_account_id",
            "account_request_repo_name",
            "account_provisioning_customizations_repo_name",
            "global_customizations_repo_name",
            "account_customizations_repo_name",
        ):
            self.assertIn(required_input, module)

    def test_network_attachment_lifecycle_and_safe_routes(self):
        core = (ROOT / "networking/core/main.tf").read_text()
        workload = (ROOT / "networking/workload-attachment/main.tf").read_text()
        self.assertIn('aws_ec2_transit_gateway_vpc_attachment_accepter" "workload', core)
        self.assertIn("depends_on                     = [aws_ec2_transit_gateway_vpc_attachment_accepter.workload]", core)
        self.assertIn('toset(["production", "development", "inspection"])', core)
        self.assertNotIn('destination_cidr_block = "0.0.0.0/0"', core)
        self.assertNotIn('destination_cidr_block = "0.0.0.0/0"', workload)
        self.assertIn('resource "aws_route" "approved_transit_gateway"', workload)

    def test_gwlb_permissions_are_supported_and_scoped(self):
        main = (ROOT / "networking/core/main.tf").read_text()
        variables = (ROOT / "networking/core/variables.tf").read_text()
        self.assertIn("allowed_principals         = var.endpoint_service_allowed_principal_arns", main)
        self.assertIn("acceptance_required        = true", main)
        self.assertIn("arn:aws:iam::", variables)
        self.assertNotIn("arn:aws:organizations::", variables)

    def test_ci_handoff_binds_plan_run_commit_and_digest(self):
        plan = (ROOT / "ci/templates/scoped-plan.yml.example").read_text()
        handoff = (ROOT / "ci/templates/reviewed-apply.yml.example").read_text()
        validation = (ROOT / "ci/templates/pull-request-validation.yml.example").read_text()
        self.assertNotIn("id-token: write", validation)
        self.assertIn("terraform -chdir=\"$TF_ROOT\" init", plan)
        self.assertIn("plan_sha256", plan)
        self.assertIn("lock_sha256", plan)
        self.assertIn("plan_run_id", handoff)
        self.assertIn("run-id: ${{ inputs.plan_run_id }}", handoff)
        self.assertIn("artifact_sha256", handoff)
        self.assertNotIn("terraform apply", plan)
        self.assertNotIn("terraform apply", handoff)

    def test_customization_ownership_is_disjoint(self):
        global_source = (ROOT / "global-customizations" / "terraform" / "main.tf").read_text()
        account_sources = "\n".join(
            (ROOT / "account-customizations" / name / "terraform" / "main.tf").read_text()
            for name in ("production", "development")
        )
        self.assertIn("aws_iam_account_password_policy", global_source)
        self.assertIn("aws_s3_account_public_access_block", global_source)
        self.assertNotIn("aws_budgets_budget", global_source)
        self.assertIn("aws_budgets_budget", account_sources)
        self.assertNotIn("aws_iam_account_password_policy", account_sources)
        self.assertNotIn("aws_s3_account_public_access_block", account_sources)

    def test_poc_state_is_not_referenced(self):
        forbidden = ("terraform/poc", "../poc", "terraform_remote_state")
        for path in ROOT.rglob("*"):
            if path.is_file() and path.suffix in {".tf", ".md", ".example"}:
                text = path.read_text()
                for marker in forbidden:
                    self.assertNotIn(marker, text, f"{marker} in {path}")

    def test_production_and_development_are_materially_different(self):
        production = (ROOT / "account-customizations" / "production" / "terraform" / "main.tf").read_text()
        development = (ROOT / "account-customizations" / "development" / "terraform" / "main.tf").read_text()
        self.assertIn('limit_amount = "25000"', production)
        self.assertIn('notification_type          = "FORECASTED"', production)
        self.assertIn('limit_amount = "5000"', development)
        self.assertIn('notification_type          = "ACTUAL"', development)

    def test_no_account_ids_outside_examples(self):
        for path in ROOT.rglob("*"):
            if (
                path.is_file()
                and ".terraform" not in path.parts
                and path.name != "terraform.tfvars.example"
                and path.name != "render_aft_templates.py"
                and path.suffix in {".tf", ".md", ".example", ".json", ".py"}
            ):
                text = path.read_text(errors="ignore")
                self.assertFalse(re.search(r'(?<![0-9])[0-9]{12}(?![0-9])', text), path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
