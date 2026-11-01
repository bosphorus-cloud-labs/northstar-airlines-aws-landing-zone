# Offline mock plans only: never configure a live AWS provider.
mock_provider "aws" {}
override_module {
  target = module.hosting
  outputs = {
    app_id         = "synthetic-hosting-id"
    default_domain = "original.example.amplifyapp.com"
  }
}
variables {
  aws_account_id            = format("%012d", 0)
  cognito_domain_prefix     = "northstar-offline-test"
  hosting_migration_stage   = "legacy"
  github_access_token       = null
  enable_github_hosting     = false
  github_auto_build_enabled = false
}
run "original_origin_unchanged" {
  command = plan
  assert {
    condition = (
      module.identity.callback_urls == toset(["${local.origin}/auth/callback"]) &&
      module.identity.logout_urls == toset(["${local.origin}/"]) &&
      module.http.allowed_origins == toset([local.origin])
    )
    error_message = "Empty additional origins must preserve the original callback, logout and CORS values."
  }
}
run "second_origin_consistent" {
  command = plan
  variables {
    additional_origins = ["https://main.second.amplifyapp.com", "https://main.second.amplifyapp.com"]
  }
  assert {
    condition = (
      module.identity.callback_urls == toset(["${local.origin}/auth/callback", "https://main.second.amplifyapp.com/auth/callback"]) &&
      module.identity.logout_urls == toset(["${local.origin}/", "https://main.second.amplifyapp.com/"]) &&
      module.http.allowed_origins == toset([local.origin, "https://main.second.amplifyapp.com"])
    )
    error_message = "Both exact origins must be retained consistently; duplicates must be removed."
  }
  assert {
    condition = (
      local.frontend_settings.VITE_APP_ORIGIN == local.origin &&
      aws_amplify_branch.poc[0].branch_name == "poc" &&
      aws_amplify_branch.poc[0].environment_variables["VITE_APP_ORIGIN"] == local.origin &&
      aws_amplify_branch.poc[0].enable_auto_build == false
    )
    error_message = "The original hosted branch and its build origin must remain unchanged."
  }
}

run "unsafe_origin_00" {
  command = plan
  variables { additional_origins = ["http://main.second.amplifyapp.com"] }
  expect_failures = [var.additional_origins]
}

run "unsafe_origin_01" {
  command = plan
  variables { additional_origins = ["https://*.amplifyapp.com"] }
  expect_failures = [var.additional_origins]
}

run "unsafe_origin_02" {
  command = plan
  variables { additional_origins = ["*"] }
  expect_failures = [var.additional_origins]
}

run "unsafe_origin_03" {
  command = plan
  variables { additional_origins = ["https://example.com/"] }
  expect_failures = [var.additional_origins]
}

run "unsafe_origin_04" {
  command = plan
  variables { additional_origins = ["https://example.com/auth/callback"] }
  expect_failures = [var.additional_origins]
}

run "unsafe_origin_05" {
  command = plan
  variables { additional_origins = ["https://user@example.com"] }
  expect_failures = [var.additional_origins]
}

run "unsafe_origin_06" {
  command = plan
  variables { additional_origins = ["https://example.com?x=1"] }
  expect_failures = [var.additional_origins]
}

run "unsafe_origin_07" {
  command = plan
  variables { additional_origins = ["https://example.com#fragment"] }
  expect_failures = [var.additional_origins]
}

run "unsafe_origin_08" {
  command = plan
  variables { additional_origins = ["https://example.com:443"] }
  expect_failures = [var.additional_origins]
}

run "unsafe_origin_09" {
  command = plan
  variables { additional_origins = ["https://localhost"] }
  expect_failures = [var.additional_origins]
}

run "unsafe_origin_10" {
  command = plan
  variables { additional_origins = ["https://127.0.0.1"] }
  expect_failures = [var.additional_origins]
}

run "unsafe_origin_11" {
  command = plan
  variables { additional_origins = [" https://example.com"] }
  expect_failures = [var.additional_origins]
}

run "unsafe_origin_12" {
  command = plan
  variables { additional_origins = ["https://Example.com"] }
  expect_failures = [var.additional_origins]
}

run "unsafe_origin_13" {
  command = plan
  variables { additional_origins = ["https://-bad.example.com"] }
  expect_failures = [var.additional_origins]
}

run "unsafe_origin_14" {
  command = plan
  variables { additional_origins = [null] }
  expect_failures = [var.additional_origins]
}
