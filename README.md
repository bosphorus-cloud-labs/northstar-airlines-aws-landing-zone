# NorthStar Airlines AWS Landing Zone Governance

A governance proof of concept for an Emirates Senior Technical Engineer – Public Cloud interview. It combines a documented enterprise landing-zone model with a single-account governance dashboard and clearly labeled multi-account simulation.

**Current status:** Version 1 is AWS-hosted, as confirmed by the project owner; Phase 5 does not inspect or change that deployment. Phases 1–4A provide the local application and deployment foundation. Phase 5 adds an isolated offline CLI for a Version 2 policy proposal, simulated approval, canary rollout, failure/retry and account onboarding. A PR-only governance validation workflow is now defined in source; no production deployment or automatic publication path is introduced.

## Objectives

Demonstrate enterprise account governance, reusable Terraform design, controlled delivery, and operational visibility across existing and newly provisioned accounts. The planned application will show account inventory, compliance evidence, deployment history, failures, and governance exceptions. The design covers drift, recovery, expiring exceptions, and staged fleet updates.

## Architecture and scope

| Layer | Planned single-account POC | Enterprise reference only |
| --- | --- | --- |
| User interface | React + TypeScript + Vite on Amplify Hosting | Organization-wide governance visibility |
| Identity and API | Cognito; API Gateway; Python 3.13 Lambda | Federated enterprise access and scoped integration roles |
| Data and events | DynamoDB; EventBridge; synthetic account/finding fixtures | Inventory and evidence from authorized account integrations |
| Infrastructure | Terraform for approved POC resources in Frankfurt (`eu-central-1`) | Organizations, Control Tower, Account Factory, AFT, central policies |
| Delivery | GitHub Actions validation and approval-gated deployment | Documented CodePipeline/CodeBuild/AFT integration |

Planned POC request flow: browser → Cognito authentication → API Gateway authorization → Lambda → DynamoDB. EventBridge will support asynchronous governance events and simulation updates. Browser code must never receive AWS deployment credentials or direct database access.

The POC uses one personal AWS account. Accounts shown in the simulated fleet do not represent real member accounts. Synthetic findings are demonstration data, never evidence that AWS controls were evaluated. Any later real observation must identify its source, timestamp, and account and remain distinguishable from simulation.

Control Tower Account Factory provisions/enrolls accounts; AFT orchestrates Terraform account provisioning and customizations; central Organizations pipelines own policy attachments; the application reads their reported outcomes. The application does not act as an account factory or Terraform deployment engine. See [architecture and responsibility boundaries](docs/ARCHITECTURE.md).

Organizations, Control Tower, AFT, Transit Gateway, Palo Alto firewalls, and enterprise landing-zone infrastructure will **not** be deployed for this POC.

## Repository layout

```text
frontend/                  React/TypeScript/Vite Governance Console
backend/                   Local FastAPI API, service, fixture repository, ASGI adapter
terraform/modules/         Reusable infrastructure modules
terraform/poc/             Single-account POC roots
terraform/enterprise/      Reference-only enterprise examples
governance/policies/       Versioned governance definitions
governance/environments/   Non-secret environment configuration
governance/simulation/     Offline policy-rollout CLI, scenario and run contract
mock-data/                 Synthetic fixtures with explicit provenance
tests/                     Cross-component and acceptance tests
docs/                      Architecture, milestones, and operating guidance
.github/workflows/         Governance PR validation only; no cloud deployment
```

Empty directories contain `.gitkeep` placeholders so Git preserves the structure.

## Local development

Read [AGENTS.md](AGENTS.md) before making changes. The implementation sequence and acceptance criteria are in the [implementation plan](docs/IMPLEMENTATION_PLAN.md).

The local toolchain is Node.js 24 (tested 24.19.0) and Python 3.13 with an isolated virtual environment. Terraform is constrained to >=1.14,<2 (tested 1.14.6), with AWS provider 6.71.0 locked for the isolated POC root. The offline model uses Python 3.13 and pinned dependencies in `requirements-dev.txt`; see the commands below. The local API uses the same Python environment; commands follow below.

Local development will default to deterministic mock data without AWS credentials or live AWS API calls. The API currently reads local fixtures; no DynamoDB or event runtime is required. Keep secrets in ignored local files; commit only sanitized configuration examples. Commit Terraform provider lockfiles, but never state, saved plans, or sensitive variable files.

Offline governance model (no AWS access):

```sh
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m governance.model.evaluate --at 2026-10-31T12:00:00Z
```

See [data contracts and policy semantics](docs/GOVERNANCE_MODEL.md) for validation rules, simulation limits, environment differences, and the expected ten-account summary. At the reference timestamp, 50 control evaluations produce 31 compliant, 3 noncompliant, 6 unknown, and 10 stale results. Approved exceptions never convert failures into passes. JSON policy definitions are offline intent, not deployed SCPs.

Local API (explicit demo identity bypass; trusted workstation only):

```sh
.venv/bin/python -m backend --local-demo
```

The launcher binds `127.0.0.1:8000`. Open [Swagger UI](http://127.0.0.1:8000/docs) or request [fleet summary](http://127.0.0.1:8000/api/v1/summary). Without `--local-demo`, all routes are denied by default. Demo mode rejects bearer tokens and non-loopback clients; it is not production authentication and must not be exposed publicly. The console uses an explicitly scoped loopback-only Vite proxy for local development. The Lambda adapter stays fail-closed unless all deployment settings and a verified gateway identity are present; no local-demo flag can enable it. See [backend API guide](docs/BACKEND_API.md) for routes, response examples, authentication boundaries, pagination, timestamps, and limitations.

In a second terminal from the repository root, run the frontend while the API continues running:

```sh
cd frontend
npm ci
npm run dev
```

Open [NorthStar Governance Console](http://127.0.0.1:5173). The fixed reference time is visible on every page. No fallback mock data is used if the backend is unavailable. See the [frontend guide](docs/FRONTEND.md) for architecture, generated contracts, page behavior, tests, preview, and limitations.

Frontend checks (from `frontend/`):

```sh
npm run api:check
npm run typecheck
npm run lint
npm run format:check
npm test
npm run build
```

Repository checks (from the repository root):

```sh
.venv/bin/ruff check backend governance tests
.venv/bin/ruff format --check backend governance tests
git diff --check
git status --short --branch
```

## Five-minute interview demonstration

Version-aware source integration is ready locally; the hosted V1 application remains unchanged. From the repository root, after the documented Python/Node/Terraform prerequisites are installed:

```sh
./demo.sh v2
```

The launcher performs real provider-free Terraform checks/planning, then simulated approval, canary, failure/retry and onboarding. For the five-minute before/after story, start `./demo.sh v1` before the interview; then run `./demo.sh v2` once in another Terminal and refresh the same browser once. Owned servers are reused. It starts loopback-only servers; open `http://127.0.0.1:5173` to see **CURRENT governance** automatically. Use **Historical snapshot** only for comparison. V2 has eleven accounts and 66 findings: 43 compliant, 4 noncompliant, 9 unknown and 10 stale. The browser and API remain read-only. `./demo.sh reset` returns the local current marker to baseline policy 1.0.0 while keeping policy 2.0.0 readable in History; `--prepare-only` generates artifacts without starting servers.

See the [five-minute screen-by-screen runbook and safe AWS publication prerequisites](docs/INTERVIEW_DEMO.md). All publication packages stay local. Separate authorization is required to publish a distinct DynamoDB snapshot, extend the reader allowlist, and deploy the updated application. The [advanced Phase 5 CLI/Terraform walkthrough](docs/POLICY_ROLLOUT_DEMO.md) remains available. Future versions require reviewed policy/profile/scenario registration; no V3 results are invented.

## Secure deployment foundation

See [Phase 4A deployment guide](docs/AWS_DEPLOYMENT_FOUNDATION.md) for Terraform module boundaries, Cognito/PKCE and IAM trust, DynamoDB snapshot loading, Linux ARM64 packaging, public frontend settings, state bootstrap, costs, repository integration and teardown. Offline seed preparation is `.venv/bin/python -m scripts.seed_governance`; it never connects to AWS by default.

Development remains `npm run dev` with the loopback API. Production builds require the public Cognito/API configuration exported by Terraform and do not use the local proxy. Without that configuration, the compiled bundle shows a configuration-required screen and makes no API calls.

No AWS credentials, account discovery, remote state initialization, normal Terraform plans, apply/destroy, seeding execution, or hosting deployment is authorized by Phase 4A. The only Terraform test plan uses a mock provider.

## Security and delivery model

The governance CI workflow runs Python checks, provider-free Terraform validation/planning, parity checks and synthetic rollout reporting on relevant pull requests. Hosted execution is pending an authorized push/PR; it has no AWS deployment permissions. See [the short CI/CD interview runbook and integration audit](docs/CI_CD_DEMO.md). Additional security scanning and production delivery remain future work. GitHub OIDC and least-privilege roles will replace static AWS access keys. Cloud changes require explicit authorization and a protected approval gate; enterprise reference paths must be excluded from POC deployments.

Do not access AWS credentials, create cloud resources, run Terraform apply/destroy, or push changes without explicit authorization. No such actions are needed for local foundation work.

Designs will address the AWS Well-Architected pillars: operational excellence through audit trails and runbooks; security through scoped access; reliability through idempotency and recovery; performance efficiency through bounded queries; cost optimization through budgets and retention; sustainability through appropriately sized, on-demand services. These are design goals, not claims of a completed review.
