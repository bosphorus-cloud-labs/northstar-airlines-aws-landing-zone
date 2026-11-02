variable "account-request-table" {
  type        = string
  description = "Name of the AFT account request table."
  default     = "aft-request"
}

variable "account-request-table-hash" {
  type        = string
  description = "Name of the AFT account request table hash key."
  default     = "id"
}

variable "control_tower_parameters" {
  type = object({
    AccountEmail              = string
    AccountName               = string
    ManagedOrganizationalUnit = string
    SSOUserEmail              = string
    SSOUserFirstName          = string
    SSOUserLastName           = string
  })
}

variable "change_management_parameters" {
  type = object({
    change_requested_by = string
    change_reason       = string
  })
}

variable "account_tags" {
  type    = map(any)
  default = {}
}

variable "custom_fields" {
  type    = map(any)
  default = {}
}

variable "account_customizations_name" {
  type        = string
  default     = ""
  description = "Name of the account customization template to apply."
}
