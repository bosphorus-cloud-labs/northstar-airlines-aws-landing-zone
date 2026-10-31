variable "name" { type = string }
variable "tags" { type = map(string) }

variable "reserved_concurrency" { type = number }
variable "table_arn" { type = string }
variable "table_name" { type = string }
variable "snapshot_id" { type = string }
variable "api_id" { type = string }
variable "issuer" { type = string }
variable "client_id" { type = string }
variable "package_path" { type = string }
variable "log_retention_days" { type = number }
variable "permissions_boundary_arn" {
  type    = string
  default = null
}
