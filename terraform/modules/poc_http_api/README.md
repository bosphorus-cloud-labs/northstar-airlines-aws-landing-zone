# JWT HTTP read API boundary

Used by the deployed single-account POC; future resource changes still require explicit authorization. AWS provider >=6.71,<7 and Terraform >=1.14,<2; provider/account/region configuration is owned by the POC root.

Inputs: `name/tags, issuer/client_id, allowed_origin, log_retention_days`, plus optional `additional_origins = []`. Outputs: `api_id/authorizer_id/execution_arn/url`, `allowed_origins`. See `variables.tf` and `outputs.tf` for the exact typed interface.

Exact-origin CORS and redacted access logs. Root creates eight JWT/scope-protected GET routes and Lambda integration after the independent API ID exists, avoiding composition cycles.

Only the isolated POC root composes this module. Enterprise state and resources must not share ownership. See [deployment guide](../../../docs/AWS_DEPLOYMENT_FOUNDATION.md) for permissions, costs, validation and teardown.

Additional origins must be explicit lowercase HTTPS DNS origins without paths, trailing slash, ports, user information, query, fragment or wildcards. Existing singular inputs remain required and preserved; duplicates are removed. The identity module derives `/auth/callback` and `/` URLs from each added origin. See the [dual-origin procedure](../../poc/README.md#additional-approved-origins) for coordinated root configuration.
