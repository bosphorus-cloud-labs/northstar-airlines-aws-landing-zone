resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${var.name}"
  retention_in_days = var.log_retention_days
  tags              = var.tags
}
resource "aws_iam_role" "lambda" {
  name                 = "${var.name}-runtime"
  permissions_boundary = var.permissions_boundary_arn
  assume_role_policy   = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Principal = { Service = "lambda.amazonaws.com" }, Action = "sts:AssumeRole" }] })
  tags                 = var.tags
}
resource "aws_iam_role_policy" "runtime" {
  name = "read-pinned-synthetic-snapshot"
  role = aws_iam_role.lambda.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["dynamodb:Query"], Resource = var.table_arn,
    Condition = { "ForAllValues:StringEquals" = { "dynamodb:LeadingKeys" = ["SNAPSHOT#${var.snapshot_id}"] } } },
    { Effect = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents"], Resource = "${aws_cloudwatch_log_group.lambda.arn}:*" }
  ] })
}
resource "aws_lambda_function" "api" {
  function_name                  = var.name
  role                           = aws_iam_role.lambda.arn
  runtime                        = "python3.13"
  architectures                  = ["arm64"]
  handler                        = "backend.lambda_handler.handler"
  filename                       = var.package_path
  source_code_hash               = filebase64sha256(var.package_path)
  memory_size                    = 256
  timeout                        = 20
  reserved_concurrent_executions = var.reserved_concurrency
  environment {
    variables = {
      GOVERNANCE_TABLE  = var.table_name
      SNAPSHOT_ID       = var.snapshot_id
      GATEWAY_API_ID    = var.api_id
      GATEWAY_STAGE     = "poc"
      COGNITO_ISSUER    = var.issuer
      COGNITO_CLIENT_ID = var.client_id
    }
  }
  logging_config {
    log_format            = "JSON"
    application_log_level = "WARN"
    system_log_level      = "WARN"
  }
  depends_on = [aws_iam_role_policy.runtime, aws_cloudwatch_log_group.lambda]
  tags       = var.tags
}
