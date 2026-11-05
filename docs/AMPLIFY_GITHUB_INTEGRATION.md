# Existing-app Amplify GitHub integration

The migration is complete: the existing Amplify app `d1eetlse86595h` is connected to the NorthStar GitHub repository and serves branch `main`. The app ID and `module.hosting.aws_amplify_app.console` resource address were preserved; no replacement app was created. Current acceptance and automatic-build evidence are in [deployment acceptance](DEPLOYMENT_ACCEPTANCE.md), and normal data publication is in [delivery operations](GOVERNANCE_DELIVERY.md).

## Current configuration

- Keep `enable_github_hosting=true` and `hosting_migration_stage=create_main` for this migrated deployment. Default `legacy` supports unmigrated module callers; it is not the live configuration or a casual rollback option.
- Main builds from `frontend/` using the root build specification and Terraform-exported public Cognito/API/origin settings. `github_baseline_compatibility=false` selects the deployed catalogue API.
- `github_auto_build_enabled=true` enables only main; app-wide automatic builds and PR previews stay disabled. GitHub PR/CI protection precedes main merges. Frontend builds do not run Terraform or publish governance data.
- Existing Cognito callback/logout URLs and exact-origin API CORS include main. Legacy poc URLs remain retained but inert; removing them is a separate reviewed identity/CORS change.
- GitHub App authorization is a one-time external setup step. Never hardcode credentials or treat a recorded Terraform token as evidence that AWS successfully connected the repository.

## Historical migration checkpoints — do not rerun

AWS rejected UpdateApp while a manually deployed branch existed. Ordering required distinct reviewed plans rather than one apply combining branch deletion and app connection.

| Checkpoint | Terraform setting | Required scope at that historical starting state |
| --- | --- | --- |
| Original manual hosting | `legacy` | Keep poc; no repository/main creation |
| Retire manual branch | `retire_manual` | Destroy only `aws_amplify_branch.poc[0]`; app/backend unchanged |
| Connect existing repository | `connect_repository` | Update existing app in place; no branches created |
| Create Git branch/config | `create_main` | Create main; update Cognito URLs and CORS consistently |
| Frontend release | Retain `create_main` | Separate Git-based build, then verify authentication/API |

The `moved` block preserves the original branch address when introducing its conditional index. `prevent_destroy` protects the existing app. Returning to legacy or disabling integration could propose a new manual branch or removal of main; that is not recovery for a frontend/data incident.

Hosting-plan regression tests retain the historical scope safeguards. The standalone migration operator commands were retired after migration. Future changes require a fresh scoped plan and authorization.

## Token and plan handling

Provider 6.71.0 sends the setup AccessToken only when Terraform detects that sensitive attribute changed. An interrupted/rejected update can leave its value recorded in state without a connected repository. Future authorized reconnection work must verify actual AWS repository metadata and inspect sensitive-input presence without printing it; do not rotate/revoke/retry tokens automatically.

State, saved plans, token-bearing inputs and generated local settings stay private/ignored. The read-only retirement planner preserves a recorded token only in process memory to avoid unrelated plan drift and suppresses raw state/plan output. This does not authorize any apply, branch deletion, API write or build.

## Recovery and verification

For governance-data incidents, use approved registered-snapshot reselection; for frontend incidents, use a reviewed source fix/release or authorized known-good Amplify release. Neither requires replacing the app, deleting main, changing Cognito users or rewriting immutable V1/V2. Keep exact callback/logout/CORS/build origins aligned for any separately approved domain change.

Verify the actual app ID/repository, main branch/build commit, public build settings, authenticated API pages, denied access and Current/history after an authorized release. Offline mock plans validate structure only. The first AWS deployment and repository-authorization limitations remain engineering provenance; current operating status is established by the live acceptance record, not those historical proposals.
