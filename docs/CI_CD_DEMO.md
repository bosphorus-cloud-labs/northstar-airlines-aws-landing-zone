# CI/CD: safe edit, PR, real approval and reporting

## What is integrated

| Connection | Actual boundary |
| --- | --- |
| Feature branch → PR/main CI | GitHub Actions runs Python/schema/security checks, frontend checks, real provider-free Terraform fmt/init/validate/plan/parity and POC mock-provider tests. Read-only permissions; no AWS/OIDC identity. |
| Main → data CD | Explicit dispatch, exact commit/CI/PR/digest checks, governance-production approval, then short-lived OIDC data-only role. No automatic infrastructure deployment on push. |
| CD → DynamoDB → console | Manifest-last conditional immutable publication, strong digest verification, atomic generation-checked Current/History. Existing authenticated API/React application reads it; no frontend rebuild per policy snapshot. |
| GitHub main → Amplify frontend | Existing connected app/main branch with main-only auto-build enabled; app-wide auto-build remains disabled. Amplify builds frontend only, not Terraform. |
| Local demo → live AWS | No connection: demo.sh changes local immutable files/Current only. |
| Account rollout → compliance | Synthetic canary/waves/failure/retry/onboarding; successful distribution does not imply passing evidence. |

See [real execution evidence](DEPLOYMENT_ACCEPTANCE.md) and [five-minute screen script](INTERVIEW_DEMO.md). The POC is explicitly single-owner: PR plus strict CI is required; the owner supplies actual environment approval with self-review permitted, administrator bypass disabled and main-only deployment. No independent review is claimed. Default independent-review mode remains available for enterprise teams.

## Beginner-friendly PR exercise — before presenting

This harmless comment demonstrates source delivery without inventing a new security requirement or changing infrastructure. Run it once on a fresh feature branch; keep CI outside the five-minute presentation.

```sh
git switch main
git pull --ff-only
git switch -c feat/interview-governance-proposal
printf '\n# Central desired settings are validated before simulated distribution.\n' >> terraform/modules/simulated_governance/main.tf
terraform fmt terraform/modules/simulated_governance
git diff --check
git diff -- terraform/modules/simulated_governance/main.tf
git add terraform/modules/simulated_governance/main.tf
git diff --cached --check
git commit -m "docs: explain governed configuration validation"
git push -u origin feat/interview-governance-proposal
gh pr create --base main --head feat/interview-governance-proposal \
  --title "Explain governed Terraform configuration" \
  --body "Comment-only demonstration of the protected PR and real offline CI path; no infrastructure change."
```

Open PR → Checks → Governance checks/Frontend checks. Inspect the completed Terraform plan/parity step, synthetic failure/retry report, candidate digest and artifacts. Fix failures on the feature branch; do not force-push main or use admin bypass. Merge only after required checks and the configured approval model are satisfied. A real new policy also needs reviewed profile/environment/scenario/contracts updates; a comment is not such a policy change.

The existing V2 digest is already immutable and bound to its original publication source. Do not use a new comment-only merge to rebind/re-publish V2. Use the registered-revision selection procedure to demonstrate rollback/restoration, or implement a genuinely new version under reviewed contracts.

## CD outside the presentation

Use [the exact publication/recovery procedure](GOVERNANCE_DELIVERY.md) and the expected live generation. GitHub → Actions → Approved synthetic governance delivery → Run workflow on main. Supply action, exact current main SHA, approved digest and observed generation. Wait for CI/security gate, then the owner selects Review deployments → governance-production → Approve and deploy. The agent must not approve for the owner. Verify the receipt, strong catalogue history and live Current before claiming success.

Artifacts contain enumerated synthetic plan/reports/candidates/receipts. Terraform state, binary infrastructure plans, package ZIPs, local settings and credentials must never be uploaded. CI uses pull_request, never privileged pull_request_target; pinned action revisions and no persisted checkout credentials protect public-repository CI. Only the protected publication job requests an OIDC token. Actual workflow and live acceptance links are in the acceptance record; mock plans are not cloud deployment proof.

## Enterprise AWS fit — documented design, not deployed

A real enterprise path is reviewed source → CodePipeline/CodeBuild validation and revision-bound Terraform plan → IAM-authorized manual approval → controlled approved apply/customization → published deployment/evidence read model. CodePipeline may notify subscribed approvers through an SNS topic in the pipeline Region. Approval resumes the pipeline; rejection stops it. See [AWS manual approval/SNS documentation](https://docs.aws.amazon.com/codepipeline/latest/userguide/approvals.html).

Account Factory provisions/enrolls accounts; AFT customizes approved account baselines; central Organizations pipelines own SCP/attachments with separate states/roles. Canary/wave controls stop on failure and support recovery. The reporting browser/Lambda never gains deployment authority. CodePipeline, CodeBuild, SNS, Control Tower, AFT and Organizations resources are not deployed by this POC. The real GitHub OIDC data publication must not be confused with those enterprise services or synthetic account distribution.
