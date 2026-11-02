output "policy_ids" { value = { for name, policy in aws_organizations_policy.customer_managed : name => policy.id } }
output "attachment_targets" { value = { for name, attachment in local.attachments : name => attachment.target } }
