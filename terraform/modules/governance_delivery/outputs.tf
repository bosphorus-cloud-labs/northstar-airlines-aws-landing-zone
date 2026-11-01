output "publisher_role_arn" { value = aws_iam_role.publisher.arn }
output "publisher_policy" { value = aws_iam_role_policy.publisher.policy }
output "trust_policy" { value = aws_iam_role.publisher.assume_role_policy }
