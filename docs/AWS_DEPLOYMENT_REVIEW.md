# Phase 4A adversarial review

Scope: source inspection, public AWS/library documentation and offline validation on `feat/aws-poc-foundation`. No credentials, AWS account endpoints, commands, resource changes, seeding execution, commits or pushes. Mock-provider plans are structural tests, not evidence of AWS deployment compatibility.

## Findings and corrections

| Severity | Finding | Resolution |
| --- | --- | --- |
| Critical | No confirmed critical defect or unauthenticated data path found in the reviewed source. | This is a bounded review, not a penetration-test certification. |
| High | Mangum's default base path left named-stage `/poc/api/v1/...` requests unmatched (404). Previous service tests bypassed Mangum. | Configure the adapter's fixed `/poc` base path. A real in-process handler regression failed before correction and passes for prefixed and relative event paths, repeated invocations, and missing authorizer denial. |
| High | Amplify's `VITE_AUTH_MODE=cognito` was inherited by fixture-based frontend tests, blocking the documented build sequence. | Explicit per-test local configuration in test setup, overridden by authentication tests. Reproduced failure with production-like variables, then reran the full suite successfully under the same variables. No production bypass was added. |
| Medium | There was no transport-level assertion that missing/partial/unavailable DynamoDB data fails safely. | Added configured-app regression checks: sanitized 500, no fixture fallback or governance data. Existing contract/digest tests reject corrupt snapshots. |

## Authentication and data boundaries

React uses the OIDC library's code/S256 PKCE flow, state validation, exact callback, and memory-only user/token storage. Only transaction state persists in sessionStorage. Production settings select Cognito and an absolute Frankfurt API URL including `/poc`; no Vite proxy is used. API Gateway requires JWT authorization and custom read scope on all eight GET routes. Lambda checks the trusted API ID/stage, issuer/client, access-token use, subject, scope and reader group; headers alone do not establish identity. Its production composition cannot select local-demo mode, including with demo environment flags present. Unauthorized requests are rejected before repository access.

Trust is conditional on invocation IAM isolation. A privileged direct Lambda invoker can forge a gateway-shaped event: do not grant that permission to viewers or untrusted CI. Gateway verification is not duplicated as fake application JWT verification. There is no function URL, identity pool, public write route or browser DynamoDB grant. Logout/group removal cannot instantly invalidate an issued access token; lifetime is ten minutes. Cognito supports S256 but its app-client settings do not universally mandate PKCE challenges from other clients.

Runtime IAM permits only `Query` on the exact table and pinned snapshot leading key, and stream writes in its pre-created log group. Loader permissions are a separate output document, not an attached runtime permission or credential. Outputs contain public configuration, resource identifiers and that policy document; only the named `frontend_settings` output belongs in the SPA build. Keep full state/operator outputs private.

Strongly consistent Query pages are validated as one complete content-addressed snapshot before evaluation. They are not a multi-page transaction; the publication marker, conditional loader writes and digest protect against incomplete/inconsistent data. Administrative tampering is detected, not prevented as WORM storage. Evaluation time and all synthetic provenance remain unchanged. Reference findings remain 31 compliant, 3 noncompliant, 6 unknown and 10 stale.

## Exact proposed Terraform resource instances

There are **26 Terraform resource instances**, with the region fixed to `eu-central-1` and the provider restricted to the explicitly supplied account. IAM is account-global; Amplify's managed CDN is global. This list excludes service-managed internals and the separately bootstrapped state bucket. Resource names use the root `name` variable (default `northstar-governance-poc`).

| Terraform address | Count |
| --- | ---: |
| `module.identity.aws_cognito_user_pool.governance` | 1 |
| `module.identity.aws_cognito_resource_server.governance` | 1 |
| `module.identity.aws_cognito_user_group.readers` | 1 |
| `module.identity.aws_cognito_user_pool_client.spa` | 1 |
| `module.identity.aws_cognito_user_pool_domain.login` | 1 |
| `module.data.aws_dynamodb_table.governance` | 1 |
| `module.compute.aws_cloudwatch_log_group.lambda` | 1 |
| `module.compute.aws_iam_role.lambda` | 1 |
| `module.compute.aws_iam_role_policy.runtime` | 1 |
| `module.compute.aws_lambda_function.api` | 1 |
| `module.http.aws_apigatewayv2_api.governance` | 1 |
| `module.http.aws_apigatewayv2_authorizer.cognito` | 1 |
| `module.http.aws_cloudwatch_log_group.access` | 1 |
| `module.http.aws_apigatewayv2_stage.poc` | 1 |
| `aws_apigatewayv2_integration.lambda` | 1 |
| `aws_apigatewayv2_route.reads["/api/v1/health"]` | 1 |
| `aws_apigatewayv2_route.reads["/api/v1/summary"]` | 1 |
| `aws_apigatewayv2_route.reads["/api/v1/accounts"]` | 1 |
| `aws_apigatewayv2_route.reads["/api/v1/accounts/{account_id}"]` | 1 |
| `aws_apigatewayv2_route.reads["/api/v1/findings"]` | 1 |
| `aws_apigatewayv2_route.reads["/api/v1/deployments"]` | 1 |
| `aws_apigatewayv2_route.reads["/api/v1/drift"]` | 1 |
| `aws_apigatewayv2_route.reads["/api/v1/exceptions"]` | 1 |
| `aws_lambda_permission.gateway` | 1 |
| `module.hosting.aws_amplify_app.console` | 1 |
| `aws_amplify_branch.poc` | 1 |

No users, fixture items, OIDC provider/deployment role, state bucket, budgets/alarms, VPC/NAT, Organizations, Control Tower, AFT or other enterprise infrastructure are created by this root. The eight routes are GET-only with JWT/read scope; automatic CORS preflight returns no governance data. CORS, callback and logout all derive from the same Amplify branch origin. API and Lambda log retention default to 14 days. The public SPA client has no secret. API access logs omit tokens, bodies and query strings.

## Deployment blockers and operational acceptance gates

- Explicit deployment authorization, reviewed IAM/bootstrap permissions, a real account variable, available Cognito domain prefix and secure versioned Frankfurt S3 state bucket are still required. The application does not create its own backend. Restrict and verify backend bucket ownership/access separately from the AWS provider's account guard; include ListBucket, state Get/Put and lock Get/Put/Delete permissions. No credentials belong in backend configuration or state.
- Rebuild and review the Linux ARM64/Python 3.13 ZIP after source changes; locally checked wheel metadata and hashes do not prove native execution in Lambda.
- Check regional service quotas, particularly the default reserved Lambda concurrency of two. A reviewed quota increase or explicit documented opt-out is required if AWS cannot retain its unreserved concurrency pool.
- Separately authorize and run the loader, then verify the pinned digest. Before that, authenticated data endpoints intentionally fail. Separately invite users, set up TOTP, verify email and grant the reader group; no account can sign in by default.
- Manual Amplify hosting is prepared, not populated. Public settings must be baked into a reviewed build and uploaded under separate authorization. Repository integration is not wired end to end: source-provider authorization, actual branch selection and manual-app migration/replacement must be validated before enabling any builds. A replacement domain requires synchronized callback, logout, CORS and build settings.
- Real testing must verify Cognito MFA/code/PKCE/callback/logout behavior, gateway signature/audience/scope enforcement and group serialization, CORS preflight, stage routing, IAM-denied reads/writes, log delivery/redaction, deployed headers/SPA rewrites and Linux imports. None is proven by mock-provider tests.

Costs are usage/retention dependent: API requests, Lambda execution, DynamoDB requests/storage/**PITR**, log ingestion/storage, Cognito active users/email, Amplify builds/storage/transfer and state bucket/version storage. PITR and retained data/logs/state can continue costing money without dashboard activity. No provisioned concurrency, NAT, dedicated networking or customer-managed KMS key is created. Throttling/concurrency are not spending caps; review current Frankfurt pricing and authorize budget alerts before deployment.

Cleanup requires a separate reviewed authorization. DynamoDB and Cognito have both service deletion protection and Terraform prevent-destroy guards; those need deliberate reviewed changes. Respect Terraform dependencies for Amplify branch/app, Cognito domain/client/pool, API integration/permission/Lambda and IAM. Retained backups, logs, frontend assets, snapshots and state versions need explicit retention decisions. Keep state until application teardown/recovery requirements are resolved. No destroy was attempted.

## Final local validation

- `.venv/bin/python -m unittest discover -s tests -q`: **63 passed**, including 18 deployment-foundation tests. The negative loader test's confirmation error is expected and creates no SDK client.
- Ruff check/format, Python compileall, pip check, Terraform recursive formatting and Git whitespace checks: passed.
- `terraform -chdir=terraform/poc validate`: passed. `terraform -chdir=terraform/poc test`: **one mock-provider plan test passed**. There was no real plan, apply or destroy.
- Frontend typecheck, ESLint, Prettier, generated API contract check, **36 tests**, and standard production build: passed. The same 36 tests also passed with the six nonfunctional public Cognito/API variables injected as Amplify would inject them.
- A separate production build with validated nonfunctional public settings contained the expected API, issuer, domain, client ID and SPA origin; known synthetic fixture/test-token markers were absent. This proves build-time injection, not a working network/Cognito deployment.
- Rebuilt the Linux ARM64 ZIP after the handler correction; package manifest and current source integrity were checked. Native Linux imports and real Lambda execution are still unverified.

The branch remains uncommitted and unpushed. Main was not modified. Detailed local artifact/file inventories are under ignored `artifacts/validation/`.

Sources: [AWS HTTP API JWT validation](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-jwt-authorizer.html), [AWS HTTP API stage-prefix handling](https://docs.aws.amazon.com/powertools/python/2.33.0/api/event_handler/api_gateway.html), [Mangum adapter](https://github.com/Kludex/mangum/blob/main/mangum/adapter.py), [Cognito TOTP](https://docs.aws.amazon.com/cognito/latest/developerguide/user-pool-settings-mfa-totp.html), [Amplify monorepo configuration](https://docs.aws.amazon.com/amplify/latest/userguide/monorepo-configuration.html). Operational commands, pricing links and prerequisites are in [the deployment foundation guide](AWS_DEPLOYMENT_FOUNDATION.md).
