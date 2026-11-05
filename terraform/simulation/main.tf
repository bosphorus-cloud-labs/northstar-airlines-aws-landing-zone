# ISOLATED OFFLINE DEMO. Never imports terraform/poc or any AWS provider/module.
terraform {
  required_version = ">= 1.14.0, < 2.0.0"
}
variable "run_directory" {
  type        = string
  default     = "../../artifacts/policy-rollout/demo"
  description = "Existing CLI run directory, absolute or relative to this root. Read-only input."
}
variable "policy_version" {
  type    = string
  default = "2.0.0"
  validation {
    condition     = contains(["1.0.0", "2.0.0"], var.policy_version)
    error_message = "Choose the frozen V1 baseline or proposed V2 policy."
  }
}
locals {
  state             = jsondecode(file("${abspath(var.run_directory)}/state.json")).payload
  proposal          = local.state.proposal
  accounts          = { for account in(var.resource_accounts_json == "null" ? local.proposal.baseline.fleet.accounts : jsondecode(var.resource_accounts_json)) : account.id => account }
  resource_controls = var.resource_controls_json == "null" ? [] : jsondecode(var.resource_controls_json)
  policy            = var.policy_version == "1.0.0" ? local.proposal.baseline.policy : local.proposal.policy
  environments = { for env in(
    var.policy_version == "1.0.0" ? local.proposal.baseline.environments : local.proposal.environments
  ) : env.id => env }
  ous = { for ou in local.proposal.baseline.fleet.ous : ou.id => ou }
}
module "account_governance" {
  source            = "../modules/simulated_governance"
  for_each          = local.accounts
  account           = each.value
  policy            = local.policy
  environment       = local.environments[each.value.environment]
  resource_controls = { for rule in local.resource_controls : rule.id => { expected_json = rule.expected_json, max_age_hours = rule.max_age_hours[each.value.environment] } }
}
output "governance_desired" {
  description = "SIMULATED desired assignments only. Planning deploys no controls and measures no compliance."
  value = {
    source          = "northstar-terraform-desired-v1"
    simulated       = true
    proposal_digest = local.state.proposal_digest
    policy_version  = var.policy_version
    accounts        = { for id, account in module.account_governance : id => account.desired }
  }
  precondition {
    condition = (
      local.state.simulated == true && local.state.source == "northstar-policy-rollout-v1" &&
      (var.resource_accounts_json == "null" ? length(local.accounts) == 10 : length(local.accounts) >= 1 && length(local.accounts) <= 25) &&
      toset(keys(local.environments)) == toset(["production", "pre-production", "testing", "development"]) &&
      alltrue([for account in local.accounts : local.ous[account.ou_id].environment == account.environment])
    )
    error_message = "Use a valid ten-account synthetic CLI proposal with matching OU/environment assignments."
  }
}

variable "resource_controls_json" {
  type        = string
  default     = "null"
  description = "Validated synthetic resource controls; supplied by the offline release builder."
}
variable "resource_accounts_json" {
  type        = string
  default     = "null"
  description = "Validated synthetic account assignments; absent preserves the original simulation."
}
variable "resource_source_digest" {
  type    = string
  default = ""
}
output "resource_governance_desired" {
  value = var.resource_controls_json == "null" ? null : {
    source       = "northstar-terraform-resource-desired-v1"
    simulated    = true
    input_digest = var.resource_source_digest
    accounts     = { for id, account in module.account_governance : id => account.resource_desired }
  }
}
