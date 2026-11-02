output "aft_admin_role_arn" { value = module.account_factory_for_terraform.aft_admin_role_arn }
output "aft_failure_sns_topic_arn" { value = module.account_factory_for_terraform.aft_failure_sns_topic_arn }
output "aft_request_table_name" { value = module.account_factory_for_terraform.aft_request_table_name }
output "customizations_state_machine_arn" { value = module.account_factory_for_terraform.aft_invoke_customizations_step_function_arn }
