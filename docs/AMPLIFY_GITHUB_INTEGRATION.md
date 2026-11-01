# Existing-app migration: manual hosting to GitHub

## Verified state and scope

Migration history: the app originally had no repository and one manually deployed `poc` branch. The first repository update returned: **Cannot connect your app to repository while manually deployed branch still exists.** The app retains `module.hosting.aws_amplify_app.console`; the failed update also recorded the requested repository/token before AWS accepted the connection. State is not proof of a successful repository connection: verify with AWS `get-app`.

Keep the existing app ID, pool/client, API, Lambda, DynamoDB, IAM, security headers and rewrite. Never create a second app or replace the first. The app retains `prevent_destroy=true`. Removal of `poc` causes downtime and removes its hosted content; recovery is not automatic. Stage A was executed and verified in AWS; the owner subsequently reports the repository connection and main creation succeeded. These completed infrastructure operations are not repeated during source release preparation.

## Stage D release status (2026-11-01)

The owner reports the existing application is connected to the intended repository and its main branch exists, serving the default Welcome page. A release build has not been deployed. **Do not rerun Stages A–C** for source publication. This preparation does not independently query or change AWS. Review and merge the source PR first; then obtain separate authorization for the first release job. Keep `VITE_GOVERNANCE_API_MODE=baseline-v1` and automatic builds disabled. The Lambda upgrade/V2 activation remains a separate release.

## Ordered checkpoints

`hosting_migration_stage` defaults to `legacy`. For the completed infrastructure migration, ignored local settings are now at **create_main**. `enable_github_hosting=true` arms migration but no longer skips its checkpoints. Keep automatic builds false throughout migration.

| Stage | Terraform value | Required resource actions |
| --- | --- | --- |
| Before migration | `legacy` | Keep manual poc; do not connect repository or create main. |
| A | `retire_manual` | **0 create, 0 update, 1 destroy**, only `aws_amplify_branch.poc[0]`. |
| B | `connect_repository` | After A: **0 create, 1 in-place app update, 0 destroy**; no branches. |
| C | `create_main` | After B: **1 create (main), 2 updates (Cognito URLs/API CORS), 0 destroy**. App is unchanged. |
| D | Keep `create_main` | Separately authorized Amplify Git-based build/deployment; not Terraform provisioning. |

A `moved` block maps the original branch address `aws_amplify_branch.poc` to `aws_amplify_branch.poc[0]` so the retirement switch does not recreate it. The app's address is unchanged. Keep the migration stage at the last completed checkpoint in your ignored `settings.auto.tfvars`; do not return to legacy or disable migration as casual rollback.

**Separate plans/applies and inventory checks are mandatory.** A static dependency cannot safely turn AWS's manual-branch deletion prerequisite into an all-in-one migration. The plan inspector rejects combined branch retirement/app update/main creation. Never use `-target`, replace the app, or apply an obsolete combined plan.

## Stage A — completed; historical procedure only

The failed update left a token in state. Passing null or a different token could plan an unrelated app update while deleting the branch. The read-only planning helper preserves that existing input **in memory**, suppresses debug logs/full output, writes only a protected ignored plan and rejects any non-branch change. It never applies or writes state.

```sh
.venv/bin/python -m scripts.plan_amplify_retirement
# Required result: Stage A verified: 0 creates, 0 updates, 1 destroy.
```

The plan is `artifacts/amplify-retire-manual.tfplan` (mode 600). It contains state/secret inputs: never print or upload it. It was generated with read-only refresh and `-lock=false` to avoid state-lock writes during investigation. Do not run concurrent Terraform operations; regenerate/reinspect if state or configuration changes. The following destructive command is **only for separately confirmed Stage A execution**:

```sh
AWS_PROFILE=north terraform -chdir=terraform/poc apply ../../artifacts/amplify-retire-manual.tfplan
```

Then verify inventory before proceeding:

```sh
AWS_PROFILE=north aws amplify list-branches --app-id d1eetlse86595h --region eu-central-1 --query 'branches[].branchName'
# Required: []
AWS_PROFILE=north aws amplify get-app --app-id d1eetlse86595h --region eu-central-1 --query 'app.{id:appId,repository:repository}'
# Required: same app ID, repository still absent.
```

## Stage B — connect after the branch inventory is empty

AWS provider 6.71.0 updates repository/build/token via UpdateApp. It sets AccessToken **only if Terraform detects a change**. Because the failed apply recorded the prior token, resupplying that exact value may produce a repository update with no token. The Stage B guard rejects that plan. Use an owner-approved valid changed setup-token input from a secure source; do not create/revoke tokens as an unreviewed side action. Do not print it or place it in tfvars/CLI arguments. Supply it through `TF_VAR_github_access_token` with no echo/debug logs. Provider sensitivity is not write-only: plans/state and old versions can retain it.

Persist `hosting_migration_stage="connect_repository"` after A has completed, then:

```sh
umask 077
AWS_PROFILE=north terraform -chdir=terraform/poc plan -input=false -out=../../artifacts/amplify-connect-repository.tfplan
.venv/bin/python -m scripts.inspect_amplify_migration --stage connect_repository --plan artifacts/amplify-connect-repository.tfplan
# Must report app-only update and Token will be sent: True.
# Only after separate approval of that exact plan:
AWS_PROFILE=north terraform -chdir=terraform/poc apply ../../artifacts/amplify-connect-repository.tfplan
AWS_PROFILE=north aws amplify get-app --app-id d1eetlse86595h --region eu-central-1 --query 'app.{id:appId,repository:repository,autoBuild:enableBranchAutoBuild}'
# Required: original ID, exact GitHub URL, autoBuild false.
```

The repository must equal `https://github.com/bosphorus-cloud-labs/northstar-airlines-aws-landing-zone`; branch inventory must still be empty. Do not infer success from Terraform's saved values. If a changed valid token cannot be supplied, stop: an explicitly authorized direct UpdateApp followed by a fresh Terraform read/reconciliation is an alternative, not an automatic fallback. It must follow Stage A, supply token securely and preserve the ID/settings; no import or state removal is necessary for that alternative. Do not blindly unset the token and apply: this provider can send an empty token on removal.

## Stage C — main, identity/CORS and deployment settings

After B is confirmed in AWS, persist `hosting_migration_stage="create_main"`. Keep `github_auto_build_enabled=false` and `github_baseline_compatibility=true`.

```sh
AWS_PROFILE=north terraform -chdir=terraform/poc plan -input=false -out=../../artifacts/amplify-create-main.tfplan
.venv/bin/python -m scripts.inspect_amplify_migration --stage create_main --plan artifacts/amplify-create-main.tfplan
# Required: 1 branch create, 2 identity/CORS updates, no app change or deletion.
# Only after separate approval:
AWS_PROFILE=north terraform -chdir=terraform/poc apply ../../artifacts/amplify-create-main.tfplan
AWS_PROFILE=north aws amplify list-branches --app-id d1eetlse86595h --region eu-central-1 --query 'branches[].{branch:branchName,autoBuild:enableAutoBuild}'
```

Required: main only, auto-build false. The main origin is `https://main.d1eetlse86595h.amplifyapp.com`; callback is `/auth/callback`, logout is `/`. Existing URLs/additional origins are retained, not replaced. The old poc URLs are temporarily inert; later cleanup is a separate reviewed change. Pool/client IDs, scopes, read-only gateway authorization and backend roles are unchanged.

Root output `github_frontend_settings` supplies the original six public connection settings plus `VITE_GOVERNANCE_API_MODE=baseline-v1`. All are build-time public values, never tokens. Main additionally has `AMPLIFY_MONOREPO_APP_ROOT=frontend`. Hostname → identity/CORS → branch settings avoids a cycle; identity/API values are not fed back into app configuration.

## Stage D — publish compatible source, build and verify

The deployed Lambda SHA matches the existing ZIP; static inspection confirms it lacks the newer Current/History summary fields. **Do not change Lambda during this hosting migration.** The user-approved frontend compatibility path is implemented as explicit `baseline-v1` mode: no catalogue/version query parameters, fixed V1 reference time, baseline-only labeling, disabled history selection and normal authenticated API reads. API/authentication errors remain visible; there is no automatic data fallback. Default `catalog` mode and the full V2/current/history features remain intact for local use and the separate backend upgrade.

The reviewed fallback and `amplify.yml` must reach GitHub **main** through a reviewed pull request before the first build. Source release preparation permits a feature-branch commit/push and PR, but never automatic merge or an Amplify build. Amplify builds main, not an uncommitted feature checkout. This is a release prerequisite, not a reason to deploy unrelated backend changes.

The existing monorepo build specification installs Node 24.19.0, runs npm ci, TypeScript checks, lint, tests and the production build from frontend, then serves dist. Once A–C and source publication are verified, the following command requires separate build/deployment authorization:

```sh
AWS_PROFILE=north aws amplify start-job --app-id d1eetlse86595h --branch-name main --job-type RELEASE --region eu-central-1 --query 'jobSummary.{id:jobId,status:status}'
AWS_PROFILE=north aws amplify get-job --app-id d1eetlse86595h --branch-name main --job-id JOB_ID --region eu-central-1 --query 'job.summary.{id:jobId,status:status}'
```

Confirm SUCCEED, then open the main URL. Verify Cognito PKCE/MFA sign-in/logout, reader permissions, all six pages, 10 synthetic accounts, expected baseline finding counts (31/3/6/10), API errors and visible **V1 backend compatibility mode / SIMULATED DATA**. Verify unauthenticated governance reads remain denied. No Current/V2 claim is made by compatibility mode. Old poc is intentionally unavailable after A. Actual build, browser authentication and end-to-end reporting remain unverified until this authorized stage.

Later, separately upgrade/test the Lambda catalogue backend without publishing V2 data implicitly. After acceptance set `github_baseline_compatibility=false`, review the main environment-only change, then rebuild the frontend to select full catalogue behavior. V2 source/functionality is retained throughout. Automatic builds may be reviewed separately after migration; never enable app-wide builds or pretend this is a production approval gate.

## Failure recovery and evidence

If B fails after A, keep the app and shared services; do not recreate the manual branch while trying repository connection. Downtime persists until the connection/main deployment succeeds or a separately approved manual-hosting recovery is performed. A branch recreation alone cannot restore deleted content. If D fails, inspect build errors and use an approved compatible frontend revision; do not change authentication or seed data as a workaround. Preserve protected plans/logs locally and never attach secrets or raw state to support tickets.

During migration preparation only Stage A could be verified against live starting state; future B/C plans required the preceding stage to complete. The stage guards remain available for future reviewed migrations. The owner now reports A–C complete; source release preparation uses validation/mock plans only. Do not label hypothetical future-state plans as live verification.

```sh
terraform fmt -check terraform/poc terraform/poc/tests terraform/modules/poc_hosting
terraform -chdir=terraform/poc validate
mkdir -p artifacts/validation
terraform -chdir=terraform/poc test -json -verbose > artifacts/validation/migration-tests.jsonl
python terraform/poc/tests/check_origin_plans.py artifacts/validation/migration-tests.jsonl
python terraform/poc/tests/check_github_hosting_plans.py artifacts/validation/migration-tests.jsonl
```

References: [AWS UpdateApp](https://docs.aws.amazon.com/amplify/latest/APIReference/API_UpdateApp.html), [provider 6.71.0 implementation](https://github.com/hashicorp/terraform-provider-aws/blob/v6.71.0/internal/service/amplify/app.go), [AWS GitHub App setup](https://docs.aws.amazon.com/amplify/latest/userguide/setting-up-GitHub-access.html), [Amplify StartJob](https://docs.aws.amazon.com/amplify/latest/APIReference/API_StartJob.html).
