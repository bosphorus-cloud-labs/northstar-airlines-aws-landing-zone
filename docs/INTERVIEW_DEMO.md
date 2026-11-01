# Five-minute Governance Operations Console demonstration

One application shows **CURRENT governance** and read-only **Historical snapshots**. Policy revisions are not application versions. This task changes local source only; the hosted POC, Cognito, IAM and DynamoDB remain untouched.

For source edit → commit/push → PR → completed Actions result, use [the short CI/CD runbook](CI_CD_DEMO.md). Perform that review cycle before presenting; never wait for CI during the five-minute demo. The CI artifact is not automatically published to this console or AWS.

## Prepare once before the interview

Prerequisites: Python 3.13 `.venv` with `requirements-dev.txt`, Node 24 with frontend dependencies, and Terraform >=1.14,<2. No AWS credentials are needed.

```sh
./demo.sh v1
```

Leave this Terminal running and open **http://127.0.0.1:5173**. The Current view shows baseline policy 1.0.0 and ten accounts. Open a second Terminal in the repository root for the single interview command. This is the **same API and React application** throughout the demonstration. `v1`/`v2` are policy scenario aliases, not app releases.

The launcher records ownership of its loopback-only servers. A subsequent demo reuses those servers only when their recorded processes are alive. It never kills unrelated port occupants. If ports 8000/5173 are already occupied by an unverified service, stop/restart the appropriate local service yourself before rehearsal; the launcher fails safely. Some agent sandboxes require permission to bind loopback ports. There is no cloud fallback or automatic deployment hidden in the launcher.

## Five minutes: one command, one browser refresh

| Time | Action | Speaking script |
| --- | --- | --- |
| 0:00–0:45 | Show Overview, **Current governance**. | “This is NorthStar's continuous governance console. Current policy is 1.0.0. Ten synthetic accounts are evaluated against environment-specific requirements. Unknown and stale evidence never passes.” |
| 0:45–1:45 | Run the single command below in the second Terminal. | “I propose an additional detective requirement: audit-log integrity validation enabled. Terraform really validates and plans the shared desired settings, without providers or AWS resources. Approval and account distribution are explicitly simulated.” |
| 1:45–2:15 | **Refresh the browser once.** Do not choose a policy revision. | “The approved current marker now references policy 2.0.0. The same console automatically shows the new current fleet and latest rehearsal run. No historical browser choice controls the current state.” |
| 2:15–3:15 | Deployments → **Governance rollout history** → expand stages/targets. | “The Development canary passed. A simulated customization failure stopped rollout before Production. Retry retained successful targets. The run records approval, attempts, failure, retry and deferrals; no Terraform apply or AFT execution happened.” |
| 3:15–4:15 | Compliance and Configuration Drift; expand environment settings if helpful. | “Distribution succeeded for eligible targets, but that is not compliance. Desired settings, observed values, revisions and evidence timestamps are distinct. Four findings remain noncompliant, nine unknown and ten stale. Two inactive accounts were deferred.” |
| 4:15–5:00 | Accounts → search `sim-account-011` → details. Optionally choose policy 1.0.0 under **Historical snapshot**. | “The simulated new account entered under the current baseline. Eleven accounts now produce 66 findings. Prior immutable evaluations remain available for comparison in this application; opening History does not roll back anything. A new page load always returns to Current.” |

```sh
./demo.sh v2
```

This command prints seven stages, executes real Terraform fmt/init/validate/plan and full parity checks, simulates independent approval/canary/failure/retry/onboarding, prepares immutable local exports and atomically promotes the local CURRENT marker. With the prepared servers already running it returns without restarting them. **Refresh current state** in the console also re-resolves the marker and returns to Current.

The main state header shows the effective policy revision, latest run reference and whether the view is Current or Historical. Current comes from an explicit server-owned marker, never “highest version” or a stored browser choice. A missing/invalid marker is an error; historical data is not silently substituted. History options include policy revision, evaluation time and a hash prefix. The same page routes and components show both views. One pinned immutable evaluation per registered policy revision is exposed today; identical deterministic rehearsals reuse its content hash and retain separate run logs.

## Rehearsal, reset and fallback

```sh
./demo.sh reset
```

Reset changes only the local CURRENT marker to baseline policy 1.0.0. Refresh the browser to see it. Policy 2.0.0 stays registered in History; immutable snapshot files and prior run directories remain intact. Run `./demo.sh v2` again to repeat the deterministic story and promote current policy 2.0.0 with a new rehearsal run reference. Use one command at a time. The promotion marker/run label is catalogue metadata; policy/evidence/journal contents remain hashed immutable data.

`./demo.sh v2 --prepare-only` performs the same real checks and simulated rollout, promotes the local marker, and starts no servers. All artifacts stay under ignored `artifacts/policy-rollout/interview/`. Ctrl-C in the original server Terminal stops only its owned server groups. The API/browser remain read-only; only the local operator launcher can change the catalogue file.

If local or hosted connectivity/publication fails, do not repair AWS during the interview. Use the existing hosted V1 console as a clearly identified baseline, or show the deterministic stage output and `run-NNNN/report.json`. Live AWS publication is not part of this command. The updated Current/History console is available locally only until a separately authorized application deployment and reader configuration update.

## Read contract and isolation

Existing eight GET routes and Cognito/gateway authorization are retained; no new cloud API route or write endpoint is required. `GET /api/v1/summary?catalog=true` advertises a server-owned list. The selected version is passed as `policy_version=2.0.0` on all data requests, with its explicit evaluation timestamp. Catalogue responses include an explicit `current` descriptor and `current_run` reference. For compatibility, default legacy API reads still use V1; the console resolves and requests Current explicitly. The server maps semantic versions to allowlisted repositories, profiles, timestamps and digests; clients cannot pass table names, partition IDs or paths. Unknown versions return 404, malformed versions 422, missing/corrupt snapshots sanitized 500. There is no V2-to-V1 fallback. Default requests retain the original V1 response structure/counts.

Versioned responses include policy/profile/generator/digest identity and evidence observation times. React checks version, digest, timestamp and simulation provenance, keys queries by the complete selection, clears page filters on switching, and does not reuse another version's data during loading/error. If the API cannot resolve a current marker, Current is unavailable; the operator may explicitly inspect the known historical baseline. Legacy default API data/metadata remain V1-compatible. Golden HTTP fixtures are generated from the real backend for tests only and are excluded from production imports.

The snapshot document contract remains `{fleet, policy, environments}` for legacy V1. Versioned documents add a validated `context` with format version, policy/profile, fixed evaluation time, generator, synthetic journal and proposal digest. That context is part of the content hash and its own DynamoDB item. V1's existing digest and manifest encoding are unchanged. Inherited record source/schema version identifies the synthetic record protocol; generator/profile/policy version are separate.

Current/History and the snapshot envelope support additional registered policy revisions without separate applications or hardcoded frontend options. **Only V1 and V2 policy profiles/scenarios are implemented now.** Future versions require a reviewed policy/contract profile and scenario, registration in server-side validation, preparation under the same snapshot envelope and operator promotion. Unsupported profiles fail closed; `./demo.sh v3` is deliberately rejected instead of inventing results. This is not arbitrary policy execution from browser input.

## Separately authorized AWS publication and deployment

There is deliberately no AWS publication command in `demo.sh`, the API or the frontend. Preparation produces immutable `<digest>.json` and `<digest>.publication.json` files under `artifacts/policy-rollout/interview/snapshots/`. The V2 package contains validated DynamoDB payload rows and the last-to-publish MANIFEST; it is not sent anywhere. `publication.validate_package(package, approved_digest)` is a pure validation function and rejects V1, changed digests, missing rows, malformed context and policy mismatch.

The required future sequence is:

1. Review this source change, package/build artifacts, V1 regression results, new V2 digest, simulated approval and real Terraform plan. Preserve the existing V1 data/configuration and a rollback release. Checksums and `sim-` reviewers are not signatures or real human authorization.
2. Separately authorize an operator/publisher principal in the intended Frankfurt account/table. Grant only conditional `PutItem` and verification `GetItem` for **`SNAPSHOT#<approved-V2-digest>`** on the exact table. Never grant V1 partition write, Scan, delete, Organizations or deployment authority. Revoke this short-lived permission after publication.
3. In a reviewed operator tool, validate the approved package, use the existing conditional/idempotent `scripts.seed_governance.load` algorithm with an explicitly authorized client, and publish MANIFEST **last**. Equal rows may be retried; any conflict stops without overwrite. Strongly consistent read-back/digest verification must succeed before registration. This task does not implement an AWS client/publisher CLI or execute those operations. Loader IAM cannot enforce WORM semantics by itself; conditional code and pinned digest detect violations, so tightly restrict operator trust.
4. Review a separate deployment configuration change: retain `SNAPSHOT_ID` as the exact V1 digest; extend the Lambda role's Query-only `dynamodb:LeadingKeys` allowlist to the two exact snapshot partitions. Do not add writes, Scan or browser DynamoDB access. Existing Terraform POC source is intentionally unchanged in this task, so this IAM/environment wiring is still a deployment prerequisite.
5. Register V2 in server-only `GOVERNANCE_VERSIONS_JSON`, a JSON list of descriptors containing exactly `policy_version`, `profile`, `evaluated_at`, `snapshot_id`, `generator`. V2 uses `2.0.0`, `policy-v2`, the prepared timestamp/hash and `northstar-policy-rollout-v1`. V1 is always inherited from `SNAPSHOT_ID` and cannot be replaced by this registry. `CURRENT_POLICY_VERSION` defaults to `1.0.0`; promote it to `2.0.0` only after publication/read-back verification. `CURRENT_GOVERNANCE_RUN` is the approved promotion/run reference. Unknown current revisions fail closed. Rollback moves the marker to 1.0.0 while retaining V2 in the read allowlist/history; it never overwrites snapshots. Missing registry means the original V1-only composition. No local catalogue/file source or local-demo mode is selected by Lambda.
6. Deploy the reviewed Python bundle (including the two approved contract files) and React build with existing public API/Cognito build settings under separate authorization. Test in a separate staging configuration first. API paths, public SPA/Cognito settings and gateway JWT scopes do not change. The browser gains only read selection; the Lambda gains only explicitly scoped reads.
7. Smoke-test real auth denial/success, catalogue, both versions, IAM-denied writes, partial/missing data, cache isolation, timestamps and headers. These AWS/Cognito/DynamoDB checks are not proven by local tests. Then promote the reviewed reader configuration. Roll back to the prior code/config or remove the optional V2 registration; do not rewrite or delete either immutable partition.

**Incomplete live integration:** no live publication, IAM/environment changes, application deployment or AWS smoke tests were performed. The source supports registered DynamoDB readers, but the hosted dashboard cannot show V2 until these separately authorized steps are completed. Snapshot metadata/evidence-time maps suit this bounded synthetic fleet; larger fleets need dedicated paginated evidence/event read models rather than repeating timestamp maps.
