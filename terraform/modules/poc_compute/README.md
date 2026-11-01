# Read-only Python 3.13 runtime

Used by the deployed single-account POC; future resource changes still require explicit authorization. AWS provider >=6.71,<7 and Terraform >=1.14,<2; provider/account/region configuration is owned by the POC root.

Inputs: `name/tags, table_name/arn, snapshot_id, api_id, issuer/client_id, package_path, log_retention_days, reserved_concurrency, optional permissions_boundary_arn`. Outputs: `invoke_arn/function_name`. See `variables.tf` and `outputs.tf` for the exact typed interface.

ARM64 ZIP required. Pinned mode restricts Query to V1. With delivery enabled, the reader can Query snapshot partitions and GetItem the Current/History catalogue, while retaining only its log-stream writes; it never gains DynamoDB writes. No function URL, networking, deploy action or seed permission.

Only the isolated POC root composes this module. Enterprise state and resources must not share ownership. See [deployment guide](../../../docs/AWS_DEPLOYMENT_FOUNDATION.md) for permissions, costs, validation and teardown.
