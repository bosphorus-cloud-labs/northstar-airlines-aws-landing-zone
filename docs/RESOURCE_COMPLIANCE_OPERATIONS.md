# Synthetic resource compliance operations

## Scope and activation

The resource console adds a simple Git-based change workflow to the existing application. It is enabled on the deployed main branch with `governance_frontend_mode = "resources"` (`VITE_GOVERNANCE_API_MODE=resources` in the frontend). The default remains `catalog` so merging the code does not replace the deployed console before backend compatibility and protected data publication are verified. Existing API contracts, authentication, snapshots and account-governance demonstrations remain available.

[Resource-console acceptance](RESOURCE_CONSOLE_ACCEPTANCE.md) records actual protected publication and authenticated cloud checks. [Earlier catalogue evidence](DEPLOYMENT_ACCEPTANCE.md) remains a separate historical record. Keep `governance_frontend_mode = "resources"` in private deployment inputs for future POC plans; the module default deliberately remains `catalog` for backwards compatibility. Neither mode changes authentication or write permissions.

## Files an operator edits

| File | Purpose |
| --- | --- |
| `mock-aws-resources/resources.json` | Synthetic resource observations and explicit evaluation time; edit configuration attributes, never precomputed compliance statuses. |
| `mock-aws-resources/accounts.json` | Synthetic account inventory and four environment/OU assignments. |
| `compliance-rules/resource-controls.json` | Central baseline: IMDSv2 required, S3 public access blocked and EBS encryption enabled; environment-specific evidence freshness. |
| `terraform/modules/simulated_governance/main.tf` | Existing reusable, provider-free desired-state module. |
| `terraform/simulation/main.tf` | Existing planning root, extended with optional resource/control inputs. |

Production, Pre-Production, Testing and Development use 24, 48, 72 and 168-hour evidence limits respectively. Production and Pre-Production inherit approval intent from the account-governance baseline. Real publication into the POC always additionally requires GitHub Environment approval, regardless of the target environment. Freshness may be tightened within each environment ceiling; weakening the baseline is rejected. These are synthetic requirements, not deployed SCPs. Production EBS observation `sim-ebs-003` is 18 hours old at the explicit evaluation time: tightening Production freshness from 24 to 12 hours changes its result from compliant to stale. This preserves the original Production policy-change demonstration without changing existing snapshot files.

## Real Terraform connection

`deployment.resource_plan.prepare` validates inputs, freezes the existing rollout proposal, executes real `terraform fmt`, `init -backend=false`, `validate`, and `plan -refresh=false`, then reads the plan with `terraform show -json`. It rejects cloud resources, providers, data sources and remote backends. It compares **every account, environment, approval requirement and control assignment** to Python's desired projection. The release includes that verified receipt bound to the exact input content. The dashboard only reports Terraform verification when that receipt exists. Local raw fixtures explicitly report that Terraform has not run.

The Terraform plan represents desired configuration. It does not provision or remediate anything. The Python engine evaluates synthetic observed configuration independently. Configuration distribution success never changes missing, stale or failing evidence into a pass. Existing `demo.sh` and the tested rollout engine retain canary, controlled failure, retry and onboarding for deeper operational demonstrations.

## Protected delivery

1. A feature PR runs the existing credential-free governance CI, including schemas, security, all Python tests, frontend tests, real Terraform planning and complete parity.
2. CI produces `resource-release-<source SHA>`: a commit-bound release, readable Terraform plan, per-resource findings and a Markdown check summary. It contains synthetic data, not state or credentials.
3. After successful **push-to-main** CI, the existing delivery workflow verifies the exact run, repository, protected main commit, merged PR and approval model. Fork/PR validation runs cannot publish. Documentation-only merges do not request resource publication.
4. The publisher job waits for the actual `governance-production` approval. The explicitly documented single-owner POC model permits owner review; administrator bypass and non-main deployment remain prohibited.
5. Only then is the existing least-privilege OIDC role assumed. The job revalidates provenance before requesting credentials and rechecks current main immediately before writes and promotion. No long-lived AWS credentials are introduced.
6. Immutable records are inserted conditionally, manifest last, then read strongly and integrity-checked. A conditional catalogue update selects Current and appends before/after audit records. A failed/partial load cannot promote Current. Already-current data is a verified no-op.

The new catalogue uses `GOVERNANCE#CATALOG / RESOURCE-COMPLIANCE`. The existing `STATE` catalogue and all historical snapshots remain untouched. Snapshot identifiers and internal compare-and-swap generations remain implementation details; users do not manage them. A Git revert reuses immutable content and records a new approved publication event. A bounded history of 128 publications and 100 accounts/200 resources intentionally limits this POC; indexed fleet-scale storage and archival are future work.

Use the existing delivery workflow's `resources` action on main only for a controlled baseline retry; source SHA and content identity are selected and verified automatically. Older dispatch actions remain available for the preserved catalogue recovery procedure, not the new presentation workflow.

## Implemented source-to-console path

| Stage | Exact implementation | Verified boundary |
| --- | --- | --- |
| PR/main validation | `.github/workflows/governance-ci.yml` — Governance checks and Frontend checks | Credentials-free schemas, engine/backend tests, source hygiene, frontend types/lint/format/tests/build; no AWS identity or apply. |
| Desired-state automation | `deployment/resource_plan.py::prepare`; `terraform/simulation/main.tf`; `terraform/modules/simulated_governance/main.tf` | Real fmt/init/validate/plan/show, provider/resource/backend boundary guard and exact 100-account / 300-control assignment parity. |
| Commit-bound artifact | `deployment/resource_release.py` build/check; `compliance_engine/resources.py::verify_receipt` | Validated observations and requirements, input-bound Terraform receipt, content digest, source SHA, readable report; a valid noncompliant observation is reported rather than rejected. |
| Approval gate | `.github/workflows/governance-cd.yml` — resource-gate, then resource-publish; `deployment/delivery_gate.py::verify` | Exact successful main CI/run/artifact and merged PR, current-main checks, main-only `governance-production`, actual reviewer approval. The existing single-owner model deliberately permits owner review; no independent review is claimed. |
| AWS identity and data publication | Existing configure-aws-credentials OIDC step; `governance/delivery/resource_publisher.py::publish`; `deployment/seed_governance.py::load` | Short-lived data-only role. Conditional immutable writes, manifest-last insertion, strong digest read-back, atomic Current/history compare-and-swap; rechecks main before writes/promotion. No infrastructure deployment. |
| Read API | `backend/api/routes.py::summary`; `backend/deployment/resources.py::DynamoResources`; `backend/deployment/application.py` | `GET /api/v1/summary?view=resources`, trusted API Gateway/Cognito authorization, strongly verified Current and snapshot; failures do not substitute local findings. |
| Read-only console | `frontend/src/api/resources.ts`; `frontend/src/ResourceConsole.tsx` | Resources, per-control Compliance counts and Deployment Activity share the current evidence response. Refresh re-reads it. Exceptions use their existing separate endpoint; resource publication never grants exemptions or rewrites that catalogue. |

The local CLI and local fixture edit are not automatically connected to AWS. Only an approved main publication changes DynamoDB. The browser and reader Lambda have no publisher or Terraform permissions. Protected Environment settings, IAM and infrastructure are not changed by the session/demo-preparation PR.

## Tests and editable input

Fixed positive/negative test scenarios live in `tests/fixtures/resource-compliance.json`. The frontend contract examples are generated from that fixture through the actual FastAPI route. They are never a runtime browser data source. This intentional separation lets an operator edit one resource observation without rewriting golden test results. CI separately validates and plans the actual `mock-aws-resources/` and `compliance-rules/` inputs; valid noncompliant observations produce a report rather than failing schema validation.

## Local validation

From a clean checkout with Python 3.13, Node 24 and Terraform 1.14.6 installed:

```sh
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
npm --prefix frontend ci
.venv/bin/python -m unittest discover -s tests -v
npm --prefix frontend test
npm --prefix frontend run build
.venv/bin/python -m deployment.resource_release build --source-commit "$(git rev-parse HEAD)"
cat artifacts/resource-release/report.json
cat artifacts/policy-rollout/resources-ci/terraform-plan.txt
```

Release preparation requires a clean, exact checkout and a fresh output directory; for another rehearsal use `--run-dir artifacts/policy-rollout/rehearsal-2`. The command does not request AWS identity or write DynamoDB. Generated results remain ignored.

Run the backend in one terminal and frontend in another:

```sh
.venv/bin/python -m backend --local-demo
```

```sh
VITE_GOVERNANCE_API_MODE=resources npm --prefix frontend run dev
```

Open http://127.0.0.1:5173. The local backend reads current source fixtures on every request, so refresh the browser after editing fixtures. Local data is labelled **not published** and has no fabricated GitHub approval history or Terraform receipt. Cloud data changes require the protected pipeline.

## Required proof chain

```text
Central controls + synthetic account/environment assignments
  → existing provider-free Terraform root and reusable module
  → complete desired-output parity check and input-bound receipt
  → protected release publication
  → read-only API: terraform_validation + independent compliance findings
  → one governance console: environments, accounts, evidence and activity
```

Changing an observation does not weaken Terraform's desired requirement: IMDSv2 remains required when observed tokens become optional. The resulting mismatch is the compliance finding. Changing a central requirement changes the planned assignments themselves; both paths use the same module, verifier and application read model.

## Five-minute operational demonstration

Use the existing [governance console](https://main.d1eetlse86595h.amplifyapp.com/) and its in-application **Refresh** button. The authoritative path is PR → CI artifact → successful main CI → actual Environment approval → OIDC data publication → DynamoDB Current → authenticated GET. Amplify frontend builds are separate; a data publication does not require a new frontend bundle.

### Verified starting state and exact change

Read-only AWS checks on 7 November 2026 verified Current generation 6: 100 accounts, 100 resources, Booking API compliant, totals **77 compliant / 9 noncompliant / 7 unknown / 7 stale**. This is a checkpoint, not a guarantee of future Current; verify the application before each walkthrough.

| Item | Exact value |
| --- | --- |
| File | `mock-aws-resources/resources.json` |
| Resource / account / environment | Booking API / `sim-ec2-001` / `sim-account-001` / Production |
| Control | `ec2-imdsv2` — Require IMDSv2 |
| Desired setting | `metadata_options.http_tokens = required`; defined in `compliance-rules/resource-controls.json` |
| Noncompliant preparation | Change only observed `configuration.metadata_options.http_tokens` to `optional` |
| Compliant restoration | Git-revert that observation change back to `required` |
| Fleet before → after restoration | 76 / 10 / 7 / 7 → 77 / 9 / 7 / 7 |
| IMDSv2 row before → after | Total 34: 27 compliant, 1 noncompliant, 2 unknown, 4 stale → 28 compliant, 0 noncompliant, 2 unknown, 4 stale |
| Other controls | S3: 26 / 5 / 0 / 2; EBS: 23 / 4 / 5 / 1; unchanged |

These numbers describe the validated 100-account fixture. If Current differs, use its actual findings rather than repeating stale totals. Do not edit policy requirements, evidence timestamps, exceptions or precomputed findings for this scenario.

### Prepare before the timed walkthrough

1. Review/merge the session fix and wait for its normal Amplify build before relying on thirty-minute renewal. That frontend change is not deployed just because its PR tests pass. See [session management](FRONTEND.md#cognito-session-management) and complete the 0/10/20/30-minute live check after release.
2. In a clean checkout, prepare a one-field noncompliant observation on a feature branch. Do not overwrite unrelated work:

   ```sh
   git status --short
   git switch main
   git pull --ff-only
   git switch -c demo/booking-noncompliant-$(date +%Y%m%d-%H%M%S)
   # In VS Code: change only Booking API http_tokens from required to optional.
   git diff -- mock-aws-resources/resources.json
   git add mock-aws-resources/resources.json
   git commit -m "demo: prepare noncompliant synthetic Booking API evidence"
   change_commit=$(git rev-parse HEAD)
   git push -u origin HEAD
   gh pr create --draft --base main --title "Prepare synthetic Booking API regression" --body "One synthetic observation only. Expected 76/10/7/7. Merge and publication require explicit approval."
   ```

3. After the session fix merges, update any already-open data branch from current main and rerun its CI. Inspect the PR's **Governance checks** and **Frontend checks**. Open the resource-release artifact's `summary.md`, `report.json` and readable `terraform-plan.txt`: real provider-free fmt/init/validate/plan and all 100 account/control assignments must pass. An insecure observation is valid input and must produce a noncompliant finding; schema validation is not an instruction to make every resource pass.
4. **Approval boundary:** do not merge or publish without the owner's explicit approval. After approved protected merge, wait for main CI, then approve the actual `resource-publish` deployment in `governance-production`. Verify the published receipt, Current, Booking API's optional/noncompliant observation, IMDSv2 counts and Deployment Activity. No terminal publisher or direct DynamoDB update is part of this walkthrough.
5. Prepare the compliant restoration from updated main:

   ```sh
   git switch main
   git pull --ff-only
   git switch -c demo/booking-compliant-$(date +%Y%m%d-%H%M%S)
   git revert "$change_commit"
   git diff HEAD^ HEAD -- mock-aws-resources/resources.json
   git push -u origin HEAD
   gh pr create --base main --title "Restore synthetic Booking API compliance" --body "Git revert of the observation change. Expected 77/9/7/7 after approved publication; all 100 accounts retained."
   ```

   If the earlier PR was squash-merged, use its actual merged data commit, not the original feature SHA. If the terminal variable was lost, copy the exact data commit from the PR. Do not revert the 100-account fleet-extension commit.
6. With explicit merge approval, finish restoration CI **before** the five-minute slot. Leave its real `resource-publish` job waiting for Environment review. Keep main unchanged while it waits: the publisher rejects an outdated source revision. Have the owner/reviewer signed in to GitHub and the reader signed in to Cognito. Never approve a pending deployment solely to create a presentation effect without authorization.

### Timed sequence: live read and approval, validation prepared earlier

| Time | Screen/action | State clearly |
| --- | --- | --- |
| 0:00–0:45 | Overview: 100 accounts, four environment requirements and Terraform verification | Live authenticated API data; accounts and observations synthetic. |
| 0:45–1:45 | Resources & Drift: search Booking API, show desired required / observed optional and the violation reason | Live Current, after approved preparation. If preparation was not published, show its real compliant state and use recorded evidence instead. |
| 1:45–2:30 | Compliance: IMDSv2 counts and overall 76/10/7/7; briefly show exceptions | Counts from the same backend findings; exceptions unchanged and do not exempt this resource. |
| 2:30–3:15 | GitHub: one-field restoration PR, completed Governance/Frontend checks, readable Terraform plan for all 100 accounts | Validation already executed; do not pretend a new CI run completed instantly. |
| 3:15–4:15 | Open the prevalidated restoration's waiting `resource-publish` job. Authorized owner reviews `governance-production` and selects Approve and deploy | This approval and subsequent OIDC publication are live only if actually performed. Do not bypass or auto-approve it. |
| 4:15–5:00 | Refresh in the console. Show required/required, compliant, updated IMDSv2 and 77/9/7/7 totals, then Deployment Activity | Show actual publication time and optional → required / noncompliant → compliant event; do not claim success before it is returned. |

CI and human/network latency cannot be guaranteed inside this window. A release already waiting for approval removes CI execution from the timed slot, but publication can still be delayed. Always keep the recorded path below ready.

### Verified recorded path and recovery

These runs were checked against actual DynamoDB history; they are **historical executions**, not newly triggered demonstrations:

- [100-account baseline publication — 42100340646](https://github.com/bosphorus-cloud-labs/northstar-airlines-aws-landing-zone/actions/runs/42100340646).
- [Regression CI — 42101340719](https://github.com/bosphorus-cloud-labs/northstar-airlines-aws-landing-zone/actions/runs/42101340719) and [approved regression publication — 42101605111](https://github.com/bosphorus-cloud-labs/northstar-airlines-aws-landing-zone/actions/runs/42101605111).
- [Restoration CI — 42102062713](https://github.com/bosphorus-cloud-labs/northstar-airlines-aws-landing-zone/actions/runs/42102062713) and [approved compliant restoration — 42102266716](https://github.com/bosphorus-cloud-labs/northstar-airlines-aws-landing-zone/actions/runs/42102266716).
- [Governance validation workflow](https://github.com/bosphorus-cloud-labs/northstar-airlines-aws-landing-zone/actions/workflows/governance-ci.yml) and [approved data-delivery workflow](https://github.com/bosphorus-cloud-labs/northstar-airlines-aws-landing-zone/actions/workflows/governance-cd.yml).

If the release remains waiting or fails, Current must not be described as updated. Show the failed/waiting job honestly, then the verified historical CI/approval/receipt and the console's retained before/after audit. The live UI may already be compliant: label the earlier noncompliant event as recorded, not current. See [recorded acceptance](RESOURCE_CONSOLE_ACCEPTANCE.md#unified-100-account-extension).

For a local fallback, run the API and Vite commands above and change the same observation locally, then click Refresh. Clearly label it local and not published; local fixtures have no fabricated approval history or Terraform receipt. Revert the local edit afterwards. For an actual published regression, restore with a reviewed Git revert and the same protected workflow; never edit DynamoDB directly or bypass a failed gate. If main advances while an approval waits, validate the new exact source and obtain fresh approval rather than rerunning an obsolete publication. Do not repeatedly re-dispatch a data workflow without inspecting its actual Current/receipt first.

### Speaking outline

“Here are 100 synthetic accounts across four environments. Terraform calculates their desired baseline, and Python evaluates independent resource observations. Booking API currently allows optional metadata tokens, which violates IMDSv2. The control summary aggregates that same evidence. This reviewed Git change restores the required setting; its validation ran before this walkthrough. Only the actual Environment approval lets a short-lived, data-only OIDC role publish to DynamoDB. Refresh now shows the approved result and its audit event. The application infrastructure and pipeline are real; no AWS instance or security policy was changed.”

For the recorded path, replace “currently” with “in this recorded regression” and “publish now” with “this completed approved run published the restoration”.

## Central-policy variant and retained operational scenarios

To show an actual desired-policy delta instead of an observation delta, edit **only** `compliance-rules/resource-controls.json`: for `ebs-encryption`, change `max_age_hours.production` from `24` to `12`. Use the same reviewed Git/CI/approval workflow. Terraform must plan 12-hour EBS requirements for all 30 Production accounts while retaining other environments' limits. Resource `sim-ebs-003` has an 18-hour-old observation: its result changes from compliant to **stale**, while desired and observed encryption both remain true. Revert the data commit to restore the 24-hour requirement. This demonstrates evidence freshness, not a logging-retention setting or disabled encryption.

For an offline rehearsal of central/environment-wide changes and new-account inheritance, one command runs the real Terraform-backed acceptance cases without editing tracked data or contacting AWS:

```sh
.venv/bin/python -m unittest -v \
  tests.test_resource_compliance.HundredAccountTests.test_central_policy_changes_propagate_across_hundred_account_fleet \
  tests.test_resource_compliance.ResourceComplianceTests.test_new_synthetic_account_inherits_terraform_baseline
```

Keep CI's retained `simulation.txt` and rollout `report.json` ready to show simulated approval, canary, stopped failure, retry and account onboarding without typing a second sequence during the five-minute presentation. `./demo.sh v2 --prepare-only` remains an optional detailed local walkthrough. These distribution results are simulated; the Terraform planning and parity are real. Account-governance exceptions remain visible separately and never exempt the resource findings. Large-fleet collectors, provisioning and orchestration are design-only beyond the bounded POC.

The three required proofs are therefore visible in five minutes: **central environment rules**, **real Terraform plan/parity**, and **multi-account application results**. Allow CI and human approvals to finish before timed presentation where necessary; use captured, clearly dated artifacts if a live stage is delayed.

## Safe cloud activation and recovery

Deploy the backwards-compatible Lambda package first, without changing authentication, IAM, API routes or the existing catalogue. Verify existing endpoints and denied unauthenticated requests. Merge/review the pipeline, obtain real Environment approval and verify the new catalogue and manifest. Only then plan the `governance_frontend_mode = "resources"` change: expect one existing Amplify main-branch environment update, no creates/destroys, no Cognito/API/DynamoDB/IAM changes. Apply only a reviewed non-destructive plan and build the frontend through Amplify.

Keep the previous Lambda artifact and existing frontend mode for operational recovery. Reverting the console activation restores the old console without touching either dataset. Data rollback uses a normal reviewed Git revert and protected publication. No enterprise deployment, resource remediation or Terraform apply occurs in the governance-data workflow.

## Reproducing the 100-account fleet

There are 100 current accounts in total, not 100 additional accounts. `mock-aws-resources/` is the single editable current fleet. The original ten account/resource records, including Booking API and the Production 18-hour EBS observation, are retained unchanged. Ninety deterministic workload accounts extend that inventory; fixed ten-account test scenarios and immutable historical snapshots are regression/audit evidence, not another active fleet.

To reproduce the initial extension without changing source files or contacting AWS:

```sh
.venv/bin/python -m deployment.generate_synthetic_fleet
```

This writes preview JSON to ignored `artifacts/synthetic-fleet/`. Do not regenerate over an operator's later observation changes. Normal demonstrations still edit only the Booking API attribute in `mock-aws-resources/resources.json`.

Real Terraform plans all 100 accounts and checks every environment/control/approval assignment against Python. The same bounded atomic API snapshot feeds summary, account details, filters and client-side pagination; no per-page cloud scans or separate data source is introduced. Page-size controls offer 5/10/25/50 rows with first/last navigation. Refresh clamps pagination if a restored dataset has fewer records. Large publication entries collapse, while single-resource changes remain visible.

Capacity is bounded at 100 accounts, 200 resources and 200 KB of canonical snapshot JSON including the Terraform receipt. Each immutable DynamoDB payload remains below the 400 KiB item limit, and its two-item strongly consistent query remains below the 1 MiB query-page limit. The catalogue retains its 300 KB/128-event budget and 200 changes per event; oversized changes fail before writes. API views have an additional 2 MB budget, below Lambda's synchronous response limit. This is a 100-account synthetic demonstration, not unbounded enterprise ingestion.

Deploy the validated backwards-compatible Lambda package before approving the 100-account publication: the previous deployed validator permits only 25 accounts. Expect exactly one Lambda code update and zero other resource changes. Keep existing Current untouched until that code is verified, then use the normal protected publication. No table migration, new IAM permissions or enterprise resources are required.

After promoting 100 accounts, retain a 100-account-capable reader during normal Git rollback. Revert the individual observation change, not the fleet-extension commit. The previous 25-account validator cannot read a 100-account snapshot. The demonstrated rollback keeps the complete fleet and changes only Booking API evidence.
