# Architecture and responsibility boundaries

Status: the read-only application and controlled OIDC data-delivery path are deployed in the existing single-account POC. V1 bootstrap, V2 publication, rollback and V2 restoration are verified with real workflow/AWS evidence. The historical acceptance run restored V2 at generation 4; later Current generations are operational state, not a documentation constant; existing Amplify main auto-build is enabled separately. See [deployment acceptance](DEPLOYMENT_ACCEPTANCE.md). Simulated account operations remain distinct from real DynamoDB publication and GitHub approval.

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

## Proposed enterprise landing zone — not deployed

The management account would own Organizations and Control Tower. Dedicated security/audit and log-archive accounts would centralize audit storage, AWS Config and Security Hub aggregation under reviewed delegated-administration permissions. Environment OUs would separate Production, Pre-Production, Testing and Development, with central preventive policies and environment-specific customization requirements.

A separate network/inspection account would provide Transit Gateway routing and resilient Palo Alto inspection appliances for approved connected VPCs. Traffic symmetry, routing isolation, failover, licensing, capacity and cost require a production design review. No inspection VPC, Transit Gateway, firewall or enterprise account exists in this POC.

Authorized collectors would map Config/Security Hub results and deployment events into provenance-bearing evidence. They are future integrations: this console does not collect real findings or enforce controls across AWS accounts. Account Factory, AFT and central policy pipelines keep the separate ownership shown above.

V1/V2 identify whole-governance snapshots for demonstration. Production policy records need independent revisions, owners, scope, approval history and deployment outcomes; that richer policy lifecycle is outside the current contracts.

## Console and local development

React/TypeScript/Vite routes provide overview, inventory and details, compliance, deployments, drift, and exceptions. Generated OpenAPI types connect a read-only client to FastAPI via a loopback-only Vite proxy. Backend results are the sole runtime source; no frontend evaluator or fallback fixtures exist. TanStack Query handles loading, errors, cancellation, caching, and refresh. All data requests use the fixed reference timestamp and verify simulation provenance.

The proxy is deliberately restricted to a trusted local workstation: Vite and FastAPI bind to `127.0.0.1`, and Vite rewrites Host for the backend's demo guard. This is not production identity propagation. Deployed hosting uses Cognito Authorization Code + PKCE and API Gateway JWT authorization with explicit public API configuration, not the Vite proxy. No deployment authority or credentials are included in the browser. See [frontend implementation](FRONTEND.md) for contracts, paging, accessibility, tests, and snapshot limitations.

## Backend and data access

FastAPI routes → GovernanceService → GovernanceRepository/FixtureRepository. The service reuses the shared governance evaluator; Pydantic validates transport models and domain records are checked against the existing JSON Schema. The local fixture adapter performs no AWS calls; the deployed DynamoDB adapter uses bounded strongly consistent reads and digest verification. Pagination/filtering is bounded and deterministic for the fixed dataset. Evaluation defaults to a fixed demo time, not wall-clock time.

The default authenticator denies every request. Explicit local-demo mode grants only a loopback demo reader and rejects tokens; the launcher disables forwarded-header trust and binds only `127.0.0.1`. Server-side permission checks cover health/docs as well as data. The Authenticator interface supports verified Cognito identities. Mangum uses the fail-closed deployment factory: required configuration selects the immutable DynamoDB adapter and verified-gateway authenticator; missing configuration denies all access. The deployed factory supports a read-only DynamoDB Current/History catalogue while preserving pinned V1 compatibility. Local demo identity must never be used for deployed authentication.

No API storage writes, exception mutations, event consumers, or infrastructure execution are implemented in the application. A separate protected GitHub publisher performs approved conditional snapshot loading; the application never executes the publisher.

## Deployed AWS application

React on Amplify Hosting authenticates through Cognito. API Gateway enforces authorization before Python 3.13 Lambda reads DynamoDB. EventBridge-based asynchronous lifecycle handlers remain planned. Browser code receives no deployment credentials or direct database access. API, event processing, and deployment roles remain separate.

Any future exception submission or approval API needs a separately reviewed authorization and audit design. Display access does not imply mutation authority.

Every inventory/evidence record identifies simulation versus real observation, source, observation time, and stable identifiers. Compliance distinguishes evaluated pass/fail from unknown, stale, and not evaluated. Exceptions preserve underlying findings. Deployment history distinguishes simulated runs from actual workflow results and records revisions and correlation IDs.

## Account lifecycle and fleet operations

The policy-rollout CLI implements a local simulation of the lifecycle below. The CLI writes only ignored artifacts and explicitly opts into the `policy-v2` contract profile; default V1 validation, API contracts, fixture loading and pinned DynamoDB snapshot are unchanged. It separates V2 desired assignments from observed revisions, retains historical evidence/violations, stops on failed attempts, resumes pending targets and defers inactive accounts. Its approval journal is simulated, not an authenticated enterprise approval service. The local launcher never publishes cloud data. The separate protected CD workflow publishes a commit/digest-bound candidate after real approval. See [the demo runbook](POLICY_ROLLOUT_DEMO.md).

The optional isolated `terraform/simulation/` root consumes that same frozen proposal and calls the pure `simulated_governance` module per existing account. Real Terraform plans calculate only desired outputs; a separate read-only Python verifier compares the entire output and proposal digest. No provider/resource/data source, apply or live integration exists in this root. Terraform planning and Python simulated deployment/compliance reporting are explicitly distinct.

Enterprise new-account flow: approved request → Account Factory/AFT provisioning → baseline/customizations → published events and evidence → application read model. Existing accounts require inventory, supported enrollment where appropriate, assessment, and reviewed customization rollout. Discovery does not imply compliance.

Fleet changes use versioned definitions, environment targeting, canary waves, bounded concurrency, approval gates, and stop conditions. Desired and observed revisions are tracked separately. Drift detection combines scheduled reconciliation with relevant events; missing evidence is unknown. Automated remediation requires a later explicitly authorized design.

Handlers must tolerate duplicate and out-of-order events, use idempotency keys and revisions, bound retries, route exhausted failures to a dead-letter destination, and support audited replay. Recovery uses reviewed rollback or roll-forward and state reconciliation. Policy rollback must account for changed access constraints.

Exceptions require scope, rationale, owner, approver, approval reference, expiry, and audit history. Expiry triggers reevaluation and escalation; exceptions never silently erase findings.

## Delivery and enterprise integration

GitHub Actions validates application code, policies, Terraform and security; separate protected data CD publishes the exact approved commit/digest through OIDC. Use scoped OIDC trust, revision-bound artifacts, and serialized deployments per state. Untrusted PRs must not receive deployment credentials.

POC and enterprise roots never share state or execution roles. Shared module storage is not shared execution scope: POC roots must reference only POC-compatible modules, never enterprise-only modules or resources. The deployed POC uses encrypted remote Terraform state with locking; state/setup-token inputs and saved plans remain private and outside Git. Routine checks must not initialize remote state or query AWS.

The enterprise delivery design maps these controls to CodePipeline/CodeBuild and AFT customization pipelines. Organizations, Control Tower, AFT, Transit Gateway, Palo Alto firewalls, and enterprise landing-zone infrastructure remain reference-only and will not be deployed for this POC.

## Open decisions

V1 defines ten synthetic accounts, one root with four environment OUs and five representative controls; V2 adds a sixth control and an eleventh account. Production adoption requires decisions on user roles, exception approval, cost limits, retention, custom domains and recovery/teardown requirements. Node.js 24 and loopback Vite/API development are established. Terraform >=1.14,<2 and the locked AWS provider 6.71.0 define the current toolchain. The POC infrastructure and exact immutable GitHub OIDC trust are deployed. Real account evidence integrations remain outside this synthetic POC.

## AWS reference documentation

- [Account provisioning and enrollment methods](https://docs.aws.amazon.com/controltower/latest/userguide/methods-of-provisioning.html)
- [AFT prerequisites and purpose](https://docs.aws.amazon.com/controltower/latest/userguide/aft-overview.html)
- [Updating existing accounts with AFT](https://docs.aws.amazon.com/controltower/latest/userguide/aft-update-account.html)

## Read-only snapshot selection

The API exposes a server-owned version catalogue on the summary route; see [console validation](LOCAL_DEMONSTRATION.md). All data GETs accept a semantic policy version; repository selection stays server-side. Local/pinned compatibility defaults to V1; deployed requests without explicit version/time follow Current. V2 uses a distinct content-addressed snapshot including its simulated journal/reference metadata. Optional Lambda configuration registers only pinned DynamoDB readers; the local launcher explicitly supplies an immutable file catalogue to the loopback demo server. Neither path grants browser or Lambda writes.

React scopes caches and metadata checks to the selected version/hash/time. Local demonstrations publish no cloud data. The existing Cognito/app/API/table identities and immutable V1 are preserved. Authorized IAM/runtime activation and actual publication are recorded in the acceptance report. Only V1/V2 policy profiles exist today; future versions use the same envelope with explicitly registered contracts/scenarios.

## CI and cloud delivery boundary

[Credential-free CI](CI_CD_OPERATIONS.md) runs on PRs/main and performs real provider-free fmt/init/validate/plan/parity, Python/schema/security tests, POC mock-provider plans and frontend checks. It uploads only enumerated synthetic review/candidate artifacts, never credentials, Terraform state or executable infrastructure plans. It cannot deploy AWS. A separate manual-dispatch CD workflow reruns CI, checks exact commit/digest and owner/PR/environment policy, waits for actual approval, then assumes the data-only role through OIDC. Local `demo.sh` independently changes only local Current. CodePipeline/CodeBuild/SNS are enterprise design points, not deployed resources.

## Approved snapshot delivery

Data CD uses a protected GitHub environment/OIDC data-only publisher role; it cannot run Terraform or change runtime services. Snapshot records are conditionally written with the manifest last and strongly verified. A generation-checked single catalogue item atomically registers immutable revision provenance/history and promotes Current. Runtime only reads the catalogue/snapshots; browser uses the existing Cognito/API boundary. See [delivery contracts, limitations and deployment sequence](GOVERNANCE_DELIVERY.md). Simulated rollout evidence is distinct from real publication approvals/execution. Existing static/pinned V1 configuration remains supported during staged activation.

## Resource-compliance extension

The staged resource view uses `compliance_engine/resources.py` for strict contracts and deterministic observed-versus-desired evaluation. `compliance-rules/` owns central control intent; `mock-aws-resources/` owns synthetic observations. The existing provider-free Terraform module now optionally plans complete resource-control assignments, including environment freshness and approval intent. `deployment/resource_plan.py` checks every output against the same inputs before `deployment/resource_release.py` binds a release to CI's exact source commit. This is real planning, not AWS enforcement.

The protected publisher owns a distinct `RESOURCE-COMPLIANCE` catalogue sort key under the existing permitted partition. Existing IAM leading-key restrictions already cover it; no browser/runtime write permission is added. Content-addressed resource partitions have a verified manifest; immutable old content and the existing `STATE` catalogue remain intact. A conditional catalogue update records actor, Git commit, publication time and before/after resource results. A normal Git revert can select prior content with a new audit event. Evaluation remains tied to the explicit synthetic timestamp, independent of publication time.

`GET /api/v1/summary?view=resources` serves a coherent bounded resource dataset through the existing authenticated GET route. It rejects historical/version/evaluation query overrides; the dashboard always reads Current. No extra API Gateway route or AWS service is required. Missing or corrupt resource initialization fails closed rather than falling back to fixtures. Separate legacy exception and distribution reads retain their explicit account-governance scope.

Activation remains explicit: existing catalogue mode stays the default until compatible Lambda code, approved publication and authenticated acceptance pass. See [resource operations](RESOURCE_COMPLIANCE_OPERATIONS.md) and [requirement traceability](REQUIREMENTS_TRACEABILITY.md). New local acceptance does not retroactively establish cloud execution evidence.
