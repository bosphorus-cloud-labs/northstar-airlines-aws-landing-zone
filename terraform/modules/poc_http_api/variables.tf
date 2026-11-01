variable "name" { type = string }
variable "tags" { type = map(string) }

variable "issuer" { type = string }
variable "client_id" { type = string }
variable "allowed_origin" { type = string }
variable "log_retention_days" { type = number }

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
