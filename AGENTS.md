# Engineering instructions

## Purpose and scope

Build NorthStar Airlines AWS Landing Zone Governance, an interview proof of concept for an Emirates Senior Technical Engineer – Public Cloud role. Prioritize correctness, least privilege, modularity, maintainability, and AWS Well-Architected principles. NorthStar is a demonstration scenario, not an Emirates production system.

The deployable POC targets one personal AWS account in `eu-central-1`. Enterprise multi-account infrastructure is reference material only. Simulated accounts and findings must always carry explicit simulation provenance. Never present generated data as measured AWS compliance.

## Architecture and ownership

- Frontend: React, TypeScript, Vite; planned AWS Amplify Hosting.
- Backend: Python 3.13 Lambda behind API Gateway; DynamoDB storage; Cognito authentication; EventBridge asynchronous processing.
- Infrastructure: reusable Terraform modules, an isolated POC root, and enterprise reference examples. Keep POC-compatible modules separate from enterprise-only modules; POC roots must not import enterprise resources.
- CI/CD: GitHub Actions for POC validation and approved deployment; document CodePipeline, CodeBuild, and AFT integration for enterprise adoption.
- Control Tower Account Factory provisions and enrolls accounts into a landing zone baseline.
- Account Factory for Terraform (AFT) provides a Terraform-based account provisioning workflow and account customizations. It is not the owner of centrally managed Organizations policies.
- AWS Organizations centrally owns OU/account policy attachments, including SCPs. SCPs constrain permissions; they do not grant permissions or prove workload compliance.
- The Governance Application is read-focused: inventory, evidence, deployment history, failures, and exception visibility. It must not directly provision accounts, attach policies, or execute Terraform. See `docs/ARCHITECTURE.md` for boundaries.

## Repository conventions

- `frontend/`: local React/TypeScript/Vite console, generated API types, and test-only API response fixtures; `backend/`: local FastAPI routes, typed transport models, services, replaceable repository, authorization, and fail-closed Mangum adapter.
- `terraform/modules/`: narrowly scoped modules with documented inputs, outputs, dependencies, and ownership.
- `terraform/poc/`: single-account deployable roots; `terraform/enterprise/`: clearly labeled reference-only examples with separate state and credentials.
- `governance/policies/`: versioned policy definitions; `governance/environments/`: non-secret environment configuration.
- `governance/contracts/` and `governance/model/`: versioned JSON Schema contracts and offline Python validation/evaluation.
- `mock-data/`: deterministic synthetic fixtures; `tests/`: cross-component tests; `docs/`: architecture, decisions, and operations; `.github/workflows/`: automation.
- Use descriptive names, small cohesive changes, explicit interfaces, and typed TypeScript/Python boundaries. Validate all input at trust boundaries.
- Keep environment-specific values out of reusable modules. Use tags and consistent naming for ownership, environment, and cost attribution.
- Pin supported tools/providers/dependencies when introduced, commit dependency lockfiles (including `.terraform.lock.hcl`), and document update procedures.
- Add meaningful tests for authorization, validation, provenance, policy behavior, and failure paths. Run relevant formatting, linting, tests, and security checks for each change. Do not claim checks that were not run.
- Keep documentation aligned with implemented behavior. Clearly mark planned, simulated, and deployed capabilities.

## Security requirements

- Never commit credentials, tokens, private keys, Terraform state/plan output, or sensitive logs. Use synthetic data only in fixtures.
- Do not read AWS credential files or query credential stores without explicit user authorization. Use placeholders for account IDs and configuration in documentation.
- Prefer GitHub OIDC with tightly scoped role trust and permissions over long-lived AWS keys when deployment is authorized.
- Enforce authentication and server-side authorization; validate Cognito tokens at the API boundary. Do not rely on browser controls for access enforcement.
- Apply least-privilege IAM, encryption in transit and at rest, safe error responses, structured redacted logs, retention limits, and auditability.
- Keep real observations distinct from simulations, including account provenance, source, observed time, and evaluation status. Missing or stale evidence is unknown, not compliant.
- Treat event handlers as retryable: design for idempotency, bounded retries, dead-letter handling, and correlation IDs.
- Exceptions require scope, rationale, owner, approver, expiry, and audit history; they must not silently erase findings.

## Deployment restrictions

- Do not access AWS credentials, create cloud resources, run `terraform apply` or `terraform destroy`, or push changes without explicit user authorization for the relevant action.
- Do not deploy Organizations, Control Tower, AFT, Transit Gateway, Palo Alto firewalls, or enterprise landing-zone infrastructure. These remain reference-only even if POC deployment is authorized.
- Do not run commands that contact AWS, initialize a remote backend, or refresh real infrastructure as part of routine local validation. Use offline checks where possible and report tool limitations.
- Enterprise examples must never be included in the POC deployment path. Keep state, IAM roles, environment approvals, and workflows separate.
- Future deployment workflows must validate first, show a reviewable plan, require an approval gate, and apply the approved plan with scoped credentials. Production-like changes need a recovery procedure.
- Phase 1 implements only the offline governance model, versioned JSON contracts/environment policies, synthetic fixtures, and tests. No frontend, Lambda/API Gateway, Terraform resources, cloud deployment, or executable workflows are authorized by that phase.

## Phase 2 backend conventions

- Keep policy logic in `governance.model`; API layers must reuse it. Use explicit/fixed evaluation time, never a wall-clock default.
- Default authentication denies access. Local-demo identity bypass requires explicit opt-in, loopback peer/Host restrictions, and must never be used by the Lambda entry point. No fake JWT validation.
- Keep the API read-only and errors sanitized; bound paging/filter inputs and retain simulation provenance. No Lambda/API Gateway resources, frontend, or deployment workflows are authorized by Phase 2. Commit and push only when explicitly authorized by the current user task.

## Phase 3 console conventions

- Treat FastAPI as the only runtime source of governance data. Never duplicate policy evaluation or import test fixtures into production code.
- Regenerate TypeScript API types and test responses with `npm run api:generate`; verify contract drift with `npm run api:check`.
- Keep simulation provenance and the fixed reference time visible. Unknown/stale evidence and underlying violations remain explicit even when exceptions exist.
- Bind Vite to loopback and proxy only the fixed local API target. The Vite proxy is authorized for local-demo integration only; never expose it publicly or treat it as production authentication.
- Preserve accessible focus, labeled controls, responsive tables, and loading/error/empty states. Run type checking, lint, frontend tests/build, and the existing Python suite.
- Phase 3 does not authorize cloud access, Amplify deployment, or Terraform/workflows. Commit and push only when explicitly authorized by the current user task.

## Phase 4A deployment foundation

- Implement deployment source only. No AWS credentials, AWS endpoints, account discovery, remote state initialization, normal plans/refresh, apply/destroy, data insertion, commits or pushes are authorized by this phase.
- Terraform formatting/validate, `init -backend=false` public registry downloads and mock-provider tests with `command=plan` are permitted offline checks. Never add apply runs or AWS data sources to those tests.
- Keep AWS adapters lazy: imports/default tests must not create SDK clients. Inject fake clients in tests. The local CLI and default ASGI application retain their existing authentication restrictions.
- Deployed identity comes only from the configured gateway's verified authorizer context plus read scope/group checks. IAM invocation isolation is part of that trust boundary. No direct invoke or function URL for untrusted principals.
- Production SPA builds require Cognito/API public settings and may not enable local-demo mode. No secrets belong in VITE variables or Terraform source/state.
- DynamoDB reads pin a content-addressed immutable synthetic snapshot. Only the separately authorized loader can conditionally write it; manifest publication is last and retries never overwrite conflicts.
- Build Lambda ZIPs offline from pinned Linux ARM64 Python 3.13 dependencies. Keep artifacts, generated environments, plans and state ignored. Rebuild after source/dependency changes.

## Phase 5 offline simulation

- The existing hosted V1 dashboard must remain unchanged. No AWS credentials, cloud calls, Terraform operations, DynamoDB publication, frontend changes, commits or pushes are authorized by the initial Phase 5 task.
- The CLI writes only below ignored `artifacts/policy-rollout/`; it must not modify V1 fixtures, the pinned snapshot manifest, Terraform or deployment configuration.
- V2 contracts are an explicit opt-in profile. Default API/evaluator/loader behavior stays V1. Reuse policy evaluation rather than reproducing its rules in the CLI.
- Approval and rollout are explicitly simulated. Preserve desired/observed distinctions, baseline violations, exceptions, missing/stale evidence, failure stop conditions, inactive-account deferrals and deterministic timestamps. No automatic integration/publication path is permitted.
- The optional `terraform/simulation/` root is an authorized exception for real offline fmt, init with `-backend=false`, validate, plan and show only. Keep it provider/resource/data-source-free; import only `simulated_governance`, never POC/enterprise modules. Save plans/JSON only under ignored artifacts and verify the full desired output against the frozen CLI proposal. No apply, AWS access, deployment or compliance measurement is authorized.

## Interview simplification source scope

- The reviewed local launcher, read-only API/catalogue and React version selector may be implemented in source. This overrides the earlier Phase 5 source-only frontend restriction, not the prohibition on changing the deployed environment.
- No AWS credentials/APIs, publication, Terraform apply/destroy, commits or pushes are authorized. Keep the POC Terraform/IAM and Cognito/authentication configuration unchanged.
- V1 remains the default and its snapshot digest/response semantics remain compatible. Select only server-registered versions; validate full snapshot/profile/digest/timestamps and fail closed without cross-version fallback.
- Launch only loopback local-demo servers with explicit opt-in; Lambda never uses local files/demo identity. Publication preparation has no cloud execution path. Preserve immutable history during replay/reset.

## Minimal governance CI

- PR/manual governance validation is authorized in source. Use only the existing provider-free Terraform root/module and synthetic CLI; guard out cloud-capable blocks before init/plan.
- Keep workflow contents permission read-only, action revisions immutable and checkout credentials unpersisted. Never use pull_request_target, AWS secrets/OIDC, apply/destroy, push-triggered production delivery or automatic publication.
- CI approval/distribution/evidence are explicitly simulated. Upload only allowlisted synthetic text/JSON review reports, not state, saved executable plans or publication packages.
- Local and hosted CI results must be labeled accurately. The workflow does not promote local Current or update the AWS-hosted console. No commit, push, PR creation, merge or cloud change is authorized by the CI implementation task.
