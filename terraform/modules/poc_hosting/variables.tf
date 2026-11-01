variable "name" { type = string }
variable "tags" { type = map(string) }

variable "github_repository_url" {
  type        = string
  default     = null
  description = "GitHub repository for the existing app; null is the pre-integration default. Keep configured once connected."
}
variable "github_access_token" {
  type        = string
  default     = null
  sensitive   = true
  description = "One-time repository setup token supplied securely, never in source. Sensitive but NOT write-only in AWS provider 6.71; protect state and plans."
}
variable "github_build_spec" {
  type        = string
  default     = null
  description = "Repository build specification for the existing app; null preserves its computed current build spec."
}
