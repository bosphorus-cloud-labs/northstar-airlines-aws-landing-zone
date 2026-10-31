# Single-account POC root

Source-only deployment foundation for one explicitly supplied AWS account in eu-central-1. Nothing is deployed by checking out or validating this root. See the [deployment guide](../../docs/AWS_DEPLOYMENT_FOUNDATION.md) before running any Terraform command.

`terraform init -backend=false`, `terraform validate`, formatting and the mock-provider command=plan tests are the only permitted Terraform operations in Phase 4A. Registry downloads are public; no AWS credentials or endpoints are involved. A normal plan/refresh, remote state initialization, apply and destroy require separate authorization.

Build the local Linux ARM64 ZIP before mock plan tests. Copy neither real account details nor credentials into source. `settings.example.tfvars` and `backend.hcl.example` deliberately contain non-deployable placeholders. `frontend_settings` exports public SPA configuration; `seed_iam_policy` is for a separate short-lived loader, never the runtime/browser. No enterprise resources, provisioners or automatic data loads are present.
