variable "name" { type = string }
variable "tags" { type = map(string) }

variable "callback_url" { type = string }
variable "logout_url" { type = string }
variable "domain_prefix" { type = string }
