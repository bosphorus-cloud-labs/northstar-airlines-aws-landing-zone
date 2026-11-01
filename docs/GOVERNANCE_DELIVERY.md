# Governance delivery: real publication, simulated fleet

## Implemented versus deployed

Source implements the complete data path: reviewed Git policy → credential-free CI/provider-free Terraform parity → protected OIDC CD → conditional immutable snapshot records → strongly consistent verification → atomic catalogue/Current promotion → read-only API → the same React console. Rollout approval/canary/failure/retry/onboarding/evidence inside the snapshot remain **simulated**. GitHub environment approval and DynamoDB publication are real operations only when authorized and executed.

Actual deployment has now been executed under owner authorization: foundation IAM/package changes, exact immutable OIDC subject correction, V1 bootstrap, catalogue activation, Amplify release job 2, V2 publication, rollback to V1 and restoration to V2 at generation 4. Both immutable digests and authenticated Current/History were verified. Main-only Amplify auto-build is enabled separately. Workflow evidence is maintained in [deployment acceptance](DEPLOYMENT_ACCEPTANCE.md). The stages below document the deployment sequence and future recovery procedure; completed plans must never be blindly reapplied.

## Contracts and safety boundaries

Snapshots reuse the existing codec: partition `SNAPSHOT#<sha256>`, immutable row keys and a MANIFEST written last. Digest = canonical complete fleet/policy/environment/context document. Package envelope binds the exact reviewed Git commit to that publication. Release preparation requires a clean checkout at that exact SHA and a real provider-free Terraform plan matching the frozen proposal. V1 data is never rewritten; its registry registration means verified approval of the existing baseline, not a claim about its original deployment commit/time.

`GOVERNANCE#CATALOG` / `STATE` holds a closed versioned contract: schema_version, simulated=true, generation, immutable revision descriptors/source commits, Current digest and append-only promotion history. One conditional PutItem atomically registers the verified revision and advances Current using an expected-generation compare-and-swap. It preserves previous entries; no delete or cross-partition transaction is needed. Bootstrap selects only pinned V1. Rollback strongly verifies a registered immutable target and changes selection/history only. Unknown versions, missing/invalid catalogue, incomplete manifests, mismatched digests and stale concurrent promotions fail closed. An uncertain network result after the atomic write must be resolved by strong read/audit; never blindly claim Current stayed unchanged after a lost response.

The manifest-last loader retries only byte-identical conditional conflicts. Failures can leave unregistered immutable rows, but never promote incomplete data. Reader lookup uses only server-registered revisions, never browser-supplied DynamoDB keys. In dynamic mode, requests without a version or evaluation time follow Current using one captured catalogue view. Explicit V1/version/time requests retain their previous semantics. The frontend's catalogue probe keeps its explicit V1 reference request, then pins data requests to the selected immutable descriptor; no mixed Current/data claim is inferred from probe counts. Every snapshot's timestamp and simulated provenance remain explicit. V2 still has failing, unknown and stale findings after successful distribution.

POC limits: 10,000 snapshot rows/read budget, 16 registered revisions, 128 promotion records; reaching the budget stops, rather than deleting history. Each policy version has one immutable digest/source binding; do not silently reuse `2.0.0` for changed data. New policy profiles/versions need contract/evaluator updates and tests. To reselect an existing digest after rollback use the rollback action with that registered target, not a new publication that rewrites provenance.

IAM separates reader and publisher. Publisher has only table Query/GetItem/PutItem on snapshot/catalogue partitions, explicitly denied writes to pinned V1. Reader has only Query on snapshot partitions, GetItem on the catalogue and existing log writes. No browser AWS identity, Lambda writes, publisher Terraform/Lambda/Amplify authority or public API write endpoints. The publisher Python module is excluded from the Lambda ZIP. Conditional immutability is code-enforced; trusted publisher credentials or account administrators could bypass application conditions. Digest validation detects content tampering; this is not WORM or signed compliance evidence.

## CI and CD

`governance-ci.yml` runs for PRs, main pushes, manual execution and as reusable CI. It has contents:read only, immutable action pins, no OIDC/AWS role and no persisted checkout credentials. It runs Python/schema/auth/delivery tests, Ruff/source credential/artifact guards, real provider-free fmt/init/validate/plan/parity, POC mock-provider plan tests and frontend contract/type/lint/tests/build. The mock Lambda ZIP exists only for mock plans; it is not a deployable package. Review artifacts contain synthetic reports and a commit-bound release.json; no state or executable plan is uploaded.

`governance-cd.yml` is manual-dispatch on main only. It reruns unprivileged CI and requires successful main-push CI for the exact main SHA and a merged PR. The default independent model requires an independent APPROVED review of the final head. The explicitly authorized `single-owner-poc` model instead requires an owner-authored merged PR, an owner-triggered run, protected main, and the real owner as the environment approver. It never invents PR approvals. It checks `governance-production` required reviewers, the selected self-review setting and exact main-only branch policy before requesting credentials. `GOVERNANCE_APPROVAL_MODEL=single-owner-poc` is an explicit repository variable; an absent value preserves independent review. The privileged job then waits for actual environment approval. Only that job has id-token:write. It downloads only its own workflow's deterministic candidate, verifies SHA/digest offline, assumes the data-only role and executes bootstrap/publish/rollback. Concurrency serializes promotions; generation checks also reject races with other operators. The protected approval is real; `sim-security-reviewer` inside fleet events is not production authorization.

The current environment API exposes `can_admins_bypass`; the single-owner gate requires it to be explicitly false, and the deployed setting was verified. Keep administrator bypass disabled in Settings. Do not add unsupported IAM claims. Main branch protection requires a PR, strict successful Governance checks/Frontend checks, resolved conversations, and no force pushes/deletions/admin shortcuts. In the single-owner POC it requires zero independent approving reviews and no last-pusher approval; deployment authorization is the actual protected environment approval. This is a documented POC separation-of-duties limitation, not an independent review claim. The default independent model rejects self/stale PR approvals; both models reject outstanding trusted changes requests. Reviews reaching the 100-record API budget fail closed pending explicit pagination review. Repository administrators can change workflows, environment protections or IAM trust; they remain trusted operators.

## Deployment gates and exact plans

This is an operating procedure, not standing permission for future cloud changes. Source PR/CI, cloud plan authorization and protected environment approval are distinct gates. Keep existing app/Cognito/API/table/state; do not rerun hosting migration A–C.

### 1. Approve the foundation plan

Build the Python 3.13 Linux ARM64 package using the existing pinned vendor wheels:

```sh
.venv/bin/python -m scripts.package_lambda --output artifacts/lambda/governance-delivery.zip
```

The locally inspected real-state plan is `artifacts/governance-delivery-infrastructure.tfplan`, mode 600, ignored and secret-bearing. Initial review used read-only refresh without lock writes; fresh authorized apply plans used normal state locking. The recorded Amplify setup-token input was preserved in memory to avoid unrelated app changes. Do not upload or blindly reuse it after state/source changes. Exact expected actions:

| Address | Action |
| --- | --- |
| module.delivery[0].aws_iam_openid_connect_provider.github[0] | create |
| module.delivery[0].aws_iam_role.publisher | create |
| module.delivery[0].aws_iam_role_policy.publisher | create |
| module.compute.aws_iam_role_policy.runtime | in-place update |
| module.compute.aws_lambda_function.api | in-place package update |

**3 creates, 2 updates, 0 destroys/replacements.** Lambda function name/role, app/branches, Cognito, API Gateway and table stay unchanged. `enable_governance_delivery=true`, `governance_catalog_enabled=false`, `lambda_package_path=../../artifacts/lambda/governance-delivery.zip`; keep Amplify baseline mode/builds off. The package update adds read support; dynamic selection is not activated before bootstrap. Use the approved secret-management input consistently if a subsequent plan would otherwise remove the recorded Amplify token.

```sh
AWS_PROFILE=north terraform -chdir=terraform/poc plan -input=false \
  -var=enable_governance_delivery=true -var=governance_catalog_enabled=false \
  -var=lambda_package_path=../../artifacts/lambda/governance-delivery.zip \
  -out=../../artifacts/governance-delivery-infrastructure.tfplan
.venv/bin/python -m scripts.inspect_delivery_plan artifacts/governance-delivery-infrastructure.tfplan
```

An operator must separately approve/apply that exact reviewed plan. The authorized foundation apply has completed; see the acceptance record. Future applies still require scope review. Persist completed flags/package path in ignored settings; wrong defaults after deployment could propose removing roles or reverting the reader.

### 2. Configure protected GitHub delivery

The repository is public and user-owned. The owner has explicitly chosen the single-owner POC model: `GOVERNANCE_APPROVAL_MODEL=single-owner-poc` as a repository variable. `governance-production` requires the real owner, permits self-review, disables administrator bypass, and allows only exact main. The workflow still waits for the owner's actual GitHub deployment approval. No CLI approval, fabricated review or administrative bypass is used. Enterprise deployments should keep the default independent model and assign a different reviewer.

Add environment variables, not AWS keys:

- GOVERNANCE_PUBLISH_ROLE_ARN: Terraform governance_publisher_role_arn output.
- AWS_ACCOUNT_ID: authorized account ID.
- GOVERNANCE_TABLE: existing table name.
- GOVERNANCE_BASELINE_ID: Terraform governance_baseline_id output.

Missing protection or actual deployment approval is a real blocker, not permission to bypass the workflow. Keep CI unprivileged; never put repository tokens or AWS keys into artifacts.

### 3. Bootstrap the existing V1 registration

After the workflow is reviewed/merged and main CI succeeds, dispatch the approved CD workflow with the **main merge commit SHA** (not the feature-head SHA), pinned baseline digest, action bootstrap and generation 0. Its only write is the catalogue item; existing V1 snapshot rows are strongly verified and not rewritten.

```sh
gh workflow run governance-cd.yml --ref main \
  -f action=bootstrap -f source_sha=REVIEWED_MAIN_SHA \
  -f snapshot_digest=PINNED_V1_DIGEST -f expected_generation=0
```

The configured environment reviewer must inspect the exact SHA/digest/operation and approve. Verify the publication receipt and strong catalogue generation 1. Do not enable the reader while bootstrap is missing.

### 4. Activate the reader and the existing frontend

After bootstrap, prepare a second reviewed plan with delivery still enabled, `governance_catalog_enabled=true` and `github_baseline_compatibility=false`. Expected: Lambda environment update and existing main branch environment update only; package/app/identity/table remain unchanged. A real plan for this future state must be generated after stage 1/3, not invented from mock state. Apply only after authorization. The catalogue's Current stays V1 initially. Then authorize one manual Amplify release on the same main branch and verify Cognito and baseline Current/History. No deployment-role changes are needed in the browser or Lambda.

### 5. Publish V2 and prove rollback

For the safe cloud failure acceptance check, first dispatch publish with the correct approved candidate but stale expected_generation=0 while the verified registry is generation 1. The publisher rejects it before any data write; verify failed Actions status, generation 1 and V1 Current. Then use a new approved dispatch with generation 1 for the successful publication below. Do not bypass approval or corrupt a snapshot to manufacture failure.

Use the candidate digest from successful CI's job summary/artifact; source_sha is the exact main commit that generated it. Dispatch publish with expected_generation=1. CD rebuilds/validates the same approved candidate, conditionally loads rows/manifest, strongly verifies the full digest and atomically promotes generation 2.

```sh
gh workflow run governance-cd.yml --ref main \
  -f action=publish -f source_sha=REVIEWED_MAIN_SHA \
  -f snapshot_digest=APPROVED_V2_DIGEST -f expected_generation=1
```

On https://main.d1eetlse86595h.amplifyapp.com confirm Current policy 2.0.0, 11 synthetic accounts, findings 43 compliant/4 noncompliant/9 unknown/10 stale, retained rollout failure/retry and V1 history. Catalogue polling refreshes Current every 30 seconds; explicit History remains a comparison. A failed publication must leave Current unchanged; offline fault-injection tests exercise that path. Perform a separately approved cloud failure rehearsal only with a non-writing preflight failure or controlled test data, never by corrupting live history.

Then dispatch rollback with the registered V1 digest and expected_generation=2. Verify generation 3 and V1 Current with V2 still in History. To inspect only the numeric generation:

```sh
AWS_PROFILE=north aws dynamodb get-item --region eu-central-1 \
  --table-name northstar-governance-poc-records --consistent-read \
  --key '{"pk":{"S":"GOVERNANCE#CATALOG"},"sk":{"S":"STATE"}}' \
  --projection-expression '#g' --expression-attribute-names '{"#g":"generation"}'
```

Retries of the same workflow run use the same operation ID. A later promotion superseding it blocks stale retries. A new rollback can select any registered verified revision without deleting snapshots. Cloud acceptance needs actual workflow links/approval receipts and authenticated dashboard checks; local tests or a successful plan are not substitutes.

### 6. Enable main-only frontend auto-builds after acceptance

Only after CI, publication/promotion/rollback and authenticated dashboard refresh succeed, review `github_auto_build_enabled=true`. Expected plan: only main branch auto-build flag. App-wide defaults stay false, no other branches/PR previews are enabled. Protect main with reviewed PRs and required CI before this opt-in. Amplify then builds frontend source from approved main merges; it never runs Terraform. Data CD remains separately approved. Final auto-build enablement status is recorded in the acceptance document.

## Local reproduction and costs

Use the existing `./demo.sh v1` / `./demo.sh v2` for an offline local demonstration. Real provider-free plan/parity plus simulated rollout remain separate from real publication. `scripts.governance_release build` requires a clean committed checkout and completed CLI run/real plan JSON; no credential is needed. `check` validates release SHA/digest offline. Only explicit execute modes construct an AWS client, and require table confirmation, generation and approved digest.

GitHub Actions usage, DynamoDB conditional/strong reads/writes, Lambda polling and Amplify builds/storage/traffic can incur charges. No NAT/VPC/Control Tower/Organizations/AFT infrastructure is added. Closing the dashboard stops catalogue polling. History is retained; there is no automatic deletion/TTL cleanup. Infra teardown, permission removal and data retention need separate reviewed plans. Publication roles cannot delete data or provision infrastructure.

References: [GitHub AWS OIDC](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws), [deployment approvals](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments), [environment API](https://docs.github.com/en/rest/deployments/environments), [AWS OIDC trust](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_create_for-idp_oidc.html).

## OIDC subject correction (1 November 2026)

The first approved bootstrap failed before receiving AWS credentials: `Not authorized to perform sts:AssumeRoleWithWebIdentity`. The live OIDC provider and audience were correct, but role trust used the legacy name-only subject. GitHub's API reports `use_default=true`, `use_immutable_subject=true` and prefix `repo:bosphorus-cloud-labs@319390912/northstar-airlines-aws-landing-zone@1440849538`. Correct trust uses that prefix plus `:environment:governance-production`, under exact StringEquals; the workflow explicitly requests `sts.amazonaws.com`. No wildcard or second trusted legacy subject is added. The narrowly reviewed correction is one in-place publisher role trust update, zero creates/destroys. Failed bootstrap did not run the DynamoDB publication step.
