# Encrypted immutable governance snapshot storage

Reference implementation only until deployment is explicitly authorized. AWS provider >=6.71,<7 and Terraform >=1.14,<2; provider/account/region configuration is owned by the POC root.

Inputs: `name/tags`. Outputs: `table_name/table_arn`. See `variables.tf` and `outputs.tf` for the exact typed interface.

PAY_PER_REQUEST, PITR, AWS-managed encryption and deletion protection. No seed writes or credentials. Prevent-destroy requires a separately reviewed teardown change.

Only the isolated POC root composes this module. Enterprise state and resources must not share ownership. See [deployment guide](../../../docs/AWS_DEPLOYMENT_FOUNDATION.md) for permissions, costs, validation and teardown.
