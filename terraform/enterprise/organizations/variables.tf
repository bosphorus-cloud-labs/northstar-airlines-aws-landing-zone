variable "home_region" {
  type    = string
  default = "eu-central-1"
}
variable "organizations_management_account_id" { type = string }
variable "organizations_execution_role_arn" { type = string }
variable "production_ou_id" {
  type = string
  validation {
    condition     = can(regex("^ou-[a-z0-9]{4,32}-[a-z0-9]{8,32}$", var.production_ou_id))
    error_message = "Use an Organizations OU ID."
  }
}
variable "development_ou_id" {
  type = string
  validation {
    condition     = can(regex("^ou-[a-z0-9]{4,32}-[a-z0-9]{8,32}$", var.development_ou_id))
    error_message = "Use an Organizations OU ID."
  }
}

check "separate_environment_ous" {
  assert {
    condition     = var.production_ou_id != var.development_ou_id
    error_message = "Production and Development must target distinct OUs."
  }
}
