# NorthStar Airlines AWS Landing Zone Governance

A governance proof of concept for an Emirates Senior Technical Engineer – Public Cloud interview. It combines a documented enterprise landing-zone model with a planned, single-account governance dashboard and clearly labeled multi-account simulation.

**Current status:** repository foundation only. No application, Terraform resources, workflows, or AWS infrastructure have been implemented or deployed by this foundation task.

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
frontend/                  Planned React application
backend/                   Planned Python API and event handlers
terraform/modules/         Reusable infrastructure modules
terraform/poc/             Single-account POC roots
terraform/enterprise/      Reference-only enterprise examples
governance/policies/       Versioned governance definitions
governance/environments/   Non-secret environment configuration
mock-data/                 Synthetic fixtures with explicit provenance
tests/                     Cross-component and acceptance tests
docs/                      Architecture, milestones, and operating guidance
.github/workflows/         Planned GitHub Actions automation
```

Empty directories contain `.gitkeep` placeholders so Git preserves the structure.

## Local development

Read [AGENTS.md](AGENTS.md) before making changes. The implementation sequence and acceptance criteria are in the [implementation plan](docs/IMPLEMENTATION_PLAN.md).

The planned toolchain is Node.js with a supported version selected when frontend scaffolding is added, Python 3.13 with an isolated virtual environment, and Terraform with pinned CLI/provider versions when modules are introduced. No installation or application startup command exists yet. Dependency manifests, lockfiles, local service configuration, and exact developer commands will arrive with the relevant implementation phase.

Local development will default to deterministic mock data without AWS credentials or live AWS API calls. Later phases will document mock API behavior and local DynamoDB/event substitutes where needed. Keep secrets in ignored local files; commit only sanitized configuration examples. Commit Terraform provider lockfiles, but never state, saved plans, or sensitive variable files.

Foundation checks:

```sh
git diff --check
git status --short --branch
```

## Security and delivery model

Future CI will run formatting, linting, tests, Terraform validation, policy/security checks, and secret scanning before deployment review. GitHub OIDC and least-privilege roles will replace static AWS access keys. Cloud changes require explicit authorization and a protected approval gate; enterprise reference paths must be excluded from POC deployments.

Do not access AWS credentials, create cloud resources, run Terraform apply/destroy, or push changes without explicit authorization. No such actions are needed for local foundation work.

Designs will address the AWS Well-Architected pillars: operational excellence through audit trails and runbooks; security through scoped access; reliability through idempotency and recovery; performance efficiency through bounded queries; cost optimization through budgets and retention; sustainability through appropriately sized, on-demand services. These are design goals, not claims of a completed review.
