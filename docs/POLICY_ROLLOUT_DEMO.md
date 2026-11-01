# Policy lifecycle simulation

For the simplified **one-command, visual five-minute demo**, use [INTERVIEW_DEMO.md](INTERVIEW_DEMO.md). The commands below remain the advanced step-by-step explanation. No live publication is performed by either workflow.

The Python CLI runs independently of the AWS-hosted console. It is a local simulation: it performs no AWS SDK client creation, credential lookup, account provisioning, AFT execution, Terraform subprocess, database write or dashboard publication. It is separate from the read-only application.

The optional Terraform companion below performs **real local Terraform validation and planning**, not deployment. It has no providers, resources or data sources. The Python lifecycle, AFT execution records and compliance observations remain simulated. It is isolated from the deployed POC.

## Five-minute Terraform and rollout walkthrough

Prerequisites: existing Python development environment and Terraform >=1.14,<2 (tested 1.14.6). Run from the repository root. Choose a fresh run name; `plan` refuses to overwrite an existing run. All artifacts remain ignored. No AWS credentials or network access to AWS are needed.

**Minute 1 — freeze a simulated proposal; inspect real Terraform desired settings.**

```sh
RUN=artifacts/policy-rollout/tf-demo
.venv/bin/python -m governance.simulation.rollout plan --run-dir "$RUN"
terraform fmt -check -recursive terraform/simulation
terraform fmt -check -recursive terraform/modules/simulated_governance
terraform -chdir=terraform/simulation init -backend=false -input=false
terraform -chdir=terraform/simulation validate
```

Expected: CLI prints `SIMULATED ONLY`, phase `planned` and unchanged V1 counts. Fmt exits 0, init succeeds without installing a provider, validate prints `The configuration is valid.` The reusable module combines central baseline and environment requirements for each account. Terraform reads the same frozen proposal as the CLI, not a separate mock fleet.

**Minute 2 — real V1 and V2 output-only plans and full parity checks.**

```sh
terraform -chdir=terraform/simulation plan -input=false -refresh=false \
  -var="run_directory=../../$RUN" -var=policy_version=1.0.0 \
  -out="../../$RUN/v1.tfplan"
terraform -chdir=terraform/simulation show -json "../../$RUN/v1.tfplan" > "$RUN/v1.plan.json"
.venv/bin/python -m governance.simulation.terraform_plan --run-dir "$RUN" \
  --plan-json "$RUN/v1.plan.json" --policy-version 1.0.0
terraform -chdir=terraform/simulation plan -input=false -refresh=false \
  -var="run_directory=../../$RUN" -var=policy_version=2.0.0 \
  -out="../../$RUN/v2.tfplan"
terraform -chdir=terraform/simulation show -json "../../$RUN/v2.tfplan" > "$RUN/v2.plan.json"
.venv/bin/python -m governance.simulation.terraform_plan --run-dir "$RUN" \
  --plan-json "$RUN/v2.plan.json" --policy-version 2.0.0
```

Expected: Terraform shows `Changes to Outputs: + governance_desired` and no resource changes. It may print a generic apply suggestion; **do not follow it**. No apply is needed to inspect or verify plans. The verifier prints `REAL TERRAFORM PLAN VERIFIED` for ten synthetic assignments, the same proposal digest as the CLI, and these settings:

| Environment | V1 / V2 controls | Deployment approval | Maximum evidence age |
| --- | --- | --- | --- |
| Production | 5 / 6 | true | 24h |
| Pre-Production | 5 / 6 | true | 48h |
| Testing | 5 / 6 | false | 72h |
| Development | 5 / 6 | false | 168h |

It compares every account, OU, lifecycle, target revision, baseline, expected value, control category and freshness limit. Wrong proposal/version/configuration or any provider/resource-bearing plan is rejected. The final line says `NO RESOURCES / NO DEPLOYMENT / NO COMPLIANCE MEASUREMENT`. These are **real Terraform plans of synthetic desired configuration**, not deployed AWS policies, AFT executions or measured AWS compliance. Python remains the source of compliance evaluation; Terraform does not fabricate observed state. This optional verifier leaves the existing CLI behavior unchanged and is not an authenticated/enforced deployment gate.

**Minute 3 — simulated approval, canary and failure.**

```sh
.venv/bin/python -m governance.simulation.rollout approve --run-dir "$RUN" --approver sim-security-reviewer
.venv/bin/python -m governance.simulation.rollout rollout --run-dir "$RUN" --fail-account sim-account-005
```

Expected: approval references the same proposal digest verified from the Terraform plans. `canary.passed` for Development account 009 precedes fleet waves; a simulated failed customization on account 005 produces `rollout.blocked`, phase `blocked` and exit **2**, before Production. This is simulated deployment reporting, not a Terraform apply. Do not chain the next command behind `&&` after that intentional exit.

**Minute 4 — simulated recovery and new-account onboarding.**

```sh
.venv/bin/python -m governance.simulation.rollout rollout --run-dir "$RUN"
.venv/bin/python -m governance.simulation.rollout onboard --run-dir "$RUN"
```

Expected: successful targets are not repeated. Eight existing active accounts succeed, two inactive accounts remain deferred, then account 011 passes six simulated controls. Before onboarding, V2 counts are `37 / 4 / 9 / 10`; after onboarding they are `43 / 4 / 9 / 10` (compliant/noncompliant/unknown/stale).

**Minute 5 — explain application reporting and the live boundary.**

```sh
.venv/bin/python -m governance.simulation.rollout status --run-dir "$RUN"
```

Open `$RUN/report.json` for the deployment/compliance results and original V1 findings, `$RUN/candidate-snapshot.json` for the candidate read model, and `$RUN/findings.json` for evaluator results. These exports use the same read model consumed by the implemented protected publication path. The hosted dashboard is **not updated**. The original V1 snapshot remains available and unchanged. The ten-account Terraform plans represent frozen existing-account desired configuration; the eleventh-account lifecycle is a separate, explicitly simulated onboarding step.

## Demonstration story and policy meaning

NorthStar starts with ten synthetic accounts and baseline policy `1.0.0`. The security team proposes `2.0.0`, adding one detective requirement: **CloudTrail log-file integrity validation enabled** (`audit-log-integrity`). It applies to all four environments, with the existing 24/48/72/168-hour evidence freshness windows. The five previous requirements, environment-specific deployment approvals and organization-wide baseline remain unchanged.

This is simulated configuration evidence, not actual CloudTrail inspection, verified log integrity, a deployed SCP or a real Organizations policy. Enabling CloudTrail's feature allows digest delivery; separately validating those digests is another operation. See [AWS's distinction between enabling and validating](https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-log-file-validation-intro.html).

The interview sequence is:

1. **Propose and validate:** show the unchanged V1 baseline (31 compliant, 3 noncompliant, 6 unknown, 10 stale control findings). Actual offline schema/reference checks validate the V2 proposal and preserve previous requirements. Candidate V2 desired assignments do not imply observed deployment; old fresh V1 observations initially yield revision-mismatch/unknown under V2. The frozen V1 findings remain visible alongside them.
2. **Approve:** an explicitly named synthetic reviewer, separate from the proposer, approves the exact digest of the baseline, V2 policy/environments, scenario, canary and evaluation start. No rollout is allowed before this step.
3. **Canary:** active Development account `sim-account-009` goes first. All six controls must evaluate compliant before any other account is attempted. A tool-success result alone cannot pass the canary gate.
4. **Controlled rollout and failure:** proceed serially through Development, Testing, Pre-Production, then Production. Inject a simulated customization permission failure on `sim-account-005`; stop before Production. The report retains the failed attempt, desired/observed revisions, correlation ID and failure event. Resume without redeploying successful targets. Deployment distributes a policy/checker definition; it does not remediate workloads, so success can coexist with noncompliance.
5. **New account:** simulate `sim-account-011` in the Development OU, starting in onboarding under desired V2, creating a simulated customization record and six synthetic observations, and becoming active only after six passing evaluations. No AWS account is created.

Existing onboarding account `sim-account-007` and suspended account `sim-account-010` are **deferred**, not represented as successful deployments. Their desired policy is V2 but no new observation or application is claimed. Eight active existing accounts are attempted. All ten existing accounts remain in evaluation; the new account makes eleven. Completing this demo is not a claim of full fleet convergence or full compliance.

## Exact local commands

Use Python 3.13 and the existing development dependencies:

```sh
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m governance.simulation.rollout plan
.venv/bin/python -m governance.simulation.rollout approve --approver sim-security-reviewer
.venv/bin/python -m governance.simulation.rollout rollout --fail-account sim-account-005
```

The final command intentionally exits **2** and persists a blocked run. Do not chain the remaining commands behind `&&` after that expected failure. Continue explicitly:

```sh
.venv/bin/python -m governance.simulation.rollout status
.venv/bin/python -m governance.simulation.rollout rollout
.venv/bin/python -m governance.simulation.rollout onboard
.venv/bin/python -m governance.simulation.rollout status
```

All commands default to `artifacts/policy-rollout/demo/`. For another run, pass `--run-dir artifacts/policy-rollout/SECOND_NAME` to **every command**; `plan` refuses to overwrite an existing directory. `plan --at 2026-10-31T12:00:00Z --canary sim-account-009 --proposer sim-policy-author` makes defaults explicit. Dates come solely from that start time plus deterministic journal minute offsets, never the wall clock. Changing the start changes freshness/expiration and may cause canary rejection. To demonstrate a failed canary, use a separate approved run and `rollout --fail-account sim-account-009`.

Exit codes: **0** success/idempotent replay, **1** invalid request/state/approval, **2** controlled rollout block. Completed rollout/onboarding and repeated matching approval are no-ops. `status` does not write files. Only one process should operate on a run at a time.

## Results and provenance

| Stage | Accounts | Controls per account | Compliant | Noncompliant | Unknown | Stale |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Frozen V1 baseline | 10 | 5 | 31 | 3 | 6 | 10 |
| V2 after rollout/resume | 10 | 6 | 37 | 4 | 9 | 10 |
| V2 after onboarding | 11 | 6 | 43 | 4 | 9 | 10 |

These totals use the reference start and checked-in scenario, with or without the illustrated failure/retry. Failure adds audit history/time, not fabricated compliance. The new control passes for six active existing accounts, fails for `sim-account-004`, and has no evidence for `sim-account-006` or the two deferred accounts. New account 11 passes all six. Existing baseline failures and active/expired exceptions remain failures; missing evidence stays unknown and old stale evidence remains stale.

`collect()` is an explicitly simulated re-collection: for fresh existing baseline observations, it appends new V2 evidence carrying the same boolean, including failures. It never edits or retags historical rows. Missing/stale baseline observations are not refreshed. New control observations come from the versioned scenario; new-account baseline observations use the approved environment expectations. None of these are measured AWS results. The run journal distinguishes distribution from subsequent compliance evaluation.

The CLI writes four ignored files only:

- `state.json`: checksum-protected authoritative run state, frozen inputs, simulated approval, current candidate and ordered journal; validated by `governance/simulation/run.schema.json` plus the domain contracts.
- `report.json`: V1 findings/account summaries, V2 counts/account summaries, evaluation time, rollout outcomes and audit trail.
- `candidate-snapshot.json`: explicit `policy-v2` profile, simulation metadata, content digest and `{fleet, policy, environments}` payload for publication validation/review.
- `findings.json`: current V2 findings produced by the existing evaluator.

The output root is restricted to `artifacts/policy-rollout/`, including symlink resolution. Source fixtures, Terraform and live configuration cannot be output targets. Individual files are atomically replaced, with state written last; the four-file export is not a transactional storage system. After an interrupted export, regenerate derivatives from the authoritative state with an idempotent applicable command. There is no multi-process lock, distributed execution or event-consumer infrastructure.

Checksums detect accidental editing and approvals bind exact inputs. **They are not signatures, authenticated identity, tamper-proof audit or real authorization.** A local file owner can rewrite files and checksums. Synthetic `sim-` reviewer names do not authenticate people. A production workflow requires real identity, protected approvals and durable audit/concurrency design.

## Compatibility and protected dashboard integration

Default `validate()`, `validate_model()` and `evaluate()` remain strict V1 contracts; the rollout CLI explicitly selects `profile="policy-v2"`. V1 source fixtures and the pinned digest are preserved. Schema/source version identifies the synthetic record protocol, while profile/policy revision/generator identifies the scenario. The raw CLI exports are not directly publishable.

The implemented publication adapter validates the completed frozen run and real Terraform-plan parity, binds it to an exact clean Git commit, and creates a distinct immutable envelope/context. Protected GitHub OIDC CD conditionally loads the approved snapshot, verifies it strongly and updates the generation-checked Current/History catalogue. Deployed API/React readers select that registered version; local CLI/launcher commands never contact AWS or publish data. See [delivery contracts](GOVERNANCE_DELIVERY.md) and [actual execution evidence](DEPLOYMENT_ACCEPTANCE.md).

V1/V2 represent whole-governance snapshots, not independently versioned production policies. Future policies/profiles require reviewed contract/scenario registration and a new version/digest. Real Config/Security Hub evidence, AFT distribution and central Organizations enforcement remain separate production integrations. The browser and reader Lambda retain no write/deployment authority.

## Validation

```sh
.venv/bin/python -m unittest tests.test_policy_rollout -v
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/ruff check backend governance scripts tests
.venv/bin/ruff format --check backend governance scripts tests
.venv/bin/python -m compileall -q backend governance scripts tests
.venv/bin/python -m pip check
npm --prefix frontend run api:check
npm --prefix frontend run typecheck
npm --prefix frontend run lint
npm --prefix frontend test
npm --prefix frontend run build
git diff --check
```

Tests cover unchanged V1 behavior/schema/defaults and snapshot digest, all environment requirements, missing/self/changed-input approval, failed canary/compliance gates, mid-wave failure and retry, inactive deferrals, known totals, missing/stale evidence, active/expired exceptions, deterministic/no-client operation, onboarding and replay, checksum tampering, CLI persistence/exit codes and output restrictions. Existing backend/frontend tests remain the compatibility checks for the read-only dashboard.
