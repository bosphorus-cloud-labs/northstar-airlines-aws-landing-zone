variable "aws_account_id" {
  type        = string
  description = "Explicit authorized deployment account; never discovered by this configuration."
  validation {
    condition     = can(regex("^[0-9]{12}$", var.aws_account_id))
    error_message = "Supply the authorized account ID only when deployment is approved."
  }
}
variable "name" {
  type    = string
  default = "northstar-governance-poc"
  validation {
    condition     = can(regex("^northstar-[a-z0-9-]{3,32}$", var.name))
    error_message = "Use a short northstar-prefixed resource name."
  }
}
variable "owner" {
  type    = string
  default = "northstar-platform-demo"
}
variable "cognito_domain_prefix" {
  type        = string
  description = "Globally available Cognito prefix chosen by the operator; availability not checked offline."
  validation {
    condition     = can(regex("^[a-z0-9-]{3,50}$", var.cognito_domain_prefix))
    error_message = "Use a 3-50 character lowercase Cognito domain prefix."
  }
}
variable "lambda_package_path" {
  type    = string
  default = "../../artifacts/lambda/function.zip"
}
variable "log_retention_days" {
  type    = number
  default = 14
  validation {
    condition     = contains([7, 14, 30, 60, 90], var.log_retention_days)
    error_message = "Choose a supported bounded log retention."
  }
}
variable "permissions_boundary_arn" {
  type        = string
  default     = null
  description = "Optional pre-existing permissions boundary for the Lambda role, supplied after authorization."
}

variable "lambda_reserved_concurrency" {
  type        = number
  default     = 2
  description = "Regional quota must permit this reservation; -1 explicitly opts out after review."
  validation {
    condition     = contains([-1, 1, 2, 3, 4, 5], var.lambda_reserved_concurrency)
    error_message = "Use -1 or a small reserved concurrency limit."
  }
}
