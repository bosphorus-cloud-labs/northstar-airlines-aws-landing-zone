# Governance backend API (v1)

Python 3.13 FastAPI/Pydantic read APIs reuse the governance contracts and deterministic evaluator. Local development uses synthetic fixtures without AWS calls; deployed Lambda/Mangum uses strongly verified DynamoDB snapshots and API Gateway's Cognito JWT-authorizer context. See [deployment evidence](DEPLOYMENT_ACCEPTANCE.md). Simulated Terraform/AFT history is data only; HTTP requests cannot execute either tool.

## Install and run

From the repository root:

```sh
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
# Explicitly opt in to a local-only identity bypass:
.venv/bin/python -m backend --local-demo
```

The launcher binds only `127.0.0.1:8000`, disables forwarded-header trust, and disables access logging. Use `--port 8765` for another port. Stop with Ctrl+C. Without `--local-demo`, the same launcher runs in locked mode: every HTTP surface returns 401. Importing `backend.app:app` is also locked by default; there is no environment variable that enables demo mode.

In demo mode, browse [Swagger UI](http://127.0.0.1:8000/docs) or [OpenAPI JSON](http://127.0.0.1:8000/openapi.json). Both are protected by the same server-side boundary as data routes. Swagger UI loads its assets from the framework's default CDN; the API and automated tests operate offline after dependency installation.

```sh
curl --fail --silent http://127.0.0.1:8000/api/v1/summary
curl --fail --silent --get http://127.0.0.1:8000/api/v1/findings \
  --data-urlencode 'at=2026-10-31T12:00:00Z' \
  --data-urlencode 'account_id=sim-account-002' \
  --data-urlencode 'status=noncompliant'
```

`backend/requirements.txt` pins runtime dependencies and includes `governance/requirements.txt` for the shared model. `requirements-dev.txt` adds pinned Ruff and HTTP test tooling. A runtime-only install can use `.venv/bin/python -m pip install -r backend/requirements.txt`. Run from the repository root: imports and fixture/schema packaging must remain available.

## Authentication and authorization

Default mode is **fail-closed**, not an anonymous API. All routes, health, docs, OpenAPI, unknown paths, and unsupported methods pass through server-side authentication and a `governance:read` permission check before dispatch. No-read principals receive 403.

`--local-demo` is an explicit identity bypass for development on a trusted workstation, **not production authentication**. It grants a fixed local demo reader only to numeric loopback client addresses, requires exactly one raw Host header matching a loopback name/address (with an optional numeric port), and rejects every Authorization header. It never parses or accepts bearer tokens. Forwarded identity/address headers confer no identity; no CORS allowances are configured. The local Vite proxy is the sole documented proxy exception: both processes bind to loopback on a trusted workstation, with a fixed API target. Do not expose either server via public binds, tunnels, public reverse proxies, port forwarding, or shared hosts. Local processes can access demo data while the mode is enabled.

`Authenticator.authenticate(Request) -> Principal` is the replaceable identity interface. API Gateway verifies JWT signature, issuer, audience/client binding, expiry and scopes; Lambda requires the configured gateway/stage and verified reader scope/group. A different authenticator must preserve an equivalent reviewed identity boundary. The deployed authenticator consumes only API Gateway verified claims and checks read scope/group; it does not pretend to verify arbitrary bearer tokens. No local-demo bypass exists in that composition.

`backend.lambda_handler.handler` wraps a fail-closed app in Mangum, with an explicitly owned Python 3.13 event loop per invocation. It has both in-process API Gateway event regressions and actual deployed smoke-test evidence. It constructs the deployment composition with `local_demo=False`; environment variables, forwarded headers, and bearer tokens cannot enable demo mode. Complete deployment settings select the DynamoDB adapter and trusted gateway authenticator; incomplete settings deny requests. The live result is recorded separately from local tests in the acceptance report.

## Dependency and Lambda packaging boundaries

Runtime and test dependencies are exact-pinned for Python 3.13; advisory scans and update guidance are in [SECURITY.md](../SECURITY.md). FastAPI's OpenTelemetry API dependency has no configured telemetry SDK/exporter. Do not remove transitive pins independently: the package builder validates the complete runtime set.

`deployment.package_lambda` accepts preinstalled Linux ARM64/Python 3.13 wheels and assembles a deterministic ZIP containing backend/governance code and the approved contract files. It excludes local fixtures, tests, environment files, Terraform and the publisher. Deployed Lambda uses DynamoDB, not a copied local fixture directory. Native wheel compatibility is checked locally and actual Lambda execution is verified separately; never package the workstation virtual environment. See [the deployment guide](AWS_DEPLOYMENT_FOUNDATION.md).

## API structure

Successful responses use:

```json
{
  "metadata": {
    "api_version": "v1",
    "source": "northstar-synthetic-v1",
    "simulated": true,
    "evaluated_at": "2026-10-31T12:00:00Z"
  },
  "data": {}
}
```

List responses contain `data: []` and `pagination: {"total": 10, "limit": 25, "offset": 0, "next_offset": null}`. Totals are computed **after filtering**. Records are ordered by ID (findings by account/control); offset pagination is deterministic for an unchanged snapshot. `limit` defaults to 25 and is bounded 1–100. `offset` defaults to zero and is bounded 0–1,000,000. Beyond the end, data is empty and next_offset is null. The bounded snapshot adapter uses strongly consistent Query pages internally; fleet-scale indexed queries/cursors would require a separately versioned storage/API design, not Scan.

Except for process health, endpoints accept `at`, a timezone-aware RFC 3339 timestamp. Local/pinned V1 omission uses 2026-10-31T12:00:00Z. In deployed catalogue mode, omission of both `at` and `policy_version` resolves Current and its fixed reference time; explicit versions use their registered timestamps. Evaluation never defaults to wall-clock time. Timestamps are normalized to UTC; values whose UTC conversion overflows the supported datetime range return 422. Numeric epochs, naive timestamps, duplicate query parameters, unknown filter fields, invalid enum values, and evaluations predating account creation are rejected with 422.

| GET path | Data | Additional query filters |
| --- | --- | --- |
| `/api/v1/health` | Process status and authentication mode | None; does not read or verify the dataset; metadata carries the demo reference timestamp |
| `/api/v1/summary` | Fleet counts, four-state account/finding counts, environment counts; optional catalogue | `at`, `policy_version`, `catalog` |
| `/api/v1/accounts` | Account record and compliance summary | `environment`, `lifecycle_status`, `compliance_status`; pagination |
| `/api/v1/accounts/{account_id}` | Account, OU, compliance summary, selected-profile control findings | `at` |
| `/api/v1/findings` | Governance finding records | `account_id`, `environment`, `control_id`, `status`; pagination |
| `/api/v1/deployments` | Simulated revision/deployment records | `account_id`, `environment`; pagination |
| `/api/v1/drift` | Simulated desired/observed drift records | `account_id`, `environment`; pagination |
| `/api/v1/exceptions` | Original exception plus evaluator-derived expiration state | `account_id`, `environment`; pagination |

Environment values are `production`, `pre-production`, `testing`, `development`. Compliance states are `compliant`, `noncompliant`, `unknown`, `stale`. Control values are defined by the selected version/profile contract. Account IDs must match `sim-account-NNN`. A well-formed absent account produces 404 in detail or account-filtered endpoints; malformed IDs produce 422. Valid filters with no matches return an empty page.

Health reports process availability, not datastore readiness. The evaluation time affects compliance and exception state only. Inventory, deployments, drift, and exception approval metadata remain the current fixture snapshot; `at` does not reconstruct historical account/deployment states or rerun drift detection. See [model semantics](GOVERNANCE_MODEL.md).

Example V1 summary `data` at its reference timestamp:

```json
{
  "account_count": 10,
  "finding_count": 50,
  "account_counts": {"compliant": 3, "noncompliant": 3, "unknown": 2, "stale": 2},
  "finding_counts": {"compliant": 31, "noncompliant": 3, "unknown": 6, "stale": 10},
  "environment_counts": {"production": 3, "pre-production": 2, "testing": 2, "development": 3}
}
```

Exception items retain both the original record and its evaluation state:

```json
{"exception": {"id": "exc-002", "status": "approved", "simulated": true},
 "expiration_state": {"id": "exc-002", "state": "active"}}
```

The exception record above is abbreviated; actual responses include all required contract fields and provenance. The related encryption finding remains **noncompliant**. Missing evidence remains unknown; stale evidence remains stale.

Errors use `{"error":{"code":"invalid_request","message":"Request parameters are invalid"}}`. Statuses include 401 authentication required, 403 access denied, 404 unknown account/path, 405 unsupported method, 422 invalid request/time, and 500 internal failure. Validation input, exceptions, local file paths, and stack traces are not returned. Responses have no-store caching and nosniff headers. No durable error telemetry is implemented yet.

## Layers and integration boundaries

- `backend/api/routes.py`: versioned GET routes and filtering/pagination presentation.
- `backend/api/models.py`: typed Pydantic queries/responses and governance JSON Schema validation of returned domain records. It does not define compliance rules.
- `backend/service.py`: loads one request-owned snapshot, calls `compliance_engine.evaluate.evaluate` and `summarize`, assembles read views. Exception states come from evaluator output.
- `backend/repository.py`: `GovernanceRepository` protocol and read-only `FixtureRepository`. The deployed `DynamoSnapshotRepository` and `DynamoCatalog` preserve immutable version/digest selection and strongly verify the read model.
- `backend/auth.py`, `app.py`: identity/permission boundary, application factory, sanitized error handling. No cloud SDKs or network calls.

The fixture adapter parses fresh JSON per request so caller mutations cannot affect subsequent requests. It validates the complete model and evaluates the small fleet for each data request. This favors correctness for ten accounts; fleet-scale storage, indexes, caching, timeouts, and snapshot consistency need later design. There are no write routes or background jobs.

## Tests and quality checks

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/ruff check backend governance tests
.venv/bin/ruff format --check backend governance tests
.venv/bin/python -m compileall -q backend governance tests
.venv/bin/python -m pip check
git diff --check
```

Tests cover every route, Pydantic/domain contract validation, paging/filter combinations, invalid and absent IDs, default denial, demo peer/host/token restrictions, permission denial, metadata, exception expiration, evaluator parity, deterministic UTC-equivalent responses, safe internal errors, repository isolation, CLI defaults, OpenAPI, and fail-closed Mangum invocation. Governance model tests run in the same suite.

References: [FastAPI response validation](https://fastapi.tiangolo.com/tutorial/response-model/), [Mangum adapter](https://mangum.fastapiexpert.com/adapter/).

## Policy-version reads and Current/History

Data GETs accept `policy_version=1.0.0|2.0.0`; `/api/v1/summary?catalog=true` advertises server-owned descriptors, `current` and `current_run`. Clients cannot supply raw table/partition IDs, file paths or arbitrary profiles. Unknown versions return 404; missing/corrupt selected data fails closed without substituting V1.

The deployed `GOVERNANCE_CATALOG_MODE=dynamodb` path reads one generation-checked server catalogue. Default requests follow Current when neither version nor time is supplied; explicit version/time reads retain deterministic historical semantics. Local/pinned compatibility remains V1 without a catalogue. The optional static `GOVERNANCE_VERSIONS_JSON` path is retained for compatibility, not the active deployment mechanism.

Version metadata includes policy/profile/generator, immutable hash and observation times. Versioned summaries include the simulated journal and environment requirements. The same evaluator computes all findings. The local launcher explicitly selects a file catalogue with loopback-only demo identity; deployed Lambda cannot select it. V1/V2 are whole-governance snapshots, not independently versioned production policy records. See [data semantics](GOVERNANCE_MODEL.md), [delivery operations](GOVERNANCE_DELIVERY.md) and [console validation](LOCAL_DEMONSTRATION.md).
