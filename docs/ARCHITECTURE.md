# Architecture and responsibility boundaries

Status: the Phase 1 model, Phase 2 local backend, and Phase 3 React console are implemented. AWS infrastructure remains design intent. See [contracts and evaluation](GOVERNANCE_MODEL.md) and [local API](BACKEND_API.md).

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

The default authenticator denies every request. Explicit local-demo mode grants only a loopback demo reader and rejects tokens; the launcher disables forwarded-header trust and binds only `127.0.0.1`. Server-side permission checks cover health/docs as well as data. The Authenticator interface is reserved for verified Cognito identities. Mangum compatibility is provided using a fail-closed application; no Lambda resource or API Gateway configuration exists. Local demo identity must never be used for deployed authentication.

No storage writes, exception mutations, event consumers, AWS integrations, or infrastructure execution are implemented.

## Planned AWS application

React on Amplify Hosting authenticates through Cognito. API Gateway enforces authorization before Python 3.13 Lambda reads DynamoDB. EventBridge routes asynchronous lifecycle and governance events to handlers. Browser code receives no deployment credentials or direct database access. API, event processing, and deployment roles remain separate.

Start with read APIs. Any later exception submission or approval API needs a separately reviewed authorization and audit design. Display access does not imply mutation authority.

Every inventory/evidence record identifies simulation versus real observation, source, observation time, and stable identifiers. Compliance distinguishes evaluated pass/fail from unknown, stale, and not evaluated. Exceptions preserve underlying findings. Deployment history distinguishes simulated runs from actual workflow results and records revisions and correlation IDs.

## Account lifecycle and fleet operations

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
