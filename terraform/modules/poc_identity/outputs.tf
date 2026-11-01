output "pool_id" { value = aws_cognito_user_pool.governance.id }
output "issuer" { value = "https://${aws_cognito_user_pool.governance.endpoint}" }
output "client_id" { value = aws_cognito_user_pool_client.spa.id }
output "domain" { value = "https://${aws_cognito_user_pool_domain.login.domain}.auth.eu-central-1.amazoncognito.com" }

output "callback_urls" { value = aws_cognito_user_pool_client.spa.callback_urls }
output "logout_urls" { value = aws_cognito_user_pool_client.spa.logout_urls }
