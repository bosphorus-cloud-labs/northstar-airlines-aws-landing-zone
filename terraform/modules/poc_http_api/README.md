# JWT HTTP read API boundary

Reference implementation only until deployment is explicitly authorized. AWS provider >=6.71,<7 and Terraform >=1.14,<2; provider/account/region configuration is owned by the POC root.

Inputs: `name/tags, issuer/client_id, allowed_origin, log_retention_days`. Outputs: `api_id/authorizer_id/execution_arn/url`. See `variables.tf` and `outputs.tf` for the exact typed interface.

Exact-origin CORS and redacted access logs. Root creates eight JWT/scope-protected GET routes and Lambda integration after the independent API ID exists, avoiding composition cycles.

Only the isolated POC root composes this module. Enterprise state and resources must not share ownership. See [deployment guide](../../../docs/AWS_DEPLOYMENT_FOUNDATION.md) for permissions, costs, validation and teardown.
