output "api_id" { value = aws_apigatewayv2_api.governance.id }
output "authorizer_id" { value = aws_apigatewayv2_authorizer.cognito.id }
output "execution_arn" { value = aws_apigatewayv2_api.governance.execution_arn }
output "url" { value = "${aws_apigatewayv2_api.governance.api_endpoint}/poc" }

output "allowed_origins" { value = aws_apigatewayv2_api.governance.cors_configuration[0].allow_origins }
