# Local Demonstration and Console Validation

For the simplified resource-change demonstration, start with [Resource Compliance Operations](RESOURCE_COMPLIANCE_OPERATIONS.md#five-minute-operational-demonstration). The procedures below preserve the earlier account-policy rollout rehearsal and recovery path.

The governance console displays inventory, policy requirements, rollout outcomes and compliance evidence in one read-only application. Current/History select governance snapshots, not application releases. Account distribution and compliance evidence are synthetic; [deployment validation](DEPLOYMENT_ACCEPTANCE.md) records the separate GitHub approval, OIDC publication and recovery results.

## Local demonstration

Install the dependencies described in the [README](../README.md#run-locally), then run from the repository root:

```sh
./demo.sh v1       # Start the local baseline and loopback application servers.
# In a second terminal:
./demo.sh v2       # Validate the proposed policy and simulate its rollout.
./demo.sh reset    # Restore local Current to V1 without deleting history.
```

Open http://127.0.0.1:5173 and refresh after a rollout or reset. The launcher reuses only its owned loopback servers. It runs Terraform fmt/init/validate/plan and parity checks, followed by simulated approval, a Development canary, controlled failure/retry and synthetic account onboarding. Results are written to ignored immutable local artifacts. The browser reads the local Python API; there is no separate frontend-only mock source.

`./demo.sh v2 --prepare-only` generates local results without starting servers. None of these commands publishes DynamoDB records, changes the AWS-hosted console or provisions resources. The [policy rollout guide](POLICY_ROLLOUT_DEMO.md) provides individual commands and expected outputs.

## Console validation

For AWS-hosted validation, use the [authenticated console](https://main.d1eetlse86595h.amplifyapp.com/) and an invited Cognito reader. Tokens remain in memory; reload or expiry may require sign-in through Cognito SSO. Keep credentials, state and saved plans private.

| View | Expected behavior |
| --- | --- |
| Overview / Current | Policy 2.0.0 contains 11 synthetic accounts and 66 findings: 43 compliant, 4 noncompliant, 9 unknown and 10 stale. Compare the selected revision and evaluation time with the acceptance record. |
| Historical snapshot / policy 1.0.0 | The immutable baseline contains 10 accounts and 50 findings. Selection is read-only and performs no rollback or deployment. |
| Deployments | Targets and stages retain simulated approval, canary, failure, retry and onboarding outcomes. Terraform planning is distinguished from simulated account distribution. |
| Compliance / Configuration Drift | Desired state, observed configuration, distribution success and compliance evidence remain separate. Missing and stale evidence never count as compliant. |
| Governance Exceptions | Approved and expired exceptions retain the original violation. The application cannot approve exceptions. |
| Accounts / sim-account-011 | The synthetic account added under V2 has account-specific requirements and findings. It is absent from V1. |

At smaller widths, use **Toggle navigation** to open the sidebar. Current polls every 30 seconds while the page is active; use **Refresh current state** if background timers have paused. Snapshot promotion needs no frontend rebuild. Historical comparison stays selected until Current is chosen; a new application load defaults to Current.

## Publication and recovery validation

Console selection and local reset do not publish or roll back cloud data. Only an authorized operator should dispatch [protected data CD](GOVERNANCE_DELIVERY.md). Verify the current merged source SHA, successful CI, approved digest and observed catalogue generation before requesting the required GitHub environment approval.

To reselect the registered V1 snapshot, replace `LIVE_GENERATION` with the observed generation:

```sh
main_sha=$(gh api repos/bosphorus-cloud-labs/northstar-airlines-aws-landing-zone/commits/main --jq .sha)
gh workflow run governance-cd.yml --ref main -f action=rollback \
  -f source_sha="$main_sha" \
  -f snapshot_digest=08456a729e0dbe3b2bf36f02f79baa4778a8eaf518d1761831607fbf08de97dd \
  -f expected_generation=LIVE_GENERATION
```

The same rollback action can restore registered V2 using digest `1e00c3c3e1919a59dd16a83f092d1c2bab2cdff68c0999c33cb1735822098fc5` and the newly observed generation. It updates Current/history without rewriting snapshot records. Do not republish registered V2 from a different commit: immutable source provenance cannot be rebound. A new policy requires a reviewed profile and a distinct version/digest.

After an approved operation, inspect the delivery receipt, strongly verified catalogue/history and console Current state. Completed [deployment evidence](DEPLOYMENT_ACCEPTANCE.md) provides the bootstrap, publication, rollback and restoration records. Do not execute publication or recovery solely to browse historical data.

## Offline validation

If cloud access is unavailable, use the local API/console and previously generated synthetic plan/report artifacts. Clearly identify local or previously captured results; they are not fresh AWS compliance observations. Recovery must retain approval and integrity checks rather than bypassing them.

See [CI/CD Operations](CI_CD_OPERATIONS.md) for source review, validation artifacts, approval boundaries and the proposed enterprise delivery design.
