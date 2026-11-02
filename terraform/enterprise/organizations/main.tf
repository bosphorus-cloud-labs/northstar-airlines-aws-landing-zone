locals {
  policies = {
    common_regions = { name = "northstar-common-regions-v1", file = "common-regions.json" }
    production     = { name = "northstar-production-protection-v1", file = "production-protection.json" }
    development    = { name = "northstar-development-guardrails-v1", file = "development-guardrails.json" }
  }
  attachments = {
    common_production  = { policy = "common_regions", target = var.production_ou_id }
    common_development = { policy = "common_regions", target = var.development_ou_id }
    production         = { policy = "production", target = var.production_ou_id }
    development        = { policy = "development", target = var.development_ou_id }
  }
}
resource "aws_organizations_policy" "customer_managed" {
  for_each    = local.policies
  name        = each.value.name
  description = "NorthStar customer-managed SCP; does not grant IAM permissions or replace Control Tower controls."
  type        = "SERVICE_CONTROL_POLICY"
  content     = file("${path.module}/policies/${each.value.file}")
  tags        = { ManagedBy = "Terraform", PolicyOwner = "CentralGovernance", PolicyVersion = "v1" }
  lifecycle { prevent_destroy = true }
}

resource "aws_organizations_policy_attachment" "ou" {
  for_each  = local.attachments
  policy_id = aws_organizations_policy.customer_managed[each.value.policy].id
  target_id = each.value.target
  lifecycle { prevent_destroy = true }
}
