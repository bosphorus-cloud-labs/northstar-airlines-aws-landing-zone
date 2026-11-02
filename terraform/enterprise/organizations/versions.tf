terraform {
  required_version = ">= 1.14.0, < 2.0.0"
  required_providers { aws = { source = "hashicorp/aws", version = "~> 6.71.0" } }
  backend "s3" {}
}

provider "aws" {
  region              = var.home_region
  allowed_account_ids = [var.organizations_management_account_id]
  assume_role {
    role_arn     = var.organizations_execution_role_arn
    session_name = "northstar-scp-governance"
  }
}
