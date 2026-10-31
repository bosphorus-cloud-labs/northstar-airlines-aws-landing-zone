# Invited read-only console identity

Reference implementation only until deployment is explicitly authorized. AWS provider >=6.71,<7 and Terraform >=1.14,<2; provider/account/region configuration is owned by the POC root.

Inputs: `name/tags, callback_url, logout_url, domain_prefix`. Outputs: `pool_id/issuer/client_id/domain`. See `variables.tf` and `outputs.tf` for the exact typed interface.

Lite/classic UI, TOTP MFA, code-only public client and read scope. Reader group is empty; no user/password resources. The SPA implements S256 PKCE; no provider setting universally mandates it.

Only the isolated POC root composes this module. Enterprise state and resources must not share ownership. See [deployment guide](../../../docs/AWS_DEPLOYMENT_FOUNDATION.md) for permissions, costs, validation and teardown.
