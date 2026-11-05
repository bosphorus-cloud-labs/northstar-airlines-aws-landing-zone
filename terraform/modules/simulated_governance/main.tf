# Pure desired-configuration calculation. No providers, resources or data sources.
terraform {
  required_version = ">= 1.14.0, < 2.0.0"
}
variable "account" {
  type = object({ id = string, environment = string, ou_id = string, lifecycle_status = string })
  validation {
    condition     = can(regex("^sim-account-[0-9]{3}$", var.account.id))
    error_message = "Only synthetic account identifiers are permitted."
  }
}
variable "policy" {
  type = object({
    id                    = string, version = string
    baseline_requirements = map(bool)
    controls              = list(object({ id = string, category = string, description = string }))
  })
}
variable "environment" {
  type = object({
    id           = string, policy_id = string, policy_version = string
    requirements = list(object({ control_id = string, expected = bool, max_age_hours = number }))
  })
}
locals {
  requirements = { for requirement in var.environment.requirements : requirement.control_id => {
    expected      = requirement.expected
    max_age_hours = requirement.max_age_hours
    category      = one([for control in var.policy.controls : control.category if control.id == requirement.control_id])
  } }
}
output "desired" {
  value = {
    account_id             = var.account.id
    environment            = var.account.environment
    ou_id                  = var.account.ou_id
    lifecycle_status       = var.account.lifecycle_status
    policy_id              = var.policy.id
    desired_policy_version = var.policy.version
    baseline_requirements  = var.policy.baseline_requirements
    requirements           = local.requirements
  }
  precondition {
    condition = (
      var.environment.id == var.account.environment &&
      var.environment.policy_id == var.policy.id &&
      var.environment.policy_version == var.policy.version &&
      toset(keys(local.requirements)) == toset([for control in var.policy.controls : control.id]) &&
      alltrue([for id, expected in var.policy.baseline_requirements : try(local.requirements[id].expected == expected, false)])
    )
    error_message = "Environment assignment must cover all controls and preserve the central baseline."
  }
}

# Optional resource controls reuse this same pure module; no additional provider/project.
variable "resource_controls" {
  type    = map(object({ expected_json = string, max_age_hours = number }))
  default = {}
}
output "resource_desired" {
  value = {
    account_id        = var.account.id
    environment       = var.account.environment
    approval_required = local.requirements["deployment-approval"].expected
    requirements      = var.resource_controls
  }
  precondition {
    condition     = alltrue([for requirement in values(var.resource_controls) : can(jsondecode(requirement.expected_json)) && requirement.max_age_hours >= 1 && requirement.max_age_hours <= 168])
    error_message = "Resource requirements must be explicit JSON values with bounded freshness."
  }
}
