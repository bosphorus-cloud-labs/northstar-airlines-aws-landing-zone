# Single-account AWS deployment guide

The POC is deployed in eu-central-1. [Acceptance evidence](DEPLOYMENT_ACCEPTANCE.md) records the authorized changes and successful cloud checks. This guide describes the existing design and future operating procedures; it is not standing permission to deploy or tear down resources.

## Actual scope

React/Vite on the existing GitHub-connected Amplify app → Cognito Authorization Code + S256 PKCE → HTTP API JWT authorizer → Python 3.13 ARM64 Lambda/Mangum → DynamoDB immutable snapshots and Current/History. CloudWatch provides bounded log retention. A separate GitHub OIDC publisher writes approved synthetic snapshots; browser and Lambda remain read-only.

The isolated `terraform/poc/` root composes `poc_identity`, `poc_data`, `poc_compute`, `poc_http_api`, `poc_hosting` and optional `governance_delivery` modules. Region is fixed and `allowed_account_ids` restricts provider use. Enterprise roots do not share ownership, state or execution roles. No real member accounts, VPC/NAT, Transit Gateway, inspection firewall, Organizations, Control Tower, AFT, EventBridge processor or CodePipeline/SNS resources are deployed.

Terraform is constrained to >=1.14,<2; the POC locks AWS provider 6.71.0 for supported platforms. Module constraints permit compatible 6.x providers, but root upgrades require reviewed lockfile and full validation. `terraform validate` and mock-provider tests are offline checks; a normal plan/refresh accesses AWS and requires authorization.

## Authentication and least privilege

The public SPA client has no secret. Cognito provides invited users, TOTP and the custom `northstar-governance/read` scope. Terraform creates the reader group but does not manage user credentials, MFA secrets or memberships. API Gateway verifies JWT signature, issuer, audience/client binding, validity and scope. Lambda then checks the trusted API/stage, access-token identity and `governance-readers` membership.

Tokens stay in memory; only PKCE transaction state uses sessionStorage. Reload/expiry requires sign-in again through Cognito SSO. The SPA always supplies S256 PKCE, but Cognito's app-client configuration does not universally require a challenge from every possible client. Logout/group removal does not instantly invalidate an already issued JWT; the ten-minute access-token lifetime bounds that delay.

There is no function URL or browser AWS identity. Lambda invocation permission is restricted to the configured API/account/stage/GET path. Privileged direct invokers and account administrators remain trusted: the application consumes the gateway's verified context rather than pretending to independently verify arbitrary bearer headers. Local-demo mode is explicitly loopback-only and impossible in deployed composition.

Callbacks, logout URLs and CORS use explicit approved HTTPS origins. Preflight returns no governance data. All eight data/health routes require JWT/read scope; no public write routes or exception-approval API exists. Logs exclude tokens, bodies, user emails and query strings.

## Storage, publication and recovery

DynamoDB uses on-demand capacity, encryption, PITR and deletion protection, plus Terraform prevent-destroy. Snapshots live under `SNAPSHOT#<digest>`; ordered payload rows and a final manifest encode the approved inventory, evidence, policy/environment configuration and context. Strongly consistent bounded Query pages are decoded and digest-verified before evaluation. Missing/corrupt/partial data fails closed.

`GOVERNANCE#CATALOG`/`STATE` records immutable revision descriptors/provenance, Current, generation and promotion history. The reader uses Query for snapshots and GetItem for the catalogue, never writes or Scan. The publisher has table-scoped Query/GetItem/PutItem with an explicit V1-write denial; it cannot provision infrastructure or delete records. Conditional immutability is enforced by reviewed code, not a DynamoDB WORM feature.

Normal publication/reselection uses [the protected OIDC workflow](GOVERNANCE_DELIVERY.md), not direct loading from a workstation. Manifest-last insertion and strong verification precede a generation-checked atomic selection update. Rollback/restoration reselects a registered revision without rewriting its rows or provenance. Lost responses must be resolved by strong read/history inspection, not blind retries or claims that Current stayed unchanged.

`scripts.seed_governance` remains the original baseline preparation/bootstrap utility. Its no-execute form is offline. Its explicit execute form requires a separately approved temporary loader principal and matching table confirmation. Do not rerun it against the working deployment or substitute its broader initial-loader scope for the data-CD role. Terraform and the API never seed records.

## Lambda packaging and public frontend configuration

Build from Linux ARM64 Python 3.13 wheels, never the workstation virtual environment:

```sh
.venv/bin/python -m pip install --platform manylinux2014_aarch64 --implementation cp \
  --python-version 3.13 --abi cp313 --only-binary=:all: \
  -r backend/requirements.txt --target artifacts/lambda/vendor
.venv/bin/python -m scripts.package_lambda --output artifacts/lambda/governance-delivery.zip
```

Use an empty vendor directory for a new dependency set; the builder rejects duplicate/stale/non-Linux metadata and checks the complete pins. It assembles deterministic code/schema payloads, excludes fixtures/tests/local settings and omits the publisher. ZIPs and vendor files remain ignored. Package validation is not permission to update Lambda; code changes require a separate reviewed plan.

The existing `amplify.yml` builds `frontend/` with Node 24, `npm ci`, type/lint/tests and `dist` output. Terraform supplies six public API/Cognito/origin settings plus explicit catalogue mode and the monorepo root. No local Vite proxy exists in Amplify. App-wide automatic builds remain disabled; only the protected main branch has auto-build enabled, with PR previews disabled. A main source merge builds frontend assets only, never Terraform or data publication.

For explicitly authorized manual/static consumers, `scripts.frontend_config` retains its six-setting `frontend_settings` contract and writes ignored `.env.production.local`. Hosted main instead consumes `github_frontend_settings` directly, including catalogue mode; do not feed that extended object to the six-setting converter. Never pass full state or secret-bearing outputs. Missing production configuration fails closed. [The historical existing-app migration](AMPLIFY_GITHUB_INTEGRATION.md) explains why the original app ID/resource address were preserved; it is not a procedure to rerun on the working app.

## State, IAM and future deployment authorization

The private remote state backend is bootstrapped separately and uses encryption, versioning, restricted access and locking. Provider account restrictions do not verify backend bucket ownership; verify the state bucket independently. Scope state/lock permissions to the exact key and preserve state until retention/recovery requirements are resolved. Never commit backend credentials, state, local tfvars, saved plans, package ZIPs or generated settings.

State and saved plans can contain the GitHub repository-setup token. Preserve approved sensitive inputs through the operator's secure mechanism so a fresh plan does not introduce unrelated app drift. Never print full state/plan contents, put tokens in command history or upload them as Actions artifacts. Current OIDC/data-delivery configuration does not require a permanent AWS key in GitHub.

GitHub CI is unprivileged; only the protected data publication job has `id-token: write`. Trust pins the immutable owner/repository IDs, exact `governance-production` environment and `sts.amazonaws.com` audience. Main requires PR/CI; the explicitly documented single-owner approval model permits self-review while disabling administrator bypass. The default independent model is available for enterprise teams. Neither data-CD nor reader roles can run Terraform. Infrastructure deployment IAM/state access remains a separately authorized operator concern.

## Cost, operations and teardown

Low-cost defaults include HTTP API, ARM64/256 MB Lambda, bounded timeout/concurrency, gateway throttling, on-demand DynamoDB, static hosting and 14-day logs. They are not hard spending caps. API traffic, Lambda execution, DynamoDB strong reads/storage/PITR, retained history, CloudWatch logs, Cognito, Amplify builds/transfer and state versions may incur charges even with a small fleet. Review [AWS Pricing Calculator](https://calculator.aws/) and [service pricing](https://aws.amazon.com/pricing/) for current account-specific rates; no free-tier entitlement or fixed bill is promised.

Dedicated budgets/alerts, WAF, fleet-scale queries, durable security telemetry, real AWS Config/Security Hub collection and regional failover are not implemented. Catalogue/history limits stop publication rather than deleting evidence. Future versions require reviewed profiles and source-bound snapshots. Follow the existing interview fallback rather than repairing AWS during a presentation.

Teardown requires separate authorization and a reviewed destroy plan. Preserve needed snapshots/state/backups first; disable builds/traffic and remove temporary publisher access according to the approved procedure. Cognito and DynamoDB have service deletion protection and Terraform lifecycle guards; deliberately review any removal of those protections. Respect branch/app, domain/client/pool, API/Lambda/IAM and retained-log dependencies. Never remove state before resource ownership and recovery requirements are resolved. No teardown or state manipulation is part of repository hygiene.

## Validation

Use the [README](../README.md) and CI workflow for Python/frontend checks. In a clean checkout without ignored live settings, run Terraform formatting, `init -backend=false -lockfile=readonly`, validate and the existing `command=plan` mock tests with an ignored test ZIP. Use `terraform/simulation/` for actual provider-free planning/parity. Do not use a normal POC plan as an offline check or run apply/destroy to validate the simulation. [Security review](AWS_DEPLOYMENT_REVIEW.md) and [acceptance evidence](DEPLOYMENT_ACCEPTANCE.md) distinguish local/mock tests from real deployed verification.
