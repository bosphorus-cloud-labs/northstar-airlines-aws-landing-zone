# Mock provider + command=plan ONLY. No AWS calls and no apply/destroy test runs.
mock_provider "aws" {}
variables {
  aws_account_id            = format("%012d", 0)
  cognito_domain_prefix     = "northstar-offline-test"
  hosting_migration_stage   = "legacy"
  github_access_token       = null
  enable_github_hosting     = false
  github_auto_build_enabled = false
}
run "protected_read_surface" {
  command = plan
  assert {
    condition     = length(aws_apigatewayv2_route.reads) == 8
    error_message = "Expose exactly the eight read routes."
  }
  assert {
    condition     = alltrue([for route in aws_apigatewayv2_route.reads : route.authorization_type == "JWT" && route.authorization_scopes == toset(["northstar-governance/read"]) && startswith(route.route_key, "GET ")])
    error_message = "Every data route must require verified read-scope JWT authorization."
  }
  assert {
    condition     = local.frontend_settings.VITE_AUTH_MODE == "cognito" && aws_amplify_branch.poc[0].enable_auto_build == false
    error_message = "Never configure hosted demo bypass or auto-trigger repository builds."
  }
}
