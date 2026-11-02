variable "region" {
  type    = string
  default = "eu-central-1"
}
variable "workload_account_id" { type = string }
variable "workload_execution_role_arn" { type = string }
variable "environment" {
  type = string
  validation {
    condition     = contains(["production", "development"], var.environment)
    error_message = "Use production or development."
  }
}
variable "vpc_id" { type = string }
variable "transit_gateway_id" { type = string }
variable "transit_gateway_subnet_ids" { type = list(string) }
variable "approved_routes" {
  type = map(object({
    destination_cidr = string
    route_table_id   = string
  }))
  default     = {}
  description = "Explicit workload routes approved for the TGW; no default route is created implicitly."
}
