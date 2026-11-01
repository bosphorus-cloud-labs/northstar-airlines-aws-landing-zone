module "delivery" {
  count                      = var.enable_governance_delivery ? 1 : 0
  source                     = "../modules/governance_delivery"
  name                       = var.name
  tags                       = local.tags
  table_arn                  = module.data.table_arn
  baseline_id                = local.snapshot_id
  existing_oidc_provider_arn = var.github_oidc_provider_arn
}
output "governance_publisher_role_arn" {
  value = var.enable_governance_delivery ? module.delivery[0].publisher_role_arn : null
}
output "governance_baseline_id" { value = local.snapshot_id }
