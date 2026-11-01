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

variable "additional_origins" {
  type        = list(string)
  default     = []
  nullable    = false
  description = "Explicit additional HTTPS DNS origins; no paths, trailing slash, ports, wildcards, credentials, query or fragment."
  validation {
    condition = alltrue([for origin in var.additional_origins : origin == null ? false : (
      length(origin) <= 261 && can(regex("^https://([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\\.)+[a-z]([a-z0-9-]{0,61}[a-z0-9])?$", origin))
    )])
    error_message = "Additional origins must be lowercase HTTPS DNS origins only, for example https://main.example.amplifyapp.com (no trailing slash or port)."
  }
}

variable "enable_github_hosting" {
  type        = bool
  default     = false
  nullable    = false
  description = "Connect the existing Terraform-managed app to GitHub in place and create its main branch. Keep true once connected."
}
variable "github_access_token" {
  type        = string
  default     = null
  sensitive   = true
  description = "GitHub App setup token for the reviewed in-place repository connection. Never commit; sensitive but not write-only, so protect state/plans."
  validation {
    condition     = var.github_access_token == null || var.enable_github_hosting
    error_message = "A GitHub setup token requires enable_github_hosting=true. Set it explicitly in your ignored settings.auto.tfvars; a token alone does not enable repository integration."
  }
}
variable "github_auto_build_enabled" {
  type        = bool
  default     = false
  nullable    = false
  description = "Keep false during provisioning. Enable only after reviewed backend/frontend compatibility and Cognito/CORS readiness."
  validation {
    condition     = !var.github_auto_build_enabled || var.enable_github_hosting
    error_message = "Automatic main-branch builds require enable_github_hosting."
  }
}

variable "hosting_migration_stage" {
  type        = string
  default     = "legacy"
  nullable    = false
  description = "Ordered migration checkpoints: legacy -> retire_manual -> connect_repository -> create_main. Apply and verify each checkpoint separately."
  validation {
    condition     = contains(["legacy", "retire_manual", "connect_repository", "create_main"], var.hosting_migration_stage)
    error_message = "Choose legacy, retire_manual, connect_repository, or create_main."
  }
  validation {
    condition     = var.hosting_migration_stage == "legacy" || var.enable_github_hosting
    error_message = "Migration stages require enable_github_hosting=true."
  }
  validation {
    condition     = !var.github_auto_build_enabled || var.hosting_migration_stage == "create_main"
    error_message = "Automatic main builds can only be enabled after create_main acceptance."
  }
}

variable "github_baseline_compatibility" {
  type        = bool
  default     = true
  nullable    = false
  description = "Explicit main-branch frontend baseline mode for the existing V1 Lambda. Set false only after the separate backend upgrade is verified."
}
