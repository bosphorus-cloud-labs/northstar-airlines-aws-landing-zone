variable "region" {
  type    = string
  default = "eu-central-1"
}
variable "network_account_id" { type = string }
variable "network_execution_role_arn" { type = string }
variable "organization_arn" { type = string }
variable "amazon_side_asn" {
  type    = number
  default = 64520
}
variable "inspection_vpc_id" { type = string }
variable "inspection_transit_gateway_subnet_ids" {
  type = list(string)
  validation {
    condition     = length(var.inspection_transit_gateway_subnet_ids) >= 2
    error_message = "Use dedicated TGW subnets in at least two Availability Zones."
  }
}
variable "inspection_gwlb_subnet_ids" {
  type = list(string)
  validation {
    condition     = length(var.inspection_gwlb_subnet_ids) >= 2
    error_message = "Use GWLB subnets in at least two Availability Zones."
  }
}
variable "customer_gateway_ip" {
  type      = string
  sensitive = true
}
variable "customer_gateway_bgp_asn" { type = number }
variable "appliance_health_check_port" {
  type    = string
  default = "22"
}
variable "workload_attachments" {
  type = map(object({
    attachment_id = string
    environment   = string
    vpc_cidr      = string
  }))
  default     = {}
  description = "Accepted cross-account attachments and routes promoted into the central network state."
  validation {
    condition     = alltrue([for attachment in values(var.workload_attachments) : contains(["production", "development"], attachment.environment)])
    error_message = "Every workload attachment must target production or development."
  }
}
variable "inspection_routes" {
  type = map(object({
    destination_cidr = string
    environment      = string
  }))
  default     = {}
  description = "Explicit TGW prefixes routed to inspection only after the complete symmetric inspection path is approved."
  validation {
    condition     = alltrue([for route in values(var.inspection_routes) : contains(["production", "development"], route.environment)])
    error_message = "Every inspection route must target production or development."
  }
}
variable "inspection_return_routes" {
  type = map(object({
    attachment_key = string
    vpc_cidr       = string
  }))
  default     = {}
  description = "Explicit inspection-table return routes enabled only with an approved symmetric path."
}

check "inspection_return_attachments_exist" {
  assert {
    condition     = alltrue([for route in values(var.inspection_return_routes) : contains(keys(var.workload_attachments), route.attachment_key)])
    error_message = "Every inspection return route must reference a configured workload attachment key."
  }
}
variable "direct_hybrid_route_environments" {
  type        = set(string)
  default     = []
  description = "Environment route tables that may receive direct, explicitly uninspected VPN propagation."
  validation {
    condition     = alltrue([for environment in var.direct_hybrid_route_environments : contains(["production", "development"], environment)])
    error_message = "Direct hybrid propagation supports only production or development."
  }
}
variable "endpoint_service_allowed_principal_arns" {
  type        = set(string)
  default     = []
  description = "Explicit AWS account-root, role, or user ARNs permitted to request GWLB endpoints."
  validation {
    condition = alltrue([
      for arn in var.endpoint_service_allowed_principal_arns :
      can(regex("^arn:aws:iam::[0-9]{12}:(root|role/[A-Za-z0-9+=,.@_/-]+|user/[A-Za-z0-9+=,.@_/-]+)$", arn))
    ])
    error_message = "Use supported IAM account-root, role, or user principal ARNs; Organizations ARNs are not supported."
  }
}
