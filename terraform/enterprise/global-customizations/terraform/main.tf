data "aws_caller_identity" "current" {}

resource "aws_iam_account_password_policy" "baseline" {
  minimum_password_length        = 20
  require_lowercase_characters   = true
  require_numbers                = true
  require_symbols                = true
  require_uppercase_characters   = true
  allow_users_to_change_password = true
  max_password_age               = 90
  password_reuse_prevention      = 24
}

resource "aws_s3_account_public_access_block" "baseline" {
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

output "customized_account_id" { value = data.aws_caller_identity.current.account_id }
