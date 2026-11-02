provider "aws" {
  region              = var.aft_home_region
  allowed_account_ids = [var.control_tower_management_account_id]

  default_tags {
    tags = local.tags
  }
}
