# Single-account POC root

Source-only deployment foundation for one explicitly supplied AWS account in eu-central-1. Nothing is deployed by checking out or validating this root. See the [deployment guide](../../docs/AWS_DEPLOYMENT_FOUNDATION.md) before running any Terraform command.

`terraform init -backend=false`, `terraform validate`, formatting and the mock-provider command=plan tests are the only permitted Terraform operations in Phase 4A. Registry downloads are public; no AWS credentials or endpoints are involved. A normal plan/refresh, remote state initialization, apply and destroy require separate authorization.

Build the local Linux ARM64 ZIP before mock plan tests. Copy neither real account details nor credentials into source. `settings.example.tfvars` and `backend.hcl.example` deliberately contain non-deployable placeholders. `frontend_settings` exports public SPA configuration; `seed_iam_policy` is for a separate short-lived loader, never the runtime/browser. No enterprise resources, provisioners or automatic data loads are present.

## Additional approved origins

`additional_origins` is a `list(string)` defaulting to `[]`. The existing manually hosted `poc` origin, its callback/logout URLs and its build settings remain unchanged. The root passes this same list to identity and HTTP modules: each origin adds a Cognito `/auth/callback` URL, a logout `/` URL and one exact CORS origin. Existing module callers can keep the singular `callback_url`, `logout_url` and `allowed_origin` inputs unchanged.

Use only approved origins you control. Validation accepts lowercase HTTPS DNS names and rejects HTTP, IP/localhost, wildcards, paths, trailing slash, ports (including :443), user information, query strings, fragments and null list elements. Duplicate entries are removed. This allowlist does not create another Amplify application, grant users access or bypass JWT/scope checks. Removing an additional origin later revokes that origin's configured redirects/CORS; it does not delete an app.

Offline checks (no AWS API calls; existing local provider and Lambda package required):

```sh
terraform fmt -check terraform/poc terraform/modules/poc_identity terraform/modules/poc_http_api
terraform -chdir=terraform/poc init -backend=false
terraform -chdir=terraform/poc validate
# Every test run uses command=plan and the mock AWS provider, never apply.
mkdir -p artifacts/validation
terraform -chdir=terraform/poc test -json -verbose -filter=tests/origins.tftest.hcl > artifacts/validation/origins.jsonl
python terraform/poc/tests/check_origin_plans.py artifacts/validation/origins.jsonl
```

The mock plan comparison checks the same resource addresses and all planned configuration, allowing differences only in the existing Cognito SPA client's `callback_urls`/`logout_urls` and existing HTTP API's `cors_configuration.allow_origins`. This is not a live-state migration plan or proof of AWS deployment compatibility. Mock plans start with empty synthetic state, so their create actions do not describe changes to the deployed POC.

After separate authorization, add the approved additional HTTPS origin to an ignored deployment tfvars file, with no trailing slash:

```hcl
additional_origins = ["https://approved.example.com"] # Replace this example with the approved additional origin.
```

Alternatively, after normal approved state initialization, prepare a review plan using the existing authorized settings plus the exact origin (do not execute as part of this offline task):

```sh
terraform -chdir=terraform/poc plan -var-file=settings.tfvars \
  -var='additional_origins=["https://approved.example.com"]' \
  -out=../../artifacts/dual-origin.tfplan
terraform -chdir=terraform/poc show -no-color ../../artifacts/dual-origin.tfplan
```

Replace the example hostname with the approved additional origin before use. Review for exactly two in-place resource updates: `module.identity.aws_cognito_user_pool_client.spa` (callback/logout lists) and `module.http.aws_apigatewayv2_api.governance` (CORS origins). Stop if any other change, replacement, creation or destruction appears; investigate state/source drift without targeted applies. Those dual-origin-only commands require separate authorization; the existing-app integration investigation is described below.

The generic allowlist above supports other approved origins but does not provision them. For this project's GitHub integration, use the existing-app option below: its main branch origin is added automatically, so do not duplicate it manually in `additional_origins`.

## Staged migration to GitHub hosting

See [the migration procedure](../../docs/AMPLIFY_GITHUB_INTEGRATION.md). AWS requires deleting the old manual branch before connecting the existing app. `hosting_migration_stage` advances through `legacy`, `retire_manual`, `connect_repository`, `create_main` with separate verified plans/applies. The app is never recreated. Stage A was completed and verified; the owner reports repository connection and main creation are complete. Local settings are now at create_main. Do not rerun retirement during source release preparation.

Main builds default off. Its six public connection settings are supplemented by explicit `VITE_GOVERNANCE_API_MODE=baseline-v1` for the currently deployed V1 backend. Full V2/catalogue source remains available after the separately authorized backend upgrade. Credentials, resource changes and source publication require separate authorization.
