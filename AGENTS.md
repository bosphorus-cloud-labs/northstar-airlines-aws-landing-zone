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

- `frontend/`, `backend/`: application code, added in later tasks.
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
