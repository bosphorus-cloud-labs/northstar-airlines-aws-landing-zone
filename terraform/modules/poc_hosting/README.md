# Static Amplify app without source-provider credentials

Reference implementation only until deployment is explicitly authorized. AWS provider >=6.71,<7 and Terraform >=1.14,<2; provider/account/region configuration is owned by the POC root.

Inputs: `name/tags`. Outputs: `app_id/default_domain`. See `variables.tf` and `outputs.tf` for the exact typed interface.

Root creates the poc branch and public build variables after Cognito/API composition. No automatic builds, repository token, upload or deployment job. Repository association is explicitly operator-managed later.

Only the isolated POC root composes this module. Enterprise state and resources must not share ownership. See [deployment guide](../../../docs/AWS_DEPLOYMENT_FOUNDATION.md) for permissions, costs, validation and teardown.
