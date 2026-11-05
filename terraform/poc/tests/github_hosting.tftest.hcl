# Mock command=plan runs only: no real repository, AWS identity or credential.
mock_provider "aws" {
  mock_resource "aws_amplify_app" {
    override_during = plan
    defaults = {
      id             = "synthetic-app-id"
      arn            = "synthetic-app-arn"
      region         = "eu-central-1"
      default_domain = "synthetic.amplifyapp.com"
      build_spec     = "synthetic-manual-build-spec"
    }
  }
}
variables {
  aws_account_id          = format("%012d", 0)
  cognito_domain_prefix   = "northstar-offline-test"
  hosting_migration_stage = "legacy"
  github_access_token     = null
  # Do not inherit the real operator's auto.tfvars integration choice in tests.
  enable_github_hosting     = false
  github_auto_build_enabled = false
}
run "github_hosting_disabled" {
  command = plan
  assert {
    condition     = length(aws_amplify_branch.github_main) == 0 && local.github_origin == null && local.github_frontend_settings == null
    error_message = "Default configuration must leave repository integration and the new main branch disabled."
  }
}
run "github_hosting_staged" {
  command = plan
  variables {
    hosting_migration_stage = "create_main"
    enable_github_hosting   = true
  }
  assert {
    condition = (
      aws_amplify_branch.github_main[0].branch_name == "main" &&
      aws_amplify_branch.github_main[0].enable_auto_build == false &&
      aws_amplify_branch.github_main[0].enable_pull_request_preview == false &&
      aws_amplify_branch.github_main[0].environment_variables["AMPLIFY_MONOREPO_APP_ROOT"] == "frontend" &&
      aws_amplify_branch.github_main[0].environment_variables["VITE_APP_ORIGIN"] == "https://main.synthetic.amplifyapp.com" &&
      length(local.github_frontend_settings) == 7 &&
      local.github_frontend_settings.VITE_GOVERNANCE_API_MODE == "baseline-v1"
    )
    error_message = "Stage only the main monorepo branch with its own six public settings; no automatic build or PR preview."
  }
  assert {
    condition = (
      module.identity.callback_urls == toset(["${local.origin}/auth/callback", "${local.github_origin}/auth/callback"]) &&
      module.identity.logout_urls == toset(["${local.origin}/", "${local.github_origin}/"]) &&
      module.http.allowed_origins == toset([local.origin, local.github_origin]) &&
      length(aws_amplify_branch.poc) == 0
    )
    error_message = "New host must join both allowlists without changing the original build origin or settings."
  }
}
run "github_hosting_additional_origin_preserved" {
  command = plan
  variables {
    hosting_migration_stage = "create_main"
    enable_github_hosting   = true
    additional_origins      = ["https://approved.example.com"]
  }
  assert {
    condition = (
      module.http.allowed_origins == toset([local.origin, local.github_origin, "https://approved.example.com"]) &&
      module.identity.callback_urls == toset(["${local.origin}/auth/callback", "${local.github_origin}/auth/callback", "https://approved.example.com/auth/callback"]) &&
      module.identity.logout_urls == toset(["${local.origin}/", "${local.github_origin}/", "https://approved.example.com/"])
    )
    error_message = "Existing explicitly approved additional origins must remain intact."
  }
}
run "github_auto_build_separately_enabled" {
  command = plan
  variables {
    hosting_migration_stage   = "create_main"
    enable_github_hosting     = true
    github_auto_build_enabled = true
  }
  assert {
    condition     = aws_amplify_branch.github_main[0].enable_auto_build && length(aws_amplify_branch.poc) == 0
    error_message = "Later activation must affect only the new main branch."
  }
}
run "reject_auto_build_without_integration" {
  command = plan
  variables {
    github_auto_build_enabled = true
  }
  expect_failures = [var.github_auto_build_enabled]
}

run "reject_token_only_update" {
  command = plan
  variables {
    enable_github_hosting = false
    github_access_token   = "synthetic-offline-test-input"
  }
  expect_failures = [var.github_access_token]
}

run "retire_manual_checkpoint" {
  command = plan
  variables {
    enable_github_hosting   = true
    hosting_migration_stage = "retire_manual"
  }
  assert {
    condition     = length(aws_amplify_branch.poc) == 0 && length(aws_amplify_branch.github_main) == 0 && !local.repository_connection_enabled && module.http.allowed_origins == toset([local.origin])
    error_message = "Stage A must remove the manual branch without repository connection, main or origin changes."
  }
}
run "connect_repository_checkpoint" {
  command = plan
  variables {
    enable_github_hosting   = true
    hosting_migration_stage = "connect_repository"
  }
  assert {
    condition     = length(aws_amplify_branch.poc) == 0 && length(aws_amplify_branch.github_main) == 0 && local.repository_connection_enabled && module.http.allowed_origins == toset([local.origin])
    error_message = "Stage B connects the repository with no manual or main branch and no identity/CORS changes."
  }
}

run "full_catalog_after_separate_backend_upgrade" {
  command = plan
  variables {
    enable_github_hosting         = true
    hosting_migration_stage       = "create_main"
    github_baseline_compatibility = false
  }
  assert {
    condition     = local.github_frontend_settings.VITE_GOVERNANCE_API_MODE == "catalog"
    error_message = "Full V2-capable frontend must remain available after backend upgrade."
  }
}

run "resource_console_explicit_activation" {
  command = plan
  variables {
    hosting_migration_stage       = "create_main"
    enable_github_hosting         = true
    github_baseline_compatibility = false
    governance_frontend_mode      = "resources"
  }
  assert {
    condition     = aws_amplify_branch.github_main[0].environment_variables["VITE_GOVERNANCE_API_MODE"] == "resources" && aws_amplify_branch.github_main[0].app_id == module.hosting.app_id
    error_message = "Resource activation must use the same existing app/main branch and explicit frontend mode."
  }
}
