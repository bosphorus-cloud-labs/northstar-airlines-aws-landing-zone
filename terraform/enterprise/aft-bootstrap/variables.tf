variable "aft_management_account_id" {
  type        = string
  description = "Dedicated account where AFT orchestration resources are deployed."
  validation {
    condition     = can(regex("^[0-9]{12}$", var.aft_management_account_id))
    error_message = "Use a 12-digit AWS account ID."
  }
}

variable "control_tower_management_account_id" {
  type        = string
  description = "Existing Organizations management account that owns Control Tower."
  validation {
    condition     = can(regex("^[0-9]{12}$", var.control_tower_management_account_id))
    error_message = "Use a 12-digit AWS account ID."
  }
}

variable "audit_account_id" {
  type = string
  validation {
    condition     = can(regex("^[0-9]{12}$", var.audit_account_id))
    error_message = "Use a 12-digit AWS account ID."
  }
}

variable "log_archive_account_id" {
  type = string
  validation {
    condition     = can(regex("^[0-9]{12}$", var.log_archive_account_id))
    error_message = "Use a 12-digit AWS account ID."
  }
}

variable "aft_home_region" { type = string }
variable "backend_secondary_region" { type = string }
variable "aft_pipeline_terraform_version" {
  type    = string
  default = "1.14.6"
}
variable "vcs_provider" {
  type    = string
  default = "github"
  validation {
    condition     = contains(["codecommit", "bitbucket", "github", "githubenterprise", "gitlab", "gitlabselfmanaged", "azuredevops"], var.vcs_provider)
    error_message = "Choose a VCS provider supported by AFT 1.23.0."
  }
}
variable "repository_branch" {
  type    = string
  default = "main"
}
variable "account_request_repo_name" { type = string }
variable "account_provisioning_customizations_repo_name" { type = string }
variable "global_customizations_repo_name" { type = string }
variable "account_customizations_repo_name" { type = string }
variable "tags" {
  type    = map(string)
  default = { Project = "NorthStar" }
}
