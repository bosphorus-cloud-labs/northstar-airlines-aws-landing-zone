# Architecture and responsibility boundaries

Status: Phases 1–4A implement the model, read-only application and AWS deployment foundation. The project owner confirms the V1 dashboard is AWS-hosted; Phase 5 does not inspect or modify it. Phase 5 adds only the [offline policy lifecycle simulator](POLICY_ROLLOUT_DEMO.md). See [deployment foundation](AWS_DEPLOYMENT_FOUNDATION.md), [contracts and evaluation](GOVERNANCE_MODEL.md) and [local API](BACKEND_API.md).

## Scope and ownership

The deployable POC targets one personal account in `eu-central-1`. The fleet is synthetic. Enterprise examples are reference-only and excluded from the POC deployment path.

| Component | Responsibility | Boundary |
| --- | --- | --- |
| Control Tower Account Factory | Provision and enroll accounts into the landing-zone baseline | Does not own this dashboard or all custom governance definitions |
| Account Factory for Terraform (AFT) | Terraform-based account requests and account customization workflows | Uses Control Tower; does not replace central Organizations policy ownership |
| Central Organizations governance | Versioned organization policies, including SCPs, and OU/account attachments | SCPs constrain permissions; IAM grants them; policy presence alone does not establish compliance |
| Governance Application | Read-focused inventory, evidence, deployment history, failures, and exceptions | Cannot provision accounts, execute Terraform, or change Organizations policy attachments |

AFT requires an existing Control Tower landing zone. Its account customizations establish account baselines; application workload delivery uses a separate pipeline. Existing Control Tower-managed accounts require the supported AFT import/update process before AFT customization.

Central policy pipelines and account customization pipelines have separate resource ownership, state, and execution roles. Two states must never manage the same attachment or resource. Respect the supported lifecycle of Control Tower-managed resources.

## Implemented local console

React/TypeScript/Vite routes provide overview, inventory and details, compliance, deployments, drift, and exceptions. Generated OpenAPI types connect a read-only client to FastAPI via a loopback-only Vite proxy. Backend results are the sole runtime source; no frontend evaluator or fallback fixtures exist. TanStack Query handles loading, errors, cancellation, caching, and refresh. All data requests use the fixed reference timestamp and verify simulation provenance.

The proxy is deliberately restricted to a trusted local workstation: Vite and FastAPI bind to `127.0.0.1`, and Vite rewrites Host for the backend's demo guard. This is not production identity propagation. Future hosting requires Cognito authorization and reviewed API routing. No deployment authority or credentials are included in the browser. See [frontend implementation](FRONTEND.md) for contracts, paging, accessibility, tests, and snapshot limitations.

## Implemented local backend

FastAPI routes → GovernanceService → GovernanceRepository/FixtureRepository. The service reuses the Phase 1 evaluator; Pydantic validates transport models and domain records are checked against the existing JSON Schema. Data access returns request-owned snapshots and performs no AWS calls. Pagination/filtering is bounded and deterministic for the fixed dataset. Evaluation defaults to a fixed demo time, not wall-clock time.

The default authenticator denies every request. Explicit local-demo mode grants only a loopback demo reader and rejects tokens; the launcher disables forwarded-header trust and binds only `127.0.0.1`. Server-side permission checks cover health/docs as well as data. The Authenticator interface supports verified Cognito identities. Mangum uses the fail-closed deployment factory: required configuration selects the immutable DynamoDB adapter and verified-gateway authenticator; missing configuration denies all access. Phase 5 leaves this deployment path unchanged. Local demo identity must never be used for deployed authentication.

No API storage writes, exception mutations, event consumers, or infrastructure execution are implemented in the application. The deployment-only DynamoDB reader and explicitly gated operator loader remain unchanged; Phase 5 does not execute either against AWS.

## AWS deployment foundation (unchanged in Phase 5)

React on Amplify Hosting authenticates through Cognito. API Gateway enforces authorization before Python 3.13 Lambda reads DynamoDB. EventBridge-based asynchronous lifecycle handlers remain planned. Browser code receives no deployment credentials or direct database access. API, event processing, and deployment roles remain separate.

Start with read APIs. Any later exception submission or approval API needs a separately reviewed authorization and audit design. Display access does not imply mutation authority.

Every inventory/evidence record identifies simulation versus real observation, source, observation time, and stable identifiers. Compliance distinguishes evaluated pass/fail from unknown, stale, and not evaluated. Exceptions preserve underlying findings. Deployment history distinguishes simulated runs from actual workflow results and records revisions and correlation IDs.

## Account lifecycle and fleet operations

Phase 5 implements a local simulation of the lifecycle below. The CLI writes only ignored artifacts and explicitly opts into the `policy-v2` contract profile; default V1 validation, API contracts, fixture loading and pinned DynamoDB snapshot are unchanged. It separates V2 desired assignments from observed revisions, retains historical evidence/violations, stops on failed attempts, resumes pending targets and defers inactive accounts. Its approval journal is simulated, not an authenticated enterprise approval service. Nothing automatically publishes these artifacts to the application. See [the demo runbook](POLICY_ROLLOUT_DEMO.md).

The optional isolated `terraform/simulation/` root consumes that same frozen proposal and calls the pure `simulated_governance` module per existing account. Real Terraform plans calculate only desired outputs; a separate read-only Python verifier compares the entire output and proposal digest. No provider/resource/data source, apply or live integration exists in this root. Terraform planning and Python simulated deployment/compliance reporting are explicitly distinct.

Enterprise new-account flow: approved request → Account Factory/AFT provisioning → baseline/customizations → published events and evidence → application read model. Existing accounts require inventory, supported enrollment where appropriate, assessment, and reviewed customization rollout. Discovery does not imply compliance.

Fleet changes use versioned definitions, environment targeting, canary waves, bounded concurrency, approval gates, and stop conditions. Desired and observed revisions are tracked separately. Drift detection combines scheduled reconciliation with relevant events; missing evidence is unknown. Automated remediation requires a later explicitly authorized design.

Handlers must tolerate duplicate and out-of-order events, use idempotency keys and revisions, bound retries, route exhausted failures to a dead-letter destination, and support audited replay. Recovery uses reviewed rollback or roll-forward and state reconciliation. Policy rollback must account for changed access constraints.

Exceptions require scope, rationale, owner, approver, approval reference, expiry, and audit history. Expiry triggers reevaluation and escalation; exceptions never silently erase findings.

## Delivery and enterprise integration

GitHub Actions will validate application code, policies, Terraform, and security before a reviewable plan and protected deployment approval. Use scoped OIDC trust, revision-bound artifacts, and serialized deployments per state. Untrusted PRs must not receive deployment credentials.

POC and enterprise roots never share state or execution roles. Shared module storage is not shared execution scope: POC roots must reference only POC-compatible modules, never enterprise-only modules or resources. An authorized POC deployment needs an encrypted, access-controlled state backend with locking and a bootstrap procedure; selection is deferred. Routine checks must not initialize remote state or query AWS.

Enterprise documentation will map these controls to CodePipeline/CodeBuild and AFT customization pipelines. Organizations, Control Tower, AFT, Transit Gateway, Palo Alto firewalls, and enterprise landing-zone infrastructure remain reference-only and will not be deployed for this POC.

## Open decisions

Phase 1 defines ten synthetic accounts, one root with four environment OUs, and five representative controls. Confirm dashboard personas, future exception workflow scope, cost ceiling, retention, domain needs, and teardown expectations. Node.js 24 and the local Vite/API development strategy are established. Select Terraform versions when infrastructure implementation is authorized. Deployment account details, state bootstrap, OIDC trust, and real evidence sources remain deferred until explicitly authorized.

## AWS reference documentation

- [Account provisioning and enrollment methods](https://docs.aws.amazon.com/controltower/latest/userguide/methods-of-provisioning.html)
- [AFT prerequisites and purpose](https://docs.aws.amazon.com/controltower/latest/userguide/aft-overview.html)
- [Updating existing accounts with AFT](https://docs.aws.amazon.com/controltower/latest/userguide/aft-update-account.html)

## Read-only versioned interview view

The [one-command interview workflow](INTERVIEW_DEMO.md) adds a server-owned version catalogue on the existing summary route. All data GETs accept a semantic policy version; repository selection stays server-side. V1 remains the default, while V2 uses a distinct content-addressed snapshot including its simulated journal/reference metadata. Optional Lambda configuration registers only pinned DynamoDB readers; the local launcher explicitly supplies an immutable file catalogue to the loopback demo server. Neither path grants browser or Lambda writes.

React scopes caches and metadata checks to the selected version/hash/time. Local rehearsal publishes no cloud data. Existing POC Terraform, Cognito and live V1 remain unchanged; versioned AWS IAM/configuration, actual publication and code deployment require separate review/authorization. Only V1/V2 policy profiles exist today; future versions use the same envelope with explicitly registered contracts/scenarios.

## Minimal governance CI boundary

The [PR validation workflow and interview audit](CI_CD_DEMO.md) reuse the provider-free root and existing evaluator/CLI. Real formatting, validation, planning, parity and Python tests run before the explicitly simulated approval/rollout report. Only synthetic review artifacts are uploaded; no AWS credentials, cloud backend, apply/destroy, production environment, publication, or auto-merge is configured. The local console updates only when the local launcher runs. Hosted dashboard updates still require separate approval/deployment/publication. CodePipeline manual approval/SNS notification are documented enterprise integration points only, not implemented components.

## Approved snapshot delivery

Data CD uses a protected GitHub environment/OIDC data-only publisher role; it cannot run Terraform or change runtime services. Snapshot records are conditionally written with the manifest last and strongly verified. A generation-checked single catalogue item atomically registers immutable revision provenance/history and promotes Current. Runtime only reads the catalogue/snapshots; browser uses the existing Cognito/API boundary. See [delivery contracts, limitations and deployment sequence](GOVERNANCE_DELIVERY.md). Simulated rollout evidence is distinct from real publication approvals/execution. Existing static/pinned V1 configuration remains supported during staged activation.
