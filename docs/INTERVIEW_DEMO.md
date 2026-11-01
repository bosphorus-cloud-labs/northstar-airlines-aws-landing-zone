# Five-minute Emirates interview demonstration

Use the [same authenticated AWS console](https://main.d1eetlse86595h.amplifyapp.com/) throughout. Current/History are governance selections, not application releases. [Deployment acceptance](DEPLOYMENT_ACCEPTANCE.md) records real CI, OIDC publication and rollback evidence; the account rollout and compliance evidence remain synthetic.

## Prepare before presenting

1. Sign in through Cognito with the invited reader account; leave the application active. Tokens are memory-only: after page reload/token expiry, click Sign in again and complete Cognito SSO. Do not expose passwords, tokens, state or plans while screen-sharing.
2. Open completed [main CI](https://github.com/bosphorus-cloud-labs/northstar-airlines-aws-landing-zone/actions/runs/41311346658), [V2 publication](https://github.com/bosphorus-cloud-labs/northstar-airlines-aws-landing-zone/actions/runs/41312091632) and [V1 rollback](https://github.com/bosphorus-cloud-labs/northstar-airlines-aws-landing-zone/actions/runs/41312693235) results. Keep their summaries and synthetic plan/report artifacts ready. The console does not run Terraform or approve deployments.
3. Confirm Current is V2, generation 4 after the completed rollback/restoration rehearsal; consult the acceptance record for the evidence. Do not mutate cloud data for the interview. CI/CD approvals are prepared beforehand, not a five-minute live waiting exercise.
4. Optional offline fallback: from the repository root run `./demo.sh v1` before presenting. Use a second terminal for `./demo.sh v2`; refresh http://127.0.0.1:5173 once. These commands cannot change AWS.

## Five minutes: screens and speaking script

| Time | Action | Concise script |
| --- | --- | --- |
| 0:00–0:45 | Completed PR/CI and publication jobs | “Git validates Python, policy contracts and the real provider-free Terraform plan. CI has no AWS credentials. A separate real environment approval authorizes short-lived OIDC data publication.” |
| 0:45–1:30 | Live Overview → Historical snapshot → policy 1.0.0 | “This immutable baseline has ten synthetic accounts, four environment profiles and 50 findings. Unknown and stale evidence are not compliance passes. History is read-only; choosing it performs no rollback.” |
| 1:30–2:15 | Select Current governance | “The same application selects the approved policy 2.0.0 snapshot. It has eleven accounts and 66 findings: 43 compliant, four failing, nine unknown and ten stale. This data promotion needed no frontend build.” |
| 2:15–3:15 | Deployments → expand targets and stages | “The account distribution is simulated: real Terraform planning, synthetic approval, Development canary, failure before Production, retry and onboarding. The separate GitHub approval and DynamoDB publication really ran.” |
| 3:15–4:15 | Compliance → Configuration Drift → Exceptions | “Desired policy, observed configuration, successful distribution and compliance evidence are separate. Failure/retry history remains; an approved or expired exception never erases a violation.” |
| 4:15–5:00 | Accounts → search sim-account-011 → details; show completed rollback/restoration evidence | “The new synthetic account uses V2. Recovery reselects an already verified immutable revision, keeps History and checks the catalogue generation. Browser and Lambda cannot write or deploy anything.” |

At smaller widths, use **Toggle navigation** to open the sidebar. The Current view polls every 30 seconds while the page is active. A background browser can pause timers; use **Refresh current state** to resolve it immediately. No hard reload or rebuild is needed for policy promotion. Historical selection intentionally remains a comparison until Current is chosen; a new application load defaults to Current.

## Real publication/reselection operations — prepare outside the interview

Only an authorized operator should dispatch CD. Read the live generation first and inspect the exact source/digest. Source SHA must be the current merged main revision with successful CI and the configured PR/approval model.

```sh
main_sha=$(gh api repos/bosphorus-cloud-labs/northstar-airlines-aws-landing-zone/commits/main --jq .sha)
# Reselect existing immutable V1; replace LIVE_GENERATION with the observed number.
gh workflow run governance-cd.yml --ref main -f action=rollback \
  -f source_sha="$main_sha" \
  -f snapshot_digest=08456a729e0dbe3b2bf36f02f79baa4778a8eaf518d1761831607fbf08de97dd \
  -f expected_generation=LIVE_GENERATION
# To restore registered V2, use the same rollback action with digest
# 1e00c3c3e1919a59dd16a83f092d1c2bab2cdff68c0999c33cb1735822098fc5
# and the newly observed generation, then provide actual environment approval.
```

The rollback action deliberately supports selecting any registered, verified revision, including restoring V2. It changes Current/history only. Do not republish an already registered V2 from a different commit: immutable source provenance cannot be rebound. Future new security requirements need a new reviewed policy/profile and a distinct snapshot/version.

## Offline rehearsal/reset and fallback

```sh
./demo.sh v1
# In the second terminal during the local demo:
./demo.sh v2
# Rehearse again without deleting history:
./demo.sh reset
```

The launcher reuses only its owned loopback servers, runs actual Terraform fmt/init/validate/plan/parity, simulates approval/canary/failure/retry/onboarding and writes ignored immutable local artifacts. `./demo.sh v2 --prepare-only` starts no server. Reset affects only local Current, never DynamoDB or live AWS. No frontend-only mock source exists: the local browser still uses the local Python API.

If cloud connectivity or a future publication fails, show the completed workflow evidence and downloaded synthetic reports, or use the prepared local console. State clearly which view is local. Never improvise an AWS repair, expose credentials, bypass approvals or claim stale/offline data is a fresh AWS compliance observation.

See [CI/CD commands and integration audit](CI_CD_DEMO.md) and [publication safety/recovery](GOVERNANCE_DELIVERY.md).
