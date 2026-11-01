# Only a protected GitHub environment can assume this data-publication role.
# No IAM, Terraform, Lambda, Cognito, Amplify or DeleteItem permissions.
resource "aws_iam_openid_connect_provider" "github" {
  count          = var.existing_oidc_provider_arn == null ? 1 : 0
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
  tags           = var.tags
}
locals {
  oidc_arn = var.existing_oidc_provider_arn != null ? var.existing_oidc_provider_arn : aws_iam_openid_connect_provider.github[0].arn
}
# GitHub immutable subject: pin both owner/repository IDs and exact environment.
# Verified with GET /repos/{owner}/{repo}/actions/oidc/customization/sub.
resource "aws_iam_role" "publisher" {
  name                 = "${var.name}-github-publisher"
  max_session_duration = 3600
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect = "Allow", Principal = { Federated = local.oidc_arn }, Action = "sts:AssumeRoleWithWebIdentity",
    Condition = { StringEquals = {
      "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com",
      "token.actions.githubusercontent.com:sub" = "repo:bosphorus-cloud-labs@319390912/northstar-airlines-aws-landing-zone@1440849538:environment:governance-production"
    } }
  }] })
  tags = var.tags
}
resource "aws_iam_role_policy" "publisher" {
  name = "conditional-synthetic-publication-only"
  role = aws_iam_role.publisher.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["dynamodb:Query", "dynamodb:GetItem", "dynamodb:PutItem"], Resource = var.table_arn,
    Condition = { "ForAllValues:StringLike" = { "dynamodb:LeadingKeys" = ["SNAPSHOT#*", "GOVERNANCE#CATALOG"] } } },
    { Effect = "Deny", Action = ["dynamodb:PutItem"], Resource = var.table_arn,
    Condition = { "ForAnyValue:StringEquals" = { "dynamodb:LeadingKeys" = ["SNAPSHOT#${var.baseline_id}"] } } }
  ] })
}
