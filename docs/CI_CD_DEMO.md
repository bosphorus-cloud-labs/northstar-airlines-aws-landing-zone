# CI/CD and five-minute interview — quick runbook

## What exists now

One read-only React console shows Current governance, historical policy snapshots, rollout outcomes, account compliance and drift. `demo.sh` performs real provider-free Terraform checks and a deterministic **simulated** rollout. This change adds the `Governance checks` GitHub Actions job. Its source and commands are verified locally; **no hosted Actions run, commit, push, PR, AWS operation or publication was performed by this task**.

The workflow covers PR changes to the governance/module/simulation/backend/tests and has a manual trigger. It has read-only repository permission, immutable action pins, no persisted checkout credentials, no secrets/OIDC/AWS role, no push trigger and no deployment. The static boundary check rejects providers/resources/data/backends before planning. It uses the existing `terraform/simulation` root and reusable module, not a second implementation.

## Before the presentation — after source review/authorization

Do this in advance, not during the five minutes. Keep the branch; do not merge main yourself. All outstanding console changes must be reviewed/committed too, not only the workflow.

```sh
# Confirm the output says codex/interview-demo. Stop if it says main.
git status --short --branch
# Safe comment-only Terraform edit: demonstrates PR delivery, not a new security control.
printf '\n# Interview example: reviewed policy changes stay provider-free.\n' >> terraform/modules/simulated_governance/main.tf
terraform fmt terraform/modules/simulated_governance
git diff --check
git diff --stat
# Only after ALL listed source changes have been reviewed; never stage state/credentials/artifacts.
git add -A
git diff --cached --check
git diff --cached --stat
git commit -m "feat: integrate governance CI and interview demonstration"
git push -u origin codex/interview-demo
gh pr create --base main --head codex/interview-demo --title "Governance CI and interview demo" --body "Offline Terraform validation, parity checks and simulated rollout reporting. No AWS deployment or publication."
```

`gh` requires the GitHub CLI and GitHub sign-in (no AWS identity). Without it, use the compare/PR link printed by `git push`, choose base **main**, and create the PR in GitHub. These commands are instructions for a later authorized action; they have **not** been executed here.

Open the PR → **Checks → Governance checks → Details**. Wait for its completed result before rehearsal. Review the plan/parity and test steps, job summary and `governance-review-...` artifact. Download it before presenting; artifacts expire after seven days. If a check fails, fix it on this feature branch and push normally. A failed check is not a green demo. Have a reviewer approve the PR; no automatic merge is implemented. Repository protection settings were not inspected or configured. An owner should enforce review/check policy before merging; path-filtered checks must not be made globally required for unrelated PRs without addressing skipped/pending checks.

The comment edit only demonstrates the delivery process. The actual V1→V2 security requirement is already defined in `governance/policies/v2.json`; the real plan compares those frozen requirements with the Python simulation.

Prepare the console and fallback in advance:

```sh
./demo.sh v2 --prepare-only
./demo.sh v1
```

Leave the baseline server Terminal running; open http://127.0.0.1:5173. Use a second Terminal for the presentation command. Keep the downloaded CI artifact and a completed `artifacts/policy-rollout/interview/run-NNNN/report.json` available. If no hosted run exists, `artifacts/ci/summary.md` is a **local reproduction**, not evidence that GitHub Actions ran.

## Five minutes — no waiting for CI

| Time | Action / concise script |
| --- | --- |
| 0:00–0:45 | Show the **already completed** PR check and artifact. “Terraform formatting, validation, plan and full Python parity checks are real. This job cannot deploy AWS.” If CI is unavailable, show the pre-generated local report and say it is local, not a hosted run. |
| 0:45–1:15 | Show the pure module and environment settings. “Central baseline is inherited. Production/Pre-Production require approval configuration; evidence age varies by environment.” |
| 1:15–2:15 | Show Current baseline in the existing console; run `./demo.sh v2` once. “The same source is validated locally, then approval, canary, failure/retry and onboarding are simulated.” |
| 2:15–3:00 | Refresh the browser once. “The Current marker now selects policy 2.0.0, not a different application. There are eleven synthetic accounts.” |
| 3:00–4:15 | Deployments → rollout targets/stages; Compliance and Drift. “Distribution is not compliance: four findings still fail, nine are unknown and ten stale. Failure/retry history remains visible.” |
| 4:15–5:00 | Accounts → search `sim-account-011` → details; optionally History → baseline. “New-account governance and old immutable evaluations use the same read-only application. No AWS account or workload was changed.” |

If publication/connectivity fails, **do not repair AWS live**. Keep the hosted V1 POC as the unchanged baseline; use the local console or saved report/plan as an explicitly simulated fallback. `./demo.sh reset` returns only local Current to V1 and retains history. See [the detailed console runbook](INTERVIEW_DEMO.md) for local port ownership and reset behavior.

## Honest integration audit

| Connection | Implemented / boundary |
| --- | --- |
| PR → GitHub Actions | Workflow source added; runs after an authorized push/PR and repository Actions approval. Manual dispatch normally needs the workflow on the default branch. No hosted result is claimed yet. |
| Actions → Terraform | Real fmt/init/validate/plan, no provider/resource/data/backend; plan output checked against the same frozen proposal. No apply/destroy. |
| Actions → simulation | Automated synthetic approval, canary, intentional failure (expected exit 2), retry and onboarding; reports/test logs uploaded. No publisher/package or executable binary plan uploaded. |
| Actions → local console | **No automatic transfer.** Local `demo.sh` independently runs the same policy/evaluator/module at the presenter's checkout. Match the reviewed source revision/proposal digest. CI does not move local Current. |
| Local simulation → local console | Implemented: immutable files plus atomic local Current marker; refresh reads it through the API. History remains intact. |
| Actions/local demo → AWS-hosted console | **Not connected automatically.** Separate authorization is needed for code deployment, scoped immutable snapshot publication, reader IAM/registration and Current promotion. Browser/Lambda remain read-only. |
| Tests | CI runs the full Python suite including backend, governance and Terraform integration/parity. Frontend type/lint/tests/build are checked locally for this submission, not in this minimal governance workflow. |
| PR review / production approval | PR review is the source-review process; repository protection is an owner setting, not configured here. A `sim-` approval is not production authorization. |

## Enterprise AWS fit — design only, not deployed

A real enterprise pipeline would be **reviewed source → CodePipeline/CodeBuild validation and revision-bound plan → manual approval → controlled approved deployment → reported evidence/read model**. CodePipeline can pause for an IAM-authorized approver and send an SNS notification to subscribed approvers; the SNS topic must be in the pipeline's Region (Frankfurt here). Approval resumes the pipeline; rejection stops it. See [AWS manual approval/SNS documentation](https://docs.aws.amazon.com/codepipeline/latest/userguide/approvals.html).

The reviewer would inspect the exact plan and artifact revision before a separately scoped deployment role executes it, using canary/waves, stop conditions and recovery. Centrally managed Organizations/SCP delivery and AFT account customizations keep separate ownership/state/roles. A separate authorized publisher would deliver immutable outcomes to the read-only application; the browser and reader Lambda never become deployers. **CodePipeline, CodeBuild, SNS notifications, production approval, enterprise AFT/Organizations execution and automatic cloud publication are not implemented by this workflow.** No such AWS resources were created.

Actions implementation references: [checkout](https://github.com/actions/checkout), [setup-python](https://github.com/actions/setup-python), [setup-terraform](https://github.com/hashicorp/setup-terraform), [artifact upload](https://github.com/actions/upload-artifact). Pins were resolved from public official release refs; upgrades require review. Path filters mean a docs-only PR may not start this job. The workflow uses `pull_request`, never privileged `pull_request_target`.
