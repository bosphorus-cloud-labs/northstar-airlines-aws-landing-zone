# Resource compliance deployment acceptance — 5 November 2026

The resource console runs at [the existing Amplify application](https://main.d1eetlse86595h.amplifyapp.com/). Real AWS hosting, Cognito sign-in, API Gateway, Lambda, DynamoDB and protected OIDC publication are distinct from the **synthetic** accounts, resource configuration, account distribution and compliance observations.

## Source delivery and activation

| Check | Verified result |
| --- | --- |
| Baseline publication | [Run 42092442412](https://github.com/bosphorus-cloud-labs/northstar-airlines-aws-landing-zone/actions/runs/42092442412) passed after actual governance-production approval. Strong DynamoDB reads verified the manifest, content, ten Terraform account assignments and resource catalogue generation 1. |
| Publication failure handling | [PR #24](https://github.com/bosphorus-cloud-labs/northstar-airlines-aws-landing-zone/pull/24) fixed a false-green shell pipeline: an untracked root receipt caused the clean-checkout guard to reject publication, while tee masked its exit status. Explicit Bash pipefail and an ignored receipt path prevent recurrence; the regression test executes a real temporary Git checkout. Earlier green run 42080351067 did not publish resource data and is not acceptance evidence. |
| Backend | One reviewed in-place Lambda package update, no creates/destroys; same execution role, environment and authentication. Rebuilt Python 3.13/Linux ARM64 package matches deployed SHA-256 `6a03685818b491cbc8c4c53f2e3f0c96c28078e7d1d37059b097b5a00592794a`. Anonymous API and handler requests returned 401. |
| Live preview | Authenticated existing Cognito session opened the resource preview in the same React application, before changing the default. Overview, search, filters, pagination, account details, drift, deployment history and exceptions passed. |
| Frontend activation | Fresh Terraform plan changed only `aws_amplify_branch.github_main[0].environment_variables.VITE_GOVERNANCE_API_MODE`, catalog → resources. Applied with zero creates/destroys and no identity/API/storage/IAM changes. Amplify release job 12 passed build, deploy and verify. |
| Default application | Fresh reload and real Cognito SSO opened current resource compliance directly, with simulation labels and no policy-version selector. Ten accounts, ten resources, three controls, results 7 compliant / 1 noncompliant / 1 unknown / 1 stale; real Terraform receipt shown as succeeded. |

The original `GOVERNANCE#CATALOG / STATE` catalogue remains at generation 6. Original immutable account-governance snapshots were not rewritten. Lambda and browser remain read-only; the separate data-only publisher uses the existing exact repository/environment OIDC trust and actual GitHub Environment approval. Main-only Amplify auto-build stays enabled, app-wide auto-build stays disabled. A refreshed post-activation Terraform plan was empty (state serial 16) with the deployed resource mode explicitly retained.

## Live Git regression and rollback

| Stage | Source and publication | Verified result |
| --- | --- | --- |
| Compliant baseline | Main `5ac75cc7e294100fc30a9e551c74172b9aa9c50f`; baseline run above | Booking API observed `required`, desired `required`, compliant. |
| Synthetic regression | [PR #22](https://github.com/bosphorus-cloud-labs/northstar-airlines-aws-landing-zone/pull/22), original data commit `44954f43316d11c4ee2fc0e72cae79a401e2b446`; [main CI](https://github.com/bosphorus-cloud-labs/northstar-airlines-aws-landing-zone/actions/runs/42094480364); [approved publication 42094789521](https://github.com/bosphorus-cloud-labs/northstar-airlines-aws-landing-zone/actions/runs/42094789521) | Generation 2; 6 compliant / 2 noncompliant / 1 unknown / 1 stale. Authenticated dashboard and Production account details show desired `required`, observed `optional`, noncompliant with the IMDSv2 reason. |
| Git revert | [PR #25](https://github.com/bosphorus-cloud-labs/northstar-airlines-aws-landing-zone/pull/25), commit `06afc37da8c564978b62dd359d389b74b8136e0e` reverts only the original data commit; [main CI](https://github.com/bosphorus-cloud-labs/northstar-airlines-aws-landing-zone/actions/runs/42095608864); [approved publication 42095819240](https://github.com/bosphorus-cloud-labs/northstar-airlines-aws-landing-zone/actions/runs/42095819240) | Generation 3 selects the identical immutable baseline content. Strong reads verify all three audit entries and both snapshots. Real Cognito SSO, overview and activity show Booking API compliant again and both status transitions; totals restored to 7 / 1 / 1 / 1. |

No EC2 instance, bucket, volume or organization policy was changed. The regression changes one synthetic observation. The real pipeline validates schemas, security and Terraform desired-state parity before approved data publication. A successful plan or publication does not convert the other failing, unknown or stale observations into passing evidence.

## Validation and limits

- Local/CI coverage: 153 Python tests including organization-wide Terraform assignment checks; 57 frontend tests; 12 enterprise-reference tests; 30 Terraform mock-provider plan cases. API contract generation, TypeScript, frontend lint/format, production build, scoped Python Ruff, compilation, dependency validation and Terraform formatting/validation passed. POC mock-provider tests are configuration checks, not live AWS compatibility proof.
- Real provider-free Terraform fmt/init/validate/plan/show and full account/control parity are exercised in CI and bound to the published input. This automation does not apply AWS resources.
- Authenticated browser checks exercise the real API-backed console, not a local fixture response. Unknown and stale evidence remain separate. Account exceptions remain visible and do not exempt resource controls.
- Redacted Gitleaks scan covered all 34 reachable commits at the activation checkpoint with no findings. Generated packages, plans/state, settings, receipts and credential material remain ignored/private.
- The actual single-owner Environment approval is intentional. Administrator bypass remains disabled; this is not independent enterprise review.
- Control Tower/AFT/Organizations/SCP/networking and CodePipeline/SNS are reference designs only. Account rollout, canary, retry, onboarding, drift and compliance are synthetic. The bounded POC has no live AWS compliance collectors or resource remediation.

See [requirement-by-requirement traceability](REQUIREMENTS_TRACEABILITY.md) and [repeatable operational steps](RESOURCE_COMPLIANCE_OPERATIONS.md#five-minute-operational-demonstration). Runner and manual-approval latency can exceed five minutes; use completed CI artifacts and audit history for a time-bounded presentation.
