# Deployment security review

This is a bounded engineering review, not penetration-test certification. [Deployment acceptance](DEPLOYMENT_ACCEPTANCE.md) records the actual resource changes and live tests; [SECURITY.md](../SECURITY.md) records repository security boundaries and advisory checks. Historical source-only test totals and proposed manual-hosting inventories are superseded by that evidence.

## Reviewed trust boundaries

| Boundary | Implemented control | Limit |
| --- | --- | --- |
| Browser → API | Cognito Authorization Code + S256 PKCE; memory-only tokens; exact HTTPS origins | Reload/expiry requires sign-in; issued tokens remain valid until expiry |
| API → Lambda | API Gateway JWT/read scope; Lambda validates configured gateway/stage, issuer/client, access-token use and reader group | Trusted direct Lambda invokers could forge gateway-shaped context; do not grant invoke to viewers |
| Lambda → data | Strongly consistent Query/GetItem on the approved snapshot/catalogue read model; digest validation | No write, Scan, public function URL or fixture fallback; bounded small-fleet reads |
| GitHub → publisher | Exact immutable repository/environment subject, STS audience, protected main, successful CI and actual environment approval | Explicit single-owner POC approval; administrators remain trusted |
| Publisher → Current | Conditional rows, manifest last, strong verification and generation-checked atomic catalogue update | Code-enforced immutability is not WORM; failures can leave unregistered rows but cannot promote incomplete snapshots |

The browser has no AWS credentials or DynamoDB access. The publisher has no Terraform, IAM, Lambda or Amplify deployment authority. A failed or expired exception never converts a finding into a compliance pass. Synthetic distribution and observed compliance evidence remain separate.

## Retained regression provenance

- Named-stage routing originally produced 404s when Mangum received `/poc/api/v1/...`; the fixed base path and gateway-stage checks are covered by handler regressions and live routing tests.
- Frontend tests originally inherited production Cognito settings; test setup now explicitly isolates local identity. Production authentication was not weakened.
- Missing, partial, corrupt and unavailable DynamoDB snapshots fail closed with sanitized errors and no fixture fallback.
- The first approved OIDC bootstrap failed because IAM used the legacy name-only subject. The reviewed correction pins immutable owner/repository IDs plus the exact environment. Actual OIDC bootstrap/publication/rollback/restoration subsequently passed.

## Remaining production work

Real AWS Config/Security Hub evidence collection, multi-account enforcement, enterprise independent approvals, dedicated alerting/budgets, fleet-scale indexed reads, retention/recovery rehearsals and regional failover need separate designs and authorization. CodePipeline/CodeBuild/SNS, Organizations, Control Tower, AFT and inspection networking remain proposed architecture, not deployed services.

Future cloud changes require a fresh scoped plan and authorization. This review does not authorize apply, destroy, import, state changes, data publication or identity changes. Preserve the existing app/pool/client/API/table and immutable history; follow [the operating guide](AWS_DEPLOYMENT_FOUNDATION.md) for deployment and teardown boundaries.
