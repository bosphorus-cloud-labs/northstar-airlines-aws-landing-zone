# Update the existing app in place. Its stable hostname feeds identity/CORS,
# then main-branch settings. Never feed branch environment back into the app.
locals {
  repository_connection_enabled = var.enable_github_hosting && contains(["connect_repository", "create_main"], var.hosting_migration_stage)
  main_branch_enabled           = var.enable_github_hosting && var.hosting_migration_stage == "create_main"
  github_origin                 = local.main_branch_enabled ? "https://main.${module.hosting.default_domain}" : null
  approved_additional_origins = distinct(concat(
    var.additional_origins,
    local.main_branch_enabled ? [local.github_origin] : []
  ))
  github_frontend_settings = local.main_branch_enabled ? merge(local.frontend_settings, {
    VITE_APP_ORIGIN          = local.github_origin
    VITE_GOVERNANCE_API_MODE = var.github_baseline_compatibility ? "baseline-v1" : "catalog"
  }) : null
}
resource "aws_amplify_branch" "github_main" {
  count                       = local.main_branch_enabled ? 1 : 0
  app_id                      = module.hosting.app_id
  branch_name                 = "main"
  framework                   = "React"
  stage                       = "DEVELOPMENT"
  enable_auto_build           = var.github_auto_build_enabled
  enable_pull_request_preview = false
  environment_variables       = merge(local.github_frontend_settings, { AMPLIFY_MONOREPO_APP_ROOT = "frontend" })
  tags                        = local.tags
  depends_on                  = [module.identity, module.http]
}
output "github_app_id" { value = var.enable_github_hosting ? module.hosting.app_id : null }
output "github_app_origin" { value = local.github_origin }
output "github_frontend_settings" {
  description = "Six public connection settings plus explicit API compatibility mode for main; no credentials."
  value       = local.github_frontend_settings
}
