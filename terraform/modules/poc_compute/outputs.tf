output "invoke_arn" { value = aws_lambda_function.api.invoke_arn }
output "function_name" { value = aws_lambda_function.api.function_name }

output "runtime_policy" { value = aws_iam_role_policy.runtime.policy }
