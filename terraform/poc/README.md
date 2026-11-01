# Single-account POC root

This root manages the existing Frankfurt application, not an enterprise landing zone. [Deployment evidence](../../docs/DEPLOYMENT_ACCEPTANCE.md) records the 29 managed resources and authorized changes; [the operating guide](../../docs/AWS_DEPLOYMENT_FOUNDATION.md) covers state, packaging, security, costs and teardown. Never run apply/destroy/import or modify state as a validation step.

## Configuration and safety

`settings.example.tfvars` and `backend.hcl.example` contain placeholders only. Actual settings, state, saved plans, credentials and packages stay ignored/private. Defaults support unmigrated/manual callers; do not substitute them for the working deployment's explicit settings.

The migrated application uses `enable_github_hosting=true`, `hosting_migration_stage=create_main`, `github_baseline_compatibility=false` and `github_auto_build_enabled=true`. Dynamic reads use `enable_governance_delivery=true` and `governance_catalog_enabled=true`. Preserve the reviewed Lambda package and account/domain/owner settings. Future changes need their own fresh scoped plan and authorization; do not rerun the completed hosting checkpoints.

## Additional approved origins

`additional_origins` is a list of explicit lowercase HTTPS DNS origins, default `[]`. Paths, ports, wildcards, user information, query strings, fragments and trailing slashes are rejected. The root coordinates each added origin across Cognito `/auth/callback`, logout `/` and API CORS; duplicates are removed. Existing singular module inputs remain supported.

The main origin is derived from the existing Amplify app, avoiding a circular dependency with branch build settings. The original poc URLs remain retained for compatibility despite retirement of that hosting branch. An additional origin/domain is an identity/CORS change, not permission to create an app or weaken wildcard restrictions.

## Offline validation

Use a clean checkout without ignored live tfvars/backend cache. `terraform fmt`, `init -backend=false -lockfile=readonly`, `validate`, and the existing mock-provider `command=plan` tests do not deploy resources. Tests require an ignored local ZIP path; CI creates a deliberately nondeployable mock ZIP for this purpose. A normal POC plan/refresh is credentialed, not offline. Real provider-free governance plans belong in `terraform/simulation/`.

Retain the provider lockfile and review upgrades with all tests. POC/enterprise roots must not share state/roles, and the browser/data-CD workflow cannot execute this root. See [historical hosting migration](../../docs/AMPLIFY_GITHUB_INTEGRATION.md) and [protected data delivery](../../docs/GOVERNANCE_DELIVERY.md).
