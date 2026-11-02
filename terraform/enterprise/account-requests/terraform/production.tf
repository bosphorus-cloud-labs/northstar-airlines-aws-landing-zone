module "production_workload" {
  source = "./modules/aft-account-request"

  control_tower_parameters = {
    AccountEmail              = "northstar-production@example.com"
    AccountName               = "NorthStar Production"
    ManagedOrganizationalUnit = "Production (ou-abcd-01234567)"
    SSOUserEmail              = "cloud-platform@example.com"
    SSOUserFirstName          = "Cloud"
    SSOUserLastName           = "Platform"
  }

  account_tags = {
    Application        = "NorthStar"
    DataClassification = "Confidential"
    Environment        = "Production"
    ManagedBy          = "AFT"
    Owner              = "Airline-Platform"
  }

  change_management_parameters = {
    change_reason       = "Create the Production workload account through the reviewed account-vending process"
    change_requested_by = "cloud-platform@example.com"
  }

  custom_fields = {
    CostCenter            = "CC-EXAMPLE-001"
    GovernanceEnvironment = "production"
    SecurityTier          = "restricted"
  }

  account_customizations_name = "production"
}
