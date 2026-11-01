# Implementation plan and current milestones

All deployable infrastructure is confined to the existing personal-account POC in eu-central-1. This document does not authorize future changes. See [actual deployment evidence](DEPLOYMENT_ACCEPTANCE.md); local/mock validation alone is never proof of AWS deployment.

| Milestone | Implemented / acceptance |
| --- | --- |
| Repository foundation | Structure, architecture/security boundaries and ignored local/artifact files. |
| Governance model | Versioned contracts, four environment policies, ten-account V1 fixture, deterministic evaluator, unknown/stale/exception semantics. |
| Backend | Eight protected GET routes, validated filters/pagination, services/repository interfaces, Lambda/Mangum adapter; local identity explicitly loopback-only. |
| Frontend | Six responsive read-only pages, typed API contracts, Current/History, account details, evidence/drift separation, Cognito PKCE and simulation disclosure. |
| AWS foundation | Existing Amplify, Cognito, HTTP API, Python 3.13 ARM64 Lambda and DynamoDB deployed; scoped IAM/logging/encryption; no enterprise resources. |
| Policy lifecycle | Shared provider-free Terraform desired configuration/parity; deterministic synthetic V2 approval/canary/failure/retry/onboarding; local one-command fallback. |
| CI / protected data CD | Real PR/main CI; actual environment approval and short-lived immutable-subject OIDC; conditional manifest-last publication and strong verification. |
| Current/History and recovery | Real V1 bootstrap, V2 publication, approved V1 rollback and V2 restoration verified. V2 is Current at generation 4; existing Amplify main auto-build is enabled separately. |
| Enterprise reference | Account Factory, AFT, central Organizations ownership and CodePipeline/CodeBuild/manual approval/SNS design documented, not deployed. |

## Acceptance and tests

132 Python tests, 48 frontend tests, 29 Terraform mock plan tests, provider-free real planning/parity, formatting/lint/contracts/build checks and hosted CI pass. Cloud checks independently verify actual OIDC publication, immutable snapshot digests, generation history, Cognito-authenticated pages, denied access, read-only runtime and recovery. Negative live-catalogue tests explicitly block writes; network/partial-write fault injection remains offline. See [evidence and limits](DEPLOYMENT_ACCEPTANCE.md).

## Remaining POC limitations

Only V1/V2 profiles are implemented; future versions require reviewed profile/scenario/contract registration. No enterprise resource provisioning, real fleet compliance collection, event consumer, exception mutation, remediation or CodePipeline/SNS resources are deployed. Single-owner approval is explicit and does not provide enterprise separation of duties. Dedicated budgets/alerting, broader scale/read models, retention/history limits and teardown/state-recovery rehearsal require further reviewed work. Browser and Lambda must remain read-only.
