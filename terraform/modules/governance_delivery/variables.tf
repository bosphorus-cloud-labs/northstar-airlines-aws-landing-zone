variable "name" { type = string }
variable "tags" { type = map(string) }
variable "table_arn" { type = string }
variable "baseline_id" { type = string }
variable "existing_oidc_provider_arn" {
  type    = string
  default = null
}
