locals {
  tags        = { Project = "NorthStar", Environment = "poc", Owner = var.owner, ManagedBy = "Terraform", DataClassification = "synthetic" }
  snapshot_id = jsondecode(file("${path.module}/../../mock-data/snapshot.v1.manifest.json")).sha256
  origin      = "https://poc.${module.hosting.default_domain}"
  frontend_settings = {
    VITE_AUTH_MODE         = "cognito"
    VITE_API_BASE_URL      = module.http.url
    VITE_COGNITO_ISSUER    = module.identity.issuer
    VITE_COGNITO_CLIENT_ID = module.identity.client_id
    VITE_COGNITO_DOMAIN    = module.identity.domain
    VITE_APP_ORIGIN        = local.origin
  }
}
module "hosting" {
  source                = "../modules/poc_hosting"
  name                  = var.name
  tags                  = local.tags
  github_repository_url = local.repository_connection_enabled ? "https://github.com/bosphorus-cloud-labs/northstar-airlines-aws-landing-zone" : null
  github_access_token   = var.github_access_token
  github_build_spec     = local.repository_connection_enabled ? file("${path.module}/../../amplify.yml") : null
}
module "identity" {
  source             = "../modules/poc_identity"
  name               = var.name
  tags               = local.tags
  callback_url       = "${local.origin}/auth/callback"
  logout_url         = "${local.origin}/"
  additional_origins = local.approved_additional_origins
  domain_prefix      = var.cognito_domain_prefix
}
module "data" {
  source = "../modules/poc_data"
  name   = var.name
  tags   = local.tags
}
module "http" {
  source             = "../modules/poc_http_api"
  name               = var.name
  tags               = local.tags
  issuer             = module.identity.issuer
  client_id          = module.identity.client_id
  allowed_origin     = local.origin
  additional_origins = local.approved_additional_origins
  log_retention_days = var.log_retention_days
}
module "compute" {
  source                   = "../modules/poc_compute"
  name                     = var.name
  tags                     = local.tags
  table_arn                = module.data.table_arn
  table_name               = module.data.table_name
  snapshot_id              = local.snapshot_id
  api_id                   = module.http.api_id
  issuer                   = module.identity.issuer
  client_id                = module.identity.client_id
  reserved_concurrency     = var.lambda_reserved_concurrency
  package_path             = var.lambda_package_path
  log_retention_days       = var.log_retention_days
  permissions_boundary_arn = var.permissions_boundary_arn
}
resource "aws_apigatewayv2_integration" "lambda" {
  api_id                 = module.http.api_id
  integration_type       = "AWS_PROXY"
  integration_uri        = module.compute.invoke_arn
  payload_format_version = "2.0"
  timeout_milliseconds   = 25000
}
resource "aws_apigatewayv2_route" "reads" {
  for_each             = toset(["/api/v1/health", "/api/v1/summary", "/api/v1/accounts", "/api/v1/accounts/{account_id}", "/api/v1/findings", "/api/v1/deployments", "/api/v1/drift", "/api/v1/exceptions"])
  api_id               = module.http.api_id
  route_key            = "GET ${each.value}"
  target               = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type   = "JWT"
  authorizer_id        = module.http.authorizer_id
  authorization_scopes = ["northstar-governance/read"]
}
resource "aws_lambda_permission" "gateway" {
  statement_id   = "OnlyGovernanceGatewayReads"
  action         = "lambda:InvokeFunction"
  function_name  = module.compute.function_name
  principal      = "apigateway.amazonaws.com"
  source_account = var.aws_account_id
  source_arn     = "${module.http.execution_arn}/poc/GET/api/v1/*"
}
# Preserve the legacy branch's identity when introducing its retirement switch.
moved {
  from = aws_amplify_branch.poc
  to   = aws_amplify_branch.poc[0]
}
resource "aws_amplify_branch" "poc" {
  count                 = var.hosting_migration_stage == "legacy" ? 1 : 0
  app_id                = module.hosting.app_id
  branch_name           = "poc"
  framework             = "React"
  stage                 = "DEVELOPMENT"
  enable_auto_build     = false
  environment_variables = merge(local.frontend_settings, { AMPLIFY_MONOREPO_APP_ROOT = "frontend" })
  tags                  = local.tags
}
output "frontend_settings" {
  value       = local.frontend_settings
  description = "Public build configuration, not secrets; bake into the Vite build."
}
output "api_url" { value = module.http.url }
output "app_origin" { value = local.origin }
output "cognito_pool_id" { value = module.identity.pool_id }
output "table_name" { value = module.data.table_name }
output "snapshot_id" { value = local.snapshot_id }
output "seed_iam_policy" {
  description = "Attach only to a separately approved short-lived loader role, never the browser/runtime role."
  value = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Action = ["dynamodb:PutItem", "dynamodb:GetItem"], Resource = module.data.table_arn,
  Condition = { "ForAllValues:StringEquals" = { "dynamodb:LeadingKeys" = ["SNAPSHOT#${local.snapshot_id}"] } } }] })
}
