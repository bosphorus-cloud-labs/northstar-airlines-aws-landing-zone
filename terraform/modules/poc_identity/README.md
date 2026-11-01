# Invited read-only console identity

Used by the deployed single-account POC; future resource changes still require explicit authorization. AWS provider >=6.71,<7 and Terraform >=1.14,<2; provider/account/region configuration is owned by the POC root.

Inputs: `name/tags, callback_url, logout_url, domain_prefix`, plus optional `additional_origins = []`. Outputs: `pool_id/issuer/client_id/domain`, `callback_urls`, `logout_urls`. See `variables.tf` and `outputs.tf` for the exact typed interface.

Lite/classic UI, TOTP MFA, code-only public client and read scope. Terraform creates the reader group without managing user membership; no user/password resources are defined. The SPA implements S256 PKCE; no provider setting universally mandates it.

Only the isolated POC root composes this module. Enterprise state and resources must not share ownership. See [deployment guide](../../../docs/AWS_DEPLOYMENT_FOUNDATION.md) for permissions, costs, validation and teardown.

Additional origins must be explicit lowercase HTTPS DNS origins without paths, trailing slash, ports, user information, query, fragment or wildcards. Existing singular inputs remain required and preserved; duplicates are removed. The identity module derives `/auth/callback` and `/` URLs from each added origin. See the [dual-origin procedure](../../poc/README.md#additional-approved-origins) for coordinated root configuration.
