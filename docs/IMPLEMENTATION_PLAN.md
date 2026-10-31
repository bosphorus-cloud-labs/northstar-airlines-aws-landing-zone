# Implementation plan

Status: phase 0 complete; phase 1 offline contracts, environment policies, synthetic fleet, evaluator, and tests implemented. See `GOVERNANCE_MODEL.md` for commands and acceptance scenarios. Phase 2 and later require separate tasks. This plan does not authorize credential access, cloud changes, Terraform apply/destroy, or pushes. All deployable resources target one personal account in `eu-central-1`; enterprise infrastructure remains reference-only.

| Phase | Deliverable | Acceptance criteria |
| --- | --- | --- |
| 0 — Foundation | Conventions, architecture, structure, ignore rules, plan | Requested paths preserved in Git; ownership and simulation boundaries documented; whitespace and ignore checks pass; no application, resources, or executable workflows |
| 1 — Contracts and fixtures (implemented) | Versioned inventory/OU, policy/environment, evidence/finding, deployment, drift, exception, event contracts; four environments; ten synthetic accounts; deterministic Python evaluator and tests | Simulation provenance, stable IDs, timestamps, revisions, pass/fail/unknown/stale semantics; schema checks; no real account or credential data |
| 2 — Local backend | Python 3.13 API and event handlers with local persistence | Documented startup; paginated/filterable reads; validation and authorization tests; idempotency/failure tests; mock mode requires no AWS access |
| 3 — Local frontend | React/TypeScript/Vite dashboard | Inventory, compliance, deployment history, failures, exceptions; visible simulation labels; accessible loading/empty/error states; type/lint/build checks |
| 4 — POC Terraform | Reusable modules and isolated single-account root | Pinned CLI/providers, lockfiles, documented inputs/outputs; least privilege, encryption, retention, cost controls; format/validate/security checks; no unauthorized apply |
| 5 — Controlled delivery | GitHub Actions validation and deployment workflow | Secret/policy scans; enterprise paths excluded from deployment; scoped OIDC; protected approval gate; revision-bound plan; state concurrency controls; no unauthorized push/cloud execution |
| 6 — Authorized deployment | Single-account deployment and smoke verification | Explicit authorization before credential access/resources/apply; reviewed plan; authenticated and denied-access checks; real resources listed separately from simulated fleet; cost and teardown guidance |
| 7 — Governance lifecycle demo | Simulated onboarding, fleet updates, drift, failure recovery, exceptions | Existing/new simulated accounts; canary rollout and stop conditions; stale/unknown evidence; duplicate events safe; audited replay; exception expiry preserves findings; simulated run labels persist |
| 8 — Enterprise reference and interview readiness | Reference examples, diagrams, runbooks, CodePipeline/CodeBuild/AFT guide | Central/account customization ownership explicit; no shared resource ownership; no enterprise deployment path; reproducible demo; architecture tradeoffs and Well-Architected review documented |

## Validation strategy

Start with deterministic offline checks. Add schema checks with fixtures, Python and TypeScript checks with application code, Terraform validation with modules, and workflow/security checks with CI. Do not add executable placeholder workflows suggesting validation already exists. Test authorization, provenance, pagination, event ordering/idempotency, expired exceptions, and recovery.

Once deployment is explicitly authorized, review a concrete plan before apply and verify only approved resources. Real evidence must come from authorized integrations and record provenance and freshness. Synthetic scenarios do not certify actual compliance.

## Operational acceptance

Before a deployed demonstration is complete, document ownership, alarms, redacted logging, retention, budgets, replay, rollback/roll-forward, state recovery, and teardown. Verify that the application cannot invoke deployment or change Organizations policies. Record validation results and limitations for a reproducible interview demonstration.

## Decisions to resolve

Phase 1 fixes the fleet at ten accounts (3 Production, 2 Pre-Production, 2 Testing, 3 Development), five representative controls, Python 3.13, and read-only exception evaluation. Confirm personas, future exception mutation scope, cost/retention limits, Node.js/Terraform versions, and demo narrative before dependent phases. Defer account identifiers and credential-backed checks until authorized.
