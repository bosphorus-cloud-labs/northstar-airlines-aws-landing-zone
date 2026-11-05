aws_account_id        = "REPLACE_WITH_AUTHORIZED_ACCOUNT_ID"
cognito_domain_prefix = "REPLACE_WITH_AVAILABLE_PREFIX"
owner                 = "northstar-platform-demo"
# This deliberately cannot be planned as-is; no real account IDs are stored here.

# Defaults preserve manual hosting. For the approved existing-app GitHub integration,
# set enable_github_hosting=true in your ignored settings.auto.tfvars.
enable_github_hosting     = false
github_auto_build_enabled = false
# Never put github_access_token in a tfvars file; use an approved secret input.

# Advance only after the prior migration checkpoint has been applied and verified.
hosting_migration_stage = "legacy"

# Activate only after compatible Lambda, protected resource publication and acceptance.
governance_frontend_mode = "catalog"
