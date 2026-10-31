resource "aws_apigatewayv2_api" "governance" {
  name          = var.name
  protocol_type = "HTTP"
  cors_configuration {
    allow_origins     = [var.allowed_origin]
    allow_methods     = ["GET", "OPTIONS"]
    allow_headers     = ["authorization", "content-type"]
    allow_credentials = false
    max_age           = 300
  }
  tags = var.tags
}
resource "aws_apigatewayv2_authorizer" "cognito" {
  api_id           = aws_apigatewayv2_api.governance.id
  authorizer_type  = "JWT"
  identity_sources = ["$request.header.Authorization"]
  name             = "cognito-access-token"
  jwt_configuration {
    audience = [var.client_id]
    issuer   = var.issuer
  }
}
resource "aws_cloudwatch_log_group" "access" {
  name              = "/northstar/${var.name}/http"
  retention_in_days = var.log_retention_days
  tags              = var.tags
}
resource "aws_apigatewayv2_stage" "poc" {
  api_id      = aws_apigatewayv2_api.governance.id
  name        = "poc"
  auto_deploy = true
  default_route_settings {
    throttling_burst_limit   = 10
    throttling_rate_limit    = 5
    detailed_metrics_enabled = false
  }
  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.access.arn
    format          = jsonencode({ requestId = "$context.requestId", routeKey = "$context.routeKey", status = "$context.status", integrationStatus = "$context.integrationStatus", responseLength = "$context.responseLength" })
  }
  tags = var.tags
}
