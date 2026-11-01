# Plan-only IAM assertions; synthetic ARNs, no AWS calls or real account discovery.
mock_provider "aws" {}
override_resource {
  override_during = plan
  target          = module.data.aws_dynamodb_table.governance
  values          = { arn = "arn:aws:dynamodb:eu-central-1:000000000000:table/northstar-offline-records" }
}
override_resource {
  override_during = plan
  target          = module.compute.aws_cloudwatch_log_group.lambda
  values          = { arn = "arn:aws:logs:eu-central-1:000000000000:log-group:offline" }
}
variables {
  aws_account_id             = format("%012d", 0)
  cognito_domain_prefix      = "northstar-offline-test"
  hosting_migration_stage    = "legacy"
  github_access_token        = null
  enable_github_hosting      = false
  github_auto_build_enabled  = false
  enable_governance_delivery = true
  governance_catalog_enabled = false
  github_oidc_provider_arn   = "arn:aws:iam::000000000000:oidc-provider/token.actions.githubusercontent.com"
}
run "publisher_and_reader_boundaries" {
  command = plan
  assert {
    condition = (
      toset(jsondecode(module.delivery[0].publisher_policy).Statement[0].Action) == toset(["dynamodb:GetItem", "dynamodb:Query", "dynamodb:PutItem"]) &&
      jsondecode(module.delivery[0].publisher_policy).Statement[1].Effect == "Deny" &&
      toset(jsondecode(module.delivery[0].publisher_policy).Statement[1].Condition["ForAnyValue:StringEquals"]["dynamodb:LeadingKeys"]) == toset(["SNAPSHOT#${local.snapshot_id}"])
    )
    error_message = "Publisher must be data-only with an explicit V1 write deny."
  }
  assert {
    condition     = alltrue([for statement in jsondecode(module.compute.runtime_policy).Statement : alltrue([for action in statement.Action : contains(["dynamodb:GetItem", "dynamodb:Query", "logs:CreateLogStream", "logs:PutLogEvents"], action)])])
    error_message = "Runtime must never acquire DynamoDB writes or deployment authority."
  }
  assert {
    condition     = jsondecode(module.delivery[0].trust_policy).Statement[0].Condition.StringEquals["token.actions.githubusercontent.com:sub"] == "repo:bosphorus-cloud-labs/northstar-airlines-aws-landing-zone:environment:governance-production"
    error_message = "OIDC must be scoped to the exact repository and protected environment."
  }
}
run "catalogue_requires_reader_iam" {
  command = plan
  variables {
    enable_governance_delivery = false
    governance_catalog_enabled = true
  }
  expect_failures = [var.governance_catalog_enabled]
}
