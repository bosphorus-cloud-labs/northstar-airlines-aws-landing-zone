# AWS deployment acceptance — 1 November 2026

This records actual cloud execution separately from the synthetic account rollout. The same Amplify application, Cognito pool/client/users, API Gateway, Lambda and DynamoDB table are preserved in eu-central-1. No enterprise AWS accounts or landing-zone resources were created.

## Execution evidence

| Stage | Actual result | Evidence |
| --- | --- | --- |
| Source delivery | PRs merged through the configured main/CI path | [delivery #9](https://github.com/bosphorus-cloud-labs/northstar-airlines-aws-landing-zone/pull/9), [single-owner approval #10](https://github.com/bosphorus-cloud-labs/northstar-airlines-aws-landing-zone/pull/10), [immutable OIDC correction #11](https://github.com/bosphorus-cloud-labs/northstar-airlines-aws-landing-zone/pull/11) |
| Exact deployment source CI | Passed | [main CI](https://github.com/bosphorus-cloud-labs/northstar-airlines-aws-landing-zone/actions/runs/41311346658) |
| V1 bootstrap | Real protected approval/OIDC; generation 1, no V1 record rewrite | [bootstrap](https://github.com/bosphorus-cloud-labs/northstar-airlines-aws-landing-zone/actions/runs/41311406069) |
| Application activation | Existing Lambda catalogue flag and main frontend API-mode setting only; Amplify release job 2 build/deploy/verify succeeded | [live console](https://main.d1eetlse86595h.amplifyapp.com/) |
| V2 publication | Real OIDC conditional publication, strong digest verification; generation 2 | [publication](https://github.com/bosphorus-cloud-labs/northstar-airlines-aws-landing-zone/actions/runs/41312091632) |
| Rollback | Approved registered selection to V1; generation 3; both digests retained | [rollback](https://github.com/bosphorus-cloud-labs/northstar-airlines-aws-landing-zone/actions/runs/41312693235) |
| Restore V2 | Real approval/OIDC succeeded; V2 Current at generation 4, both digests intact | [restoration](https://github.com/bosphorus-cloud-labs/northstar-airlines-aws-landing-zone/actions/runs/41313209411) |
| Main-only Amplify auto-build | Enabled only on existing main branch; app-wide auto-build remains disabled | One-field in-place Terraform update; source-merge build verification reported with the final delivery |

Source bound to the published snapshots: `ecf7b98bcd10978e11fbbeae67c200f2aa412726`. V1 source provenance here records verification/bootstrap of the original baseline, not its original deployment commit. Restoration uses the existing `rollback` action to reselect registered V2; it does not publish a new V2 digest.

## Exact Terraform changes applied

| Plan | Changes |
| --- | --- |
| Foundation | 3 creates: GitHub OIDC provider, publisher IAM role, publisher inline policy. 2 updates: existing Lambda package and runtime read policy. |
| OIDC correction | 1 in-place publisher trust update: immutable owner/repository IDs plus exact environment, same STS audience. |
| Catalogue activation | 2 in-place updates: Lambda `GOVERNANCE_CATALOG_MODE=dynamodb`; existing Amplify main `VITE_GOVERNANCE_API_MODE=catalog`. |
| Main-only auto-build | 1 in-place update: existing Amplify main `enable_auto_build=true`; app defaults stay false, no preview branches. |

All plans were refreshed against actual remote state, inspected with exact-address/field guards, and applied only within the authorized scope. Zero destroys/replacements. Runtime role remains read-only; publisher cannot write V1, delete records, deploy infrastructure or modify services. State, setup-token inputs, plans and package ZIPs stay ignored/local; none are public source artifacts.

## Snapshot evidence

| Revision | Digest | Evaluation time | Accounts | Findings compliant / noncompliant / unknown / stale |
| --- | --- | --- | --- | --- |
| 1.0.0 | `08456a729e0dbe3b2bf36f02f79baa4778a8eaf518d1761831607fbf08de97dd` | 2026-10-31T12:00:00Z | 10 | 31 / 3 / 6 / 10 |
| 2.0.0 | `1e00c3c3e1919a59dd16a83f092d1c2bab2cdff68c0999c33cb1735822098fc5` | 2026-10-31T12:28:00Z | 11 | 43 / 4 / 9 / 10 |

Both snapshots were re-read strongly consistently and decoded/digest-verified after publication, rollback and restoration. Catalogue history links exact source commit, workflow operation, previous/target digest and generation. It is retained across selection changes. Fixed evaluation times are synthetic reference times, not real publication timestamps. GitHub workflow/approval evidence records the actual execution times.

## Verification and limits

- 132 Python tests; 48 frontend tests; 29 Terraform mock plan tests; CI provider-free Terraform fmt/init/validate/plan and full simulator parity passed. Mock tests do not prove AWS compatibility; real apply/runtime verification is listed separately above.
- Real Cognito Authorization Code + PKCE sign-in and authenticated API data verified in all six live pages, including account detail for sim-account-011, search, pagination, responsive navigation and V1 History comparison. No new frontend build was needed for V2 publication or rollback/restoration. The dashboard resolves Current from the catalogue; tokens remain memory-only, so reload/expiry requires Cognito SSO.
- Real API denied missing/invalid authentication. IAM policy simulation verified publisher V1-write/delete denial and Lambda-write denial; IAM simulation is not a real write attempt.
- Negative generation/incomplete-package/digest checks used the live catalogue with every write blocked by the test client. Current remained unchanged. Idempotent promotion replay returned the same real catalogue generation with no write. A retry of the superseded V2 publication after V1 rollback was also rejected before any write. Partial insertion/network-loss/concurrent-CAS fault injection and conditional row retries are covered offline, not by corrupting production data.
- Actual GitHub environment approvals are mandatory. This is explicitly single-owner approval, not enterprise independent review. Trust uses exact immutable IDs and environment, no repository/branch wildcard. CI has no AWS identity; browser/Lambda cannot publish.
- Compliance, account provisioning, AFT distribution, canary and failure/retry evidence are synthetic. No live SCP/AFT/Control Tower deployment, AWS compliance scan, automatic remediation, EventBridge integration or CodePipeline/SNS pipeline exists.
- Only V1/V2 profiles are implemented. Future reviewed profiles/scenarios use the same publication/catalogue contract. Bounded catalogue/history limits, administrator trust, cost/retention/alerting and real-account integration remain POC limitations.
