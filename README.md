# NorthStar Airlines AWS Landing Zone Governance

NorthStar Airlines provides a central view of AWS account governance, policy rollout outcomes and compliance evidence. The solution combines reusable Terraform configuration, deterministic policy evaluation and a read-only operations console, with a single-account deployment for validating the architecture and delivery controls.

The application runs in a single AWS account in **eu-central-1 (Frankfurt)**. Its fleet inventory, account customizations and compliance evidence are synthetic. Hosting, authentication, the API and storage use deployed AWS services. GitHub Actions publishes approved governance snapshots through a separate data-delivery workflow.

[Open the governance console](https://main.d1eetlse86595h.amplifyapp.com/). Access requires an invited Amazon Cognito user with governance-reader membership. See [resource-console acceptance](docs/RESOURCE_CONSOLE_ACCEPTANCE.md) for the current application checks and [catalogue deployment evidence](docs/DEPLOYMENT_ACCEPTANCE.md) for the preserved account-governance history.

## Architecture

```text
React / TypeScript on Amplify Hosting
    │ Cognito Authorization Code + PKCE
    ▼
API Gateway HTTP API — JWT authorizer and read scope
    ▼
Python 3.13 Lambda / FastAPI / Mangum — reader permission checks
    ▼
DynamoDB — immutable snapshots and Current/History catalogue
```

The API exposes account inventory, compliance findings, deployment history, configuration drift and governance exceptions. React consumes typed API responses; the Python governance engine evaluates the selected snapshot. Neither the browser nor Lambda can write governance records or execute deployments. CloudWatch retains API and Lambda logs with bounded retention.

The resource-compliance view shows each synthetic resource, its desired configuration, observed setting and reason for its result. Operators edit `mock-aws-resources/resources.json`; CI validates the data and real Terraform desired-state outputs before a protected publisher can update DynamoDB. A normal Git revert restores earlier resource configuration while preserving the publication audit history. The browser and Lambda remain read-only.

The deployed console opens on current resource compliance. The backwards-compatible catalogue mode remains available for recovery; its snapshots and API contracts are preserved. Protected publication, authenticated API rendering and the desired-versus-observed resource view have been verified live. See [resource compliance operations](docs/RESOURCE_COMPLIANCE_OPERATIONS.md) for activation, exact commands and the operational demonstration.

The repository separates two Terraform purposes:

- **`terraform/poc/`** manages the single-account application: Amplify, Cognito, API Gateway, Lambda, DynamoDB, IAM and logging, including the separate OIDC data-publisher role. Infrastructure changes require their own reviewed Terraform plan and authorization.
- **`terraform/simulation/`** uses the reusable, provider-free `simulated_governance` module to calculate desired account settings. Terraform planning does not provision accounts or distribute policies. A Python parity check verifies that the plan and rollout simulation use the same frozen proposal.

The proposed enterprise landing zone uses Organizations and Control Tower, separate security/log-archive accounts, environment OUs and a network/inspection account. Control Tower Account Factory provisions and enrolls accounts; AFT manages Terraform account requests and customizations; central Organizations pipelines own SCPs and attachments. The governance application reports their outcomes rather than owning those operations. Control Tower, Organizations, AFT, Transit Gateway and Palo Alto inspection are **reference architecture only**. See [architecture and ownership](docs/ARCHITECTURE.md).

## Governance model

Production, Pre-Production, Testing and Development inherit a common baseline and define environment-specific requirements. Preventive control intent, detective evidence checks and pipeline approvals are represented separately. These definitions are not deployed SCPs.

Evaluation distinguishes compliant, noncompliant, unknown and stale findings. Missing evidence is unknown, and approved or expired exceptions retain the underlying violation. Desired configuration, observed revisions, successful configuration distribution and compliance evidence are separate records: a successful simulated rollout does not make every account compliant.

The new resource fixture contains ten synthetic accounts and three controls, with passing, failing, missing and stale observations. Terraform calculates the central requirements for all four environments; Python verifies every planned assignment before evaluating evidence. No compliance totals are hardcoded in React.

The original account-governance catalogue and its immutable baseline remain available for compatibility and recovery. It includes the tested canary, failure/retry, onboarding and exception scenarios. Those simulated operations are distinct from real GitHub approval and DynamoDB publication.

## CI/CD

[Governance CI](.github/workflows/governance-ci.yml) runs on pull requests and pushes to `main`. It checks Python and frontend code, API contracts, source hygiene, Terraform formatting and validation, POC mock-provider plans, and provider-free governance planning. It also verifies Terraform-to-simulation parity and exercises simulated approval, canary, failure/retry and onboarding. Human-readable plans and synthetic reports are retained as review artifacts. CI has no AWS credentials or deployment authority.

[Governance data CD](.github/workflows/governance-cd.yml) adds a resource-publication path after successful main CI. It verifies the exact main commit, originating CI run, artifact content and protected PR process, then waits for the actual `governance-production` Environment approval. GitHub OIDC supplies short-lived credentials to the separate data-only publisher. Immutable insertion, manifest verification and conditional Current selection preserve historical data. Existing catalogue recovery dispatches remain available. The resource-publication path has passed hosted CI, actual Environment approval, DynamoDB read-back and authenticated console verification; execution links are recorded in the acceptance report.

Amplify builds the frontend from the protected GitHub `main` branch using [amplify.yml](amplify.yml). Main-only automatic builds are enabled; app-wide automatic builds and PR previews are disabled. These frontend releases are independent of governance-data publication: selecting or publishing a snapshot requires no frontend rebuild.

The deployed POC uses an explicit **single-owner approval model**. The owner may approve an environment deployment, administrator bypass is disabled, and required CI and main-only deployment restrictions remain enforced. This is not independent enterprise review. CodePipeline, CodeBuild, manual approval and SNS are documented enterprise integration points, not deployed components. See [delivery controls](docs/GOVERNANCE_DELIVERY.md) and [CI/CD operations](docs/CI_CD_OPERATIONS.md).

## Run locally

Requirements: Python 3.13, Node.js 24 and Terraform >=1.14,<2. The validated toolchain uses Node.js 24.19.0, Terraform 1.14.6 and AWS provider 6.71.0, pinned in the POC lockfile. Local application development and the provider-free simulation do not need AWS credentials.

From the repository root, install Python dependencies and start the API:

```sh
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m backend --local-demo
```

In a second terminal, also from the repository root:

```sh
npm --prefix frontend ci
VITE_GOVERNANCE_API_MODE=resources npm --prefix frontend run dev
```

Open [the local console](http://127.0.0.1:5173/) or [API documentation](http://127.0.0.1:8000/docs). Both servers bind to loopback. Explicit `--local-demo` mode grants a local read-only identity; it is unsuitable for shared or public hosts. The default API denies access, and deployed Lambda cannot enable this bypass. Amplify uses explicit API/Cognito configuration rather than the local Vite proxy.

## Validation

Run from the repository root after installing development dependencies:

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/ruff check backend governance compliance_engine deployment tests terraform/poc/tests/*.py
.venv/bin/ruff format --check backend governance compliance_engine deployment tests terraform/poc/tests/*.py
.venv/bin/python -m pip check
.venv/bin/python -m deployment.check_source_security
npm --prefix frontend run api:check
npm --prefix frontend run typecheck
npm --prefix frontend run lint
npm --prefix frontend run format:check
npm --prefix frontend test
npm --prefix frontend run build
```

In a clean checkout without live tfvars or a remote-backend cache, validate the POC configuration offline:

```sh
terraform fmt -check -recursive terraform
terraform -chdir=terraform/poc init -backend=false -input=false -lockfile=readonly
terraform -chdir=terraform/poc validate
mkdir -p artifacts/validation
.venv/bin/python -m zipfile -c artifacts/validation/mock-lambda.zip README.md
terraform -chdir=terraform/poc test \
  -var=lambda_package_path=../../artifacts/validation/mock-lambda.zip
```

The mock ZIP is deliberately nondeployable. Terraform tests use mock-provider plans and do not prove AWS deployment compatibility. A normal POC plan/refresh contacts AWS and is not an offline validation step. The [provider-free Terraform guide](terraform/simulation/README.md) contains the full planning and parity commands. [Local Demonstration](docs/LOCAL_DEMONSTRATION.md) describes the resource-change workflow and preserved `./demo.sh` rehearsal.

## Repository guide

| Path | Responsibility |
| --- | --- |
| `frontend/` | React console, Cognito sign-in and typed API client |
| `backend/` | Read-only REST API, service/repository layers and Lambda adapter |
| `compliance_engine/` | Shared deterministic policy and resource evaluation; no cloud operations |
| `compliance-rules/` | Human-readable central resource controls and environment-specific freshness |
| `mock-aws-resources/` | Editable synthetic accounts and resource observations |
| `governance/` | Existing contracts, environment requirements, rollout simulation and protected publication |
| `deployment/` | CI checks, Lambda packaging, configuration export and operator publication commands |
| `mock-data/` | Deterministic synthetic inventory and evidence |
| `terraform/modules/` | Reusable POC and provider-free governance modules |
| `terraform/poc/` | Isolated single-account infrastructure root |
| `terraform/simulation/` | Provider-free desired-configuration demonstration |
| `terraform/enterprise/` | Reference-only Control Tower/AFT account requests, customizations, SCP and networking examples |
| `.github/workflows/` | Credential-free CI and approved data publication |
| `tests/`, `docs/` | Regression tests, architecture and operating procedures |

See [requirements traceability](docs/REQUIREMENTS_TRACEABILITY.md), the [data model](docs/GOVERNANCE_MODEL.md), [API guide](docs/BACKEND_API.md), [frontend guide](docs/FRONTEND.md), [AWS operating guide](docs/AWS_DEPLOYMENT_FOUNDATION.md).

## Security and POC limits

Cognito Authorization Code + S256 PKCE, API Gateway JWT authorization and server-side reader permissions protect data access. Browser tokens remain in memory; reload or expiry requires sign-in through Cognito. Exact approved HTTPS origins are used for callbacks and CORS. The browser has no AWS credentials or direct DynamoDB access.

GitHub publisher trust pins immutable repository/owner IDs, the protected environment and STS audience. Runtime reads and publisher writes use separate IAM roles. State, saved plans, sensitive tfvars, tokens, ZIPs and generated builds stay outside source control. See [SECURITY.md](SECURITY.md) for reporting, audit commands and trust boundaries.

Snapshot immutability is enforced by conditional writes and integrity checks, not WORM storage; administrators and publisher code remain trusted. This bounded POC does not implement real AWS Config/Security Hub collection, multi-account enforcement, automated remediation, an EventBridge processor or an exception-mutation API. Fleet-scale reads, retention/recovery hardening, independent approvals, dedicated budgets and alerting require further production design. Infrastructure changes, data publication and teardown are separate authorized operations.
