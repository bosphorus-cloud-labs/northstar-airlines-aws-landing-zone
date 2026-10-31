resource "aws_cognito_user_pool" "governance" {
  name                     = var.name
  user_pool_tier           = "LITE"
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]
  deletion_protection      = "ACTIVE"
  mfa_configuration        = "ON"
  software_token_mfa_configuration { enabled = true }
  admin_create_user_config { allow_admin_create_user_only = true }
  password_policy {
    minimum_length                   = 14
    require_lowercase                = true
    require_uppercase                = true
    require_numbers                  = true
    require_symbols                  = true
    temporary_password_validity_days = 3
  }
  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }
  tags = var.tags
  lifecycle { prevent_destroy = true }
}
resource "aws_cognito_resource_server" "governance" {
  identifier   = "northstar-governance"
  name         = "NorthStar governance reads"
  user_pool_id = aws_cognito_user_pool.governance.id
  scope {
    scope_name        = "read"
    scope_description = "Read synthetic governance evidence"
  }
}
resource "aws_cognito_user_group" "readers" {
  user_pool_id = aws_cognito_user_pool.governance.id
  name         = "governance-readers"
  description  = "Explicitly invited governance console readers; no write authority"
}
resource "aws_cognito_user_pool_client" "spa" {
  name                                 = "${var.name}-spa"
  user_pool_id                         = aws_cognito_user_pool.governance.id
  generate_secret                      = false
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["openid", "email", "profile", "${aws_cognito_resource_server.governance.identifier}/read"]
  supported_identity_providers         = ["COGNITO"]
  explicit_auth_flows                  = ["ALLOW_REFRESH_TOKEN_AUTH"]
  callback_urls                        = [var.callback_url]
  logout_urls                          = [var.logout_url]
  prevent_user_existence_errors        = "ENABLED"
  enable_token_revocation              = true
  access_token_validity                = 10
  id_token_validity                    = 10
  refresh_token_validity               = 1
  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "days"
  }
}
resource "aws_cognito_user_pool_domain" "login" {
  domain                = var.domain_prefix
  user_pool_id          = aws_cognito_user_pool.governance.id
  managed_login_version = 1
}
