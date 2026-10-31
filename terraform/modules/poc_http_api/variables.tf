variable "name" { type = string }
variable "tags" { type = map(string) }

variable "issuer" { type = string }
variable "client_id" { type = string }
variable "allowed_origin" { type = string }
variable "log_retention_days" { type = number }
