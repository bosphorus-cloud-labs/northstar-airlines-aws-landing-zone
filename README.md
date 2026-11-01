# NorthStar Airlines AWS Landing Zone Governance

An Emirates Senior Technical Engineer – Public Cloud case study: a real, authenticated AWS governance console in one Frankfurt account, displaying explicitly synthetic multi-account governance evidence.

**Deployment status:** The end-to-end GitHub OIDC delivery path is live. V2 is Current at generation 4 after approved V1 rollback and V2 restoration; immutable V1 remains in History. Main-only Amplify frontend auto-build is configured separately from protected data publication. See [deployment evidence](docs/DEPLOYMENT_ACCEPTANCE.md).

[Open the authenticated governance console](https://main.d1eetlse86595h.amplifyapp.com/). Use the invited Cognito reader account. Access tokens stay in memory; after reload or expiry, sign in again through Cognito SSO. Never share passwords/tokens in repository files or interview recordings.

## What the case study demonstrates

- Central versioned policy with inherited baseline and Production, Pre-Production, Testing and Development requirements.
- Real reusable, provider-free Terraform validation/planning and full parity with the Python rollout model.
- Simulated validation/approval, Development canary, failure/retry, controlled waves and account onboarding.
- Real GitHub PR/CI, protected manual approval, short-lived AWS OIDC identity, conditional DynamoDB publication and verified Current promotion.
- One read-only application showing inventory, compliance, deployment outcomes, configuration drift and expiring exceptions; immutable History and approved selection rollback.

The dashboard displays synthetic evidence, not real AWS account compliance. V1 has ten accounts and 50 findings (31 compliant, 3 noncompliant, 6 unknown, 10 stale). V2 adds audit-log integrity validation and an eleventh account, producing 66 findings (43 compliant, 4 noncompliant, 9 unknown, 10 stale). Successful simulated distribution never implies universal compliance.

## Architecture and ownership

```text
Git feature branch → PR → unprivileged GitHub Actions CI → merge to protected main
  → manual CD + actual governance-production approval → short-lived OIDC publisher
  → conditional immutable DynamoDB rows + manifest → strong digest verification
  → atomic generation-checked Current/History catalogue
  → read-only Lambda + API Gateway JWT ← Cognito-authenticated React on Amplify
```

Terraform provisions the POC infrastructure separately; data CD cannot run Terraform or deploy application code. Amplify builds frontend source from GitHub; a policy snapshot promotion requires no frontend rebuild. Browser and Lambda cannot write DynamoDB. Local demo identity cannot be enabled in deployed Lambda.

Control Tower Account Factory provisions/enrolls accounts. AFT handles account requests/customizations. Central Organizations pipelines own SCPs and attachments. A proposed network/inspection account would handle Transit Gateway routing and resilient inspection appliances; security/log archive accounts would receive authorized audit evidence. This application reads reported governance outcomes. **Control Tower, Organizations, AFT, Transit Gateway, Palo Alto and enterprise infrastructure are reference architecture only. EventBridge processing and CodePipeline/CodeBuild/SNS integration are not deployed.** See [architecture](docs/ARCHITECTURE.md).

V1/V2 are simplified **whole-governance snapshot labels** for this POC, not application releases or a production policy-versioning scheme. Each snapshot freezes policy/environment intent, inventory, evidence and evaluation context; findings are derived by the evaluator. In production, individual policies would have independent revisions, owners, scope, approval history and account-specific deployment records. AWS Config/Security Hub evidence collection and real multi-account enforcement are future integrations, not deployed capabilities.

## Five-minute interview

Follow [the screen-by-screen interview runbook](docs/INTERVIEW_DEMO.md). Prepare completed CI/CD links in advance; never wait for CI or approve cloud changes during the five-minute presentation. Show live Current/History, rollout failures/retry, account-specific findings and onboarding. [CI/CD commands and integration audit](docs/CI_CD_DEMO.md) explain the real delivery path and enterprise approval model.

The offline fallback is independent of live AWS:

```sh
./demo.sh v1       # Prepare before presenting; loopback servers only.
./demo.sh v2       # One interview command, then refresh the local browser.
./demo.sh reset    # Local Current → V1; retain historical artifacts.
```

Open http://127.0.0.1:5173. The launcher performs real provider-free Terraform checks, then simulated operations. It never publishes DynamoDB records or changes the hosted console. Future policy profiles require reviewed contract/scenario registration; V3 results are not invented.

## Local development and validation

Python 3.13, Node.js 24 (tested 24.19.0), Terraform >=1.14,<2 (tested 1.14.6), and locked AWS provider 6.71.0:

```sh
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m backend --local-demo
```

In another terminal:

```sh
cd frontend
npm ci
npm run dev
```

FastAPI binds 127.0.0.1:8000; [Swagger](http://127.0.0.1:8000/docs) is available only in authorized local-demo mode. Vite's loopback proxy is for local development; Amplify uses the explicit Terraform-exported API/Cognito settings. Without local-demo or verified deployed identity, access is denied.

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/ruff check backend governance scripts tests terraform/poc/tests/*.py
.venv/bin/ruff format --check backend governance scripts tests terraform/poc/tests/*.py
terraform fmt -check -recursive terraform
# From frontend/:
npm run api:check
npm run typecheck
npm run lint
npm run format:check
npm test
npm run build
```

See [data contracts](docs/GOVERNANCE_MODEL.md), [backend API](docs/BACKEND_API.md), [frontend](docs/FRONTEND.md), [delivery operations](docs/GOVERNANCE_DELIVERY.md), [deployment foundation](docs/AWS_DEPLOYMENT_FOUNDATION.md) and [implementation milestones](docs/IMPLEMENTATION_PLAN.md).

## Repository and security boundaries

`frontend/` and `backend/` implement the read-only console; `governance/` owns contracts, environment intent, evaluation and simulation; `mock-data/` is synthetic. `terraform/simulation/` consumes the shared pure module. `terraform/poc/` manages only the single-account POC; `terraform/enterprise/` remains reference-only. `.github/workflows/` separates credential-free CI and protected data CD.

This public single-owner POC explicitly permits the owner to approve their own environment deployment, with administrator bypass disabled, strict required CI and main-only deployment. No independent PR approval is claimed. The default independent-review gate remains available for enterprise use. OIDC trust pins immutable owner/repository IDs and the exact protected environment; no permanent AWS keys are stored in GitHub.

See [security boundaries, reporting and audit commands](SECURITY.md). Never commit credentials, sensitive tfvars, state, saved plans, local settings, ZIPs or generated builds. Cloud writes, infrastructure changes and teardown require explicit authorization and scope inspection. POC and enterprise deployments must never share execution roles/state. Conditional publication is application-enforced immutability, not WORM storage; trusted administrators remain a security boundary. Retention budgets, alerts, real account integrations and operational hardening beyond this bounded POC remain explicit limitations.
