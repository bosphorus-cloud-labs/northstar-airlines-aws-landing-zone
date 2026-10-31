# Implementation plan

Status: Phases 0–4A implement the foundation, model, application and deployment source; see `GOVERNANCE_MODEL.md`, `BACKEND_API.md`, `FRONTEND.md` and `AWS_DEPLOYMENT_FOUNDATION.md`. The owner confirms the V1 dashboard is AWS-hosted. Phase 5 now implements the offline policy lifecycle CLI; see `POLICY_ROLLOUT_DEMO.md`. It leaves that deployment and its data untouched. Cloud changes and future integration require separate explicit authorization. This plan does not authorize credential access, Terraform apply/destroy, commits or pushes. All deployable resources target one personal account in `eu-central-1`; enterprise infrastructure remains reference-only.

| Phase | Deliverable | Acceptance criteria |
| --- | --- | --- |
| 0 — Foundation | Conventions, architecture, structure, ignore rules, plan | Requested paths preserved in Git; ownership and simulation boundaries documented; whitespace and ignore checks pass; no application, resources, or executable workflows |
| 1 — Contracts and fixtures (implemented) | Versioned inventory/OU, policy/environment, evidence/finding, deployment, drift, exception, event contracts; four environments; ten synthetic accounts; deterministic Python evaluator and tests | Simulation provenance, stable IDs, timestamps, revisions, pass/fail/unknown/stale semantics; schema checks; no real account or credential data |
| 2 — Local backend (implemented) | Python 3.13 FastAPI/Pydantic read API; service/repository layers; fixture adapter; Mangum compatibility | Eight endpoints; bounded paging/filters; explicit fixed/parameterized evaluation time; Phase 1 parity; default-deny/demo-only access; safe errors; local commands and tests; no AWS access. Event handlers and persistent storage remain deferred. |
| 3 — Local frontend (implemented) | API-backed React/TypeScript/Vite dashboard; generated contracts; local proxy | Inventory, compliance, deployment history, failures, exceptions; visible simulation labels; accessible loading/empty/error states; type/lint/build and frontend tests; visible reference time; no browser credentials or deployment authority |
| 4A — Secure deployment foundation (source implemented) | Five POC Terraform modules/root, Cognito PKCE and gateway permissions, DynamoDB adapter, packaging/seed/config tools | Pinned CLI/providers, lockfiles, documented inputs/outputs; least privilege, encryption, retention, cost controls; format/validate/security checks; offline schema/mock tests, authentication/packaging/loader tests; no AWS calls, normal plan, remote state or unauthorized apply |
| 5 — Policy lifecycle CLI (implemented offline) | V2 security requirement, provider-free Terraform desired plans/parity, validation/approval, canary, controlled fleet rollout, failure/resume and new-account onboarding | Default V1 contracts/results preserved; explicit simulated provenance; approval bound to proposal digest; stop on deployment/canary failure; inactive targets deferred; deterministic JSON exports and tests; no live publication or dashboard changes. See `POLICY_ROLLOUT_DEMO.md`. |
| Future controlled delivery | GitHub Actions validation and deployment workflow | Secret/policy scans; enterprise paths excluded from deployment; scoped OIDC; protected approval gate; revision-bound plan; state concurrency controls; no unauthorized push/cloud execution |
| 6 — Authorized deployment | Single-account deployment and smoke verification | Explicit authorization before credential access/resources/apply; reviewed plan; authenticated and denied-access checks; real resources listed separately from simulated fleet; cost and teardown guidance |
| 7 — Governance lifecycle integration (future) | Read-only dashboard consumption of reviewed simulation snapshots; event handling | Phase 5 exports adapted behind explicit versioned contracts and reviewed publication; default V1 remains available; stale/unknown evidence; durable concurrency/idempotency and event replay require a separate design; exception expiry preserves findings; simulated labels persist |
| 8 — Enterprise reference and interview readiness | Reference examples, diagrams, runbooks, CodePipeline/CodeBuild/AFT guide | Central/account customization ownership explicit; no shared resource ownership; no enterprise deployment path; reproducible demo; architecture tradeoffs and Well-Architected review documented |

## Validation strategy

Start with deterministic offline checks. Add schema checks with fixtures, Python and TypeScript checks with application code, Terraform validation with modules, and workflow/security checks with CI. Do not add executable placeholder workflows suggesting validation already exists. Test authorization, provenance, pagination, event ordering/idempotency, expired exceptions, and recovery.

Once deployment is explicitly authorized, review a concrete plan before apply and verify only approved resources. Real evidence must come from authorized integrations and record provenance and freshness. Synthetic scenarios do not certify actual compliance.

## Operational acceptance

Before a deployed demonstration is complete, document ownership, alarms, redacted logging, retention, budgets, replay, rollback/roll-forward, state recovery, and teardown. Verify that the application cannot invoke deployment or change Organizations policies. Record validation results and limitations for a reproducible interview demonstration.

## Decisions to resolve

Phase 1 fixes the fleet at ten accounts (3 Production, 2 Pre-Production, 2 Testing, 3 Development), five representative controls, Python 3.13, and read-only exception evaluation. Confirm personas, future exception mutation scope, cost/retention limits, Terraform versions, and demo narrative before dependent phases. Defer account identifiers and credential-backed checks until authorized.
