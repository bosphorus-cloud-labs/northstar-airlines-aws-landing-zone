# Synthetic resource compliance operations

## Scope and activation

The resource console adds a simple Git-based change workflow to the existing application. It is staged behind `governance_frontend_mode = "resources"` (`VITE_GOVERNANCE_API_MODE=resources` in the frontend). The default remains `catalog` so merging the code does not replace the deployed console before backend compatibility and protected data publication are verified. Existing API contracts, authentication, snapshots and account-governance demonstrations remain available.

Implementation and offline acceptance are separate from deployment acceptance. Until a successful protected resource-publication run and authenticated cloud check are recorded, this feature is **locally tested, not verified live**. Existing acceptance evidence in [DEPLOYMENT_ACCEPTANCE.md](DEPLOYMENT_ACCEPTANCE.md) applies to the earlier catalogue.

## Files an operator edits

| File | Purpose |
| --- | --- |
| `mock-aws-resources/resources.json` | Synthetic resource observations and explicit evaluation time; edit configuration attributes, never precomputed compliance statuses. |
| `mock-aws-resources/accounts.json` | Synthetic account inventory and four environment/OU assignments. |
| `compliance-rules/resource-controls.json` | Central baseline: IMDSv2 required, S3 public access blocked and EBS encryption enabled; environment-specific evidence freshness. |
| `terraform/modules/simulated_governance/main.tf` | Existing reusable, provider-free desired-state module. |
| `terraform/simulation/main.tf` | Existing planning root, extended with optional resource/control inputs. |

Production, Pre-Production, Testing and Development use 24, 48, 72 and 168-hour evidence limits respectively. Production and Pre-Production inherit approval intent from the account-governance baseline. Real publication into the POC always additionally requires GitHub Environment approval, regardless of the target environment. These are synthetic requirements, not deployed SCPs.

## Real Terraform connection

`deployment.resource_plan.prepare` validates inputs, freezes the existing rollout proposal, executes real `terraform fmt`, `init -backend=false`, `validate`, and `plan -refresh=false`, then reads the plan with `terraform show -json`. It rejects cloud resources, providers, data sources and remote backends. It compares **every account, environment, approval requirement and control assignment** to Python's desired projection. The release includes that verified receipt bound to the exact input content. The dashboard only reports Terraform verification when that receipt exists. Local raw fixtures explicitly report that Terraform has not run.

The Terraform plan represents desired configuration. It does not provision or remediate anything. The Python engine evaluates synthetic observed configuration independently. Configuration distribution success never changes missing, stale or failing evidence into a pass. Existing `demo.sh` and the tested rollout engine retain canary, controlled failure, retry and onboarding for deeper operational demonstrations.

## Protected delivery

1. A feature PR runs the existing credential-free governance CI, including schemas, security, all Python tests, frontend tests, real Terraform planning and complete parity.
2. CI produces `resource-release-<source SHA>`: a commit-bound release, readable Terraform plan and compliance report. It contains synthetic data, not state or credentials.
3. After successful **push-to-main** CI, the existing delivery workflow verifies the exact run, repository, protected main commit, merged PR and approval model. Fork/PR validation runs cannot publish. Documentation-only merges do not request resource publication.
4. The publisher job waits for the actual `governance-production` approval. The explicitly documented single-owner POC model permits owner review; administrator bypass and non-main deployment remain prohibited.
5. Only then is the existing least-privilege OIDC role assumed. The job revalidates provenance before requesting credentials and rechecks current main immediately before writes and promotion. No long-lived AWS credentials are introduced.
6. Immutable records are inserted conditionally, manifest last, then read strongly and integrity-checked. A conditional catalogue update selects Current and appends before/after audit records. A failed/partial load cannot promote Current. Already-current data is a verified no-op.

The new catalogue uses `GOVERNANCE#CATALOG / RESOURCE-COMPLIANCE`. The existing `STATE` catalogue and all historical snapshots remain untouched. Snapshot identifiers and internal compare-and-swap generations remain implementation details; users do not manage them. A Git revert reuses immutable content and records a new approved publication event. A bounded history of 128 publications and 25 accounts/100 resources intentionally limits this POC; indexed fleet-scale storage and archival are future work.

Use the existing delivery workflow's `resources` action on main only for a controlled baseline retry; source SHA and content identity are selected and verified automatically. Older dispatch actions remain available for the preserved catalogue recovery procedure, not the new presentation workflow.

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

Open http://127.0.0.1:5173. The local backend reads current source fixtures, on every request, so refresh the browser after editing fixtures. Local data is labelled **not published** and has no fabricated GitHub approval history or Terraform receipt. Cloud data changes require the protected pipeline.

## Five-minute operational demonstration

Prepare successful baseline publication and cloud activation before presenting. Keep the CI artifact/report and a captured publication receipt available so the demonstration does not rely on waiting for a runner.

1. **Overview (45 seconds):** show the four environments, resource totals and Terraform verification. Say: “Terraform calculates the desired baseline across synthetic accounts. The same input is checked against observations by the compliance engine.”
2. **Resources (45 seconds):** search `Booking API`. Its EC2 metadata setting is `required`; the IMDSv2 control is compliant. Show desired, observed and evidence time. Point out the separate noncompliant, unknown and stale examples.
3. **Git change and CI (90 seconds):** in VS Code edit only `mock-aws-resources/resources.json`: for `sim-ec2-001`, change `configuration.metadata_options.http_tokens` from `required` to `optional`. On a fresh feature branch run:

   ```sh
   git switch -c demo/metadata-regression
   git diff -- mock-aws-resources/resources.json
   git add mock-aws-resources/resources.json
   git commit -m "demo: allow optional metadata tokens on synthetic booking API"
   change_commit=$(git rev-parse HEAD)
   git push -u origin HEAD
   gh pr create --base main --title "Demo: synthetic metadata regression" --body "Synthetic observation only. Expect Booking API to become noncompliant; no AWS resource change."
   ```

   Show completed CI and its readable provider-free Terraform plan. This is a valid observation of an insecure configuration; validation must accept it and report the violation. CI rejects invalid schema or unsafe baseline weakening, not all negative observations.
4. **Approved publication (60 seconds):** merge through protected PR checks, approve the real Environment deployment when GitHub prompts, then refresh the console. Booking API becomes noncompliant because optional metadata tokens allow IMDSv1. Publication history records the old/new setting and status. No frontend rebuild is required to read new data (Amplify may independently rebuild on main pushes).
5. **Git rollback (60 seconds):** after the change has merged, create a fresh branch from updated main and revert the original data commit:

   ```sh
   git switch main
   git pull --ff-only
   git switch -c demo/restore-metadata-requirement
   git revert "$change_commit"
   git push -u origin HEAD
   gh pr create --base main --title "Restore synthetic IMDSv2 compliance" --body "Revert the synthetic metadata change; expect Booking API compliant again after protected publication."
   ```

   After protected merge/CI/approval, refresh. Show **compliant → noncompliant → compliant** in activity. Do not reset Git history or edit DynamoDB directly.

The shell variable survives only in the original terminal; otherwise copy the original data commit SHA from the PR. If the PR was squash-merged and the original commit differs from the merged data change, use the squash commit shown on main. Review the revert diff before pushing.

**Fallback:** show pre-generated CI plans, compliance reports and publication receipts, then demonstrate the same edit with the local API. Clearly call it local/captured evidence; do not claim failed live publication succeeded. CI and manual approval latency are outside a guaranteed five-minute live window.

## Safe cloud activation and recovery

Deploy the backwards-compatible Lambda package first, without changing authentication, IAM, API routes or the existing catalogue. Verify existing endpoints and denied unauthenticated requests. Merge/review the pipeline, obtain real Environment approval and verify the new catalogue and manifest. Only then plan the `governance_frontend_mode = "resources"` change: expect one existing Amplify main-branch environment update, no creates/destroys, no Cognito/API/DynamoDB/IAM changes. Apply only a reviewed non-destructive plan and build the frontend through Amplify.

Keep the previous Lambda artifact and existing frontend mode for operational recovery. Reverting the console activation restores the old console without touching either dataset. Data rollback uses a normal reviewed Git revert and protected publication. No enterprise deployment, resource remediation or Terraform apply occurs in the governance-data workflow.
