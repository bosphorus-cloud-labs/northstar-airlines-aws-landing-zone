# Governance model v1

Implemented: offline JSON contracts, environment definitions, ten synthetic accounts, and a Python 3.13 evaluator. No AWS integrations, resources, application API, frontend, or workflows exist. The model describes policy intent, not deployed Organizations policies or verified AWS compliance.

## Execute locally

```sh
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/ruff check governance tests
.venv/bin/ruff format --check governance tests
.venv/bin/python -m governance.model.evaluate --at 2026-10-31T12:00:00Z
.venv/bin/python -m governance.model.evaluate --at 2026-10-31T12:00:00Z --findings
```

Installation downloads pinned Python dependencies; evaluation and tests need no network, AWS credentials, or AWS SDK. The RFC 3339 validator is explicitly pinned because JSON Schema format checking otherwise may silently skip date-time validation. `--at` is mandatory. All persisted timestamps must be RFC 3339 with timezone; there is no system-clock default. No output is written unless the caller redirects stdout.

## Versioning and validation

`governance/contracts/v1.schema.json` is a JSON Schema Draft 2020-12 document. Its root validates the fixture bundle. `$defs` defines individually reusable account, OU, policy, environment, requirement, evidence, finding, deployment, drift, exception, and event contracts. `validate(kind, record)` validates individual records; `validate_model(fleet, policy, environments)` additionally validates relationships and temporal invariants.

All records carry `schema_version: 1.0.0`. Policy and environment definitions also bind an explicit policy content version. Breaking contract changes require a new schema version and migration; policy changes require a new content version and retained fixtures/tests for old versions. Version 1 accepts only its declared schema/policy version; older observed evidence revisions are allowed but cannot prove compliance with the desired revision.

Object fields are required and unknown fields rejected. IDs must be unique within collections. Account/OU/environment and policy references must resolve, OU ancestry must have one root and no cycles, every environment must define every control exactly once, and ambiguous evidence timestamps are rejected. Lifecycle values are `active`, `onboarding`, and `suspended`; these describe synthetic inventory, not real account state. No lifecycle state bypasses evaluation.

## Contracts and relationships

| Contract | Fields and meaning |
| --- | --- |
| OU | `id`, `parent_id` (null only for root), `environment`; IDs use `sim-ou-*` by fixture convention |
| Account | `id` (`sim-account-NNN`, never a 12-digit AWS ID), `name`, `environment`, `ou_id`, `lifecycle_status`, `desired_policy_version`, `created_at`, provenance |
| Policy | `id`, `version`, `baseline_requirements`, `controls`; each control has `id`, `category`, and descriptive intent |
| Environment | `id`, display `name`, `policy_id`, `policy_version`, `requirements`; each requirement has `control_id`, boolean `expected`, and positive integer `max_age_hours` |
| Evidence | `id`, `account_id`, `control_id`, `observed_value`, `observed_at`, `observed_policy_version`, provenance; observations never overwrite desired requirements |
| Finding | Stable account/control `id`, account/control references, `evaluated_at`, desired `policy_version`/`desired_value`, `observed_value`, `evidence_id`, `status`, `reason`, exception IDs/states, provenance |
| Deployment | `id`, `account_id`, `tool` (`terraform` or `aft`), `desired_revision`, nullable `observed_revision`, `status`, `started_at`, nullable `completed_at`, `correlation_id`, nullable `failure_reason`, provenance |
| Drift | Account/control references, desired/observed values and revisions, `observed_at`, `status` (`in-sync`, `drifted`, `unknown`), provenance |
| Exception | Account/control scope, `status`, `rationale`, `owner`, nullable `approver`/`approval_reference`/`approved_at`, `created_at`, `expires_at`, audit entries (`at`, `action`, `actor`), provenance |
| Event | `id`, `account_id`, typed lifecycle `type`, `occurred_at`, `revision`, `correlation_id`, resolvable `subject_id`, provenance |

Every synthetic account, evidence, deployment, finding, drift, exception, and event uses `simulated: true` and `source: northstar-synthetic-v1`. This schema deliberately rejects real-observation provenance. Real integrations will need separate reviewed contracts; changing a flag does not turn a fixture into real evidence. OU/policy/environment definitions are model configuration, not deployed resources.

Deployment terminal states require completion timestamps. Success requires matching desired/observed revisions and no failure reason; failure requires a reason. Pending records have no completion time. Drift status reflects value comparison independently from revision comparison: revision divergence is visible even when a particular control value matches. Events resolve subjects within the record collection selected by their type, verify applicable status and transition timestamps, and do not execute any action. This phase validates and displays history; it does not implement event transport, replay, AFT, or Terraform execution.

Exceptions require positive lifetimes and approval metadata for approved status. Approval time must fall inside the lifetime. Audit entries cannot predate creation. Approved exceptions require a matching approval audit action, approver, and timestamp. Audit history here is fixture data, not a tamper-proof audit store; persistence enforcement belongs to later implementation.

## Environment requirements

Boolean `true` means the named safeguard is enabled, not that a raw public-access setting is true. `public-access` means public-access restrictions are enabled. Encryption/logging/monitoring are coarse account-baseline demonstration checks, not exhaustive assessments of every service or resource.

| Requirement | Category | Production | Pre-Production | Testing | Development |
| --- | --- | --- | --- | --- | --- |
| Deployment approval required | CI/CD approval | true | true | false | false |
| Baseline encryption enabled | Detective check | true | true | true | true |
| Public-access restrictions enabled | Preventive intent | true | true | true | true |
| Audit logging enabled | Detective check | true | true | true | true |
| Security monitoring enabled | Detective check | true | true | true | true |
| Evidence maximum age, hours | Freshness | 24 | 48 | 72 | 168 |

Testing and Development intentionally omit a *mandatory* approval gate in this representative policy; expected false matches a gate-free configuration. This strict boolean model treats any mismatch as noncompliant, including an extra gate; a future minimum-safeguard model should explicitly version that semantic change. Other safeguards stay mandatory across environments. `baseline_requirements` centrally declares encryption, public-access restrictions, logging, and monitoring as required. Schema validation prevents weakening that v1 baseline, and cross-record validation rejects environment overrides that contradict it. This is offline model enforcement, not AWS enforcement.

Preventive intent is a desired guardrail that could later combine supported SCP action restrictions with service-level controls. No SCP document, attachment, or enforcement exists here. Detective checks inspect synthetic configuration evidence. CI/CD approval evidence describes gate configuration, not proof that a particular deployment was approved. The read-focused application/evaluator owns none of those enforcement paths. Existing/new-account customization and central policy ownership remain as documented in `ARCHITECTURE.md`.

## Deterministic evaluation

1. Validate contracts and relationships, parse supplied evaluation time, reject evaluations predating account creation.
2. For each account/control, select the latest observation at or before the evaluation timestamp. Ignore future observations; if only future evidence exists, return unknown with `future-evidence`. Conflicting observations at the same account/control/time are rejected rather than resolved by input order.
3. No observation gives unknown (`missing-evidence`). Age strictly greater than the environment maximum gives stale (`stale-evidence`); the exact age boundary is fresh. Stale includes the last observed value but never a current pass claim.
4. Fresh evidence for a different policy revision gives unknown (`revision-mismatch`). Otherwise compare actual and desired booleans: compliant (`match`) or noncompliant (`mismatch`).
5. Attach scoped exceptions as active, expired, not-yet-active, pending, or rejected. Approval becomes effective at `approved_at`; expiration is exclusive (`evaluation >= expires_at`). Exceptions never alter control status. Multiple exceptions remain visible in ID order.

Account aggregation priority is noncompliant → stale → unknown → compliant. Per-control counts preserve uncertainty even if a known failure dominates the account summary. Findings are sorted by account/control IDs and exceptions by ID. Evaluation is pure, does not mutate fixtures, and does not read wall-clock time. Finding IDs identify account/control pairs; use `evaluated_at` as part of a persisted history key in later storage.

## Reference fleet at 2026-10-31T12:00:00Z

All account IDs below begin with `sim-account-`; none represent AWS accounts.

| Suffix | Environment | Lifecycle | Account result | Scenario |
| --- | --- | --- | --- | --- |
| 001 | Production | active | compliant | Five fresh matches |
| 002 | Production | active | noncompliant | Encryption fails; approved active exception remains visible |
| 003 | Production | active | stale | All five observations expired |
| 004 | Pre-Production | active | unknown | Logging evidence missing |
| 005 | Pre-Production | active | noncompliant | Public restrictions fail; simulated failed deployment and drift |
| 006 | Testing | active | compliant | Five matches, no required approval gate |
| 007 | Testing | onboarding | unknown | No observations; simulated pending customization |
| 008 | Development | active | noncompliant | Monitoring fails; exception expired |
| 009 | Development | active | compliant | Five fresh matches |
| 010 | Development | suspended | stale | Five expired observations; suspension does not waive checks |

Total: **50 controls: 31 compliant, 3 noncompliant, 6 unknown, 10 stale**. Account totals: 3 compliant, 3 noncompliant, 2 unknown, 2 stale.

## Limits and next steps

The fixtures are snapshots, not an event-sourced history. Cross-record validation does not reconstruct a complete state machine or verify cryptographic approvals. Drift records are supplied examples, not AWS scans. The evaluator uses coarse booleans and one policy version; service/resource-specific checks and migrations need future contracts. No exception mutation API, authorization system, durable audit store, scheduler, or automated remediation has been added. Future backend work must enforce those boundaries separately.
