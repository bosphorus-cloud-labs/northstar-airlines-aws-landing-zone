locals {
  account_ids = toset([
    var.aft_management_account_id,
    var.audit_account_id,
    var.control_tower_management_account_id,
    var.log_archive_account_id,
  ])
  tags = merge(var.tags, {
    ManagedBy = "Terraform"
    Scope     = "enterprise-aft"
  })
}
check "distinct_account_boundaries" {
  assert {
    condition     = length(local.account_ids) == 4
    error_message = "AFT Management, Control Tower Management, Audit, and Log Archive must be distinct accounts."
  }
}

check "secondary_backend_region" {
  assert {
    condition     = var.backend_secondary_region != var.aft_home_region
    error_message = "The replicated backend region must differ from the AFT home region."
  }
}

module "account_factory_for_terraform" {
  source  = "aws-ia/control_tower_account_factory/aws"
  version = "1.23.0"

  aft_management_account_id   = var.aft_management_account_id
  audit_account_id            = var.audit_account_id
  ct_management_account_id    = var.control_tower_management_account_id
  log_archive_account_id      = var.log_archive_account_id
  ct_home_region              = var.aft_home_region
  tf_backend_secondary_region = var.backend_secondary_region

  terraform_distribution = "oss"
  terraform_version      = var.aft_pipeline_terraform_version
  vcs_provider           = var.vcs_provider

  account_request_repo_name                       = var.account_request_repo_name
  account_request_repo_branch                     = var.repository_branch
  account_provisioning_customizations_repo_name   = var.account_provisioning_customizations_repo_name
  account_provisioning_customizations_repo_branch = var.repository_branch
  global_customizations_repo_name                 = var.global_customizations_repo_name
  global_customizations_repo_branch               = var.repository_branch
  account_customizations_repo_name                = var.account_customizations_repo_name
  account_customizations_repo_branch              = var.repository_branch

  aft_enable_vpc                          = true
  aft_feature_cloudtrail_data_events      = true
  aft_feature_delete_default_vpcs_enabled = false
  aft_feature_enterprise_support          = false
  cloudwatch_log_group_retention          = 90
  maximum_concurrent_customizations       = 5
  aft_customization_triggers              = ["account_move"]
  tags                                    = local.tags
}
