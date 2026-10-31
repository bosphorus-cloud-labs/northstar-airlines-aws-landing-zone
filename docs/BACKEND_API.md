# Local governance backend API (v1)

Implemented for Python 3.13: FastAPI/Pydantic read APIs over the Phase 1 synthetic fleet and evaluator. The Phase 3 [React console](FRONTEND.md) now consumes these APIs. Local mode involves no AWS service or credentials. Phase 4A adds deployment-only DynamoDB/authentication composition and Terraform source without cloud execution; see [deployment guide](AWS_DEPLOYMENT_FOUNDATION.md). Simulated AFT/Terraform history is data only; requests cannot execute either tool.

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

`--local-demo` is an explicit identity bypass for development on a trusted workstation, **not production authentication**. It grants a fixed local demo reader only to numeric loopback client addresses, requires exactly one raw Host header matching a loopback name/address (with an optional numeric port), and rejects every Authorization header. It never parses or accepts bearer tokens. Forwarded identity/address headers confer no identity; no CORS allowances are configured. The Phase 3 Vite proxy is the sole documented proxy exception: both processes bind to loopback on a trusted workstation, with a fixed API target. Do not expose either server via public binds, tunnels, public reverse proxies, port forwarding, or shared hosts. Local processes can access demo data while the mode is enabled.

`Authenticator.authenticate(Request) -> Principal` is the replaceable identity interface. A future Cognito implementation must verify signature, trusted issuer, audience/client binding, expiry and permitted algorithms before mapping verified claims to permissions. API Gateway authorization and application checks must use an explicitly reviewed trust boundary. The deployed authenticator consumes only API Gateway verified claims and checks read scope/group; it does not pretend to verify arbitrary bearer tokens. No local-demo bypass exists in that composition.

`backend.lambda_handler.handler` wraps a fail-closed app in Mangum, with an explicitly owned Python 3.13 event loop per invocation. It is tested with an in-memory API Gateway-shaped event, not deployed or connected to AWS. It constructs the deployment composition with `local_demo=False`; environment variables, forwarded headers, and bearer tokens cannot enable demo mode. Complete deployment settings select the DynamoDB adapter and trusted gateway authenticator; incomplete settings deny requests. Real AWS validation remains future work.

## Dependency and Lambda packaging boundaries

Runtime and test dependencies are exact-pinned for Python 3.13. Final review upgraded FastAPI to 0.162.0 and Starlette to 1.10.0 after five advisories were reported for Starlette 0.49.3; the supported HTTPX2 test client is pinned separately from runtime dependencies. The complete flattened set of 26 pins was checked with pip-audit 2.9.0 on 2026-10-31, with no known vulnerabilities reported after the update. Advisory scans are point-in-time checks, not proof of absence of vulnerabilities. Review future updates with the full test suite and a new audit. FastAPI's OpenTelemetry API dependency is included; no telemetry SDK/exporter or outbound telemetry is configured by this application.

Local tests run on Python 3.13. Runtime requirements also resolve to binary/universal wheels for Linux ARM64 and x86_64 Python 3.13. This checks packaging availability, not execution in Lambda. Native `pydantic-core` and `rpds-py` dependencies must be built/resolved for the chosen Linux runtime/architecture; do not copy the macOS virtual environment into a deployment package. A future authorized package must preserve `backend/`, `governance/` (including schemas, policies, environments), and `mock-data/` while the fixture adapter remains in use. Linux runtime import tests, deployment configuration, and cloud smoke tests remain deferred. See [AWS Python packaging guidance](https://docs.aws.amazon.com/lambda/latest/dg/python-package.html) and [Starlette advisories](https://github.com/Kludex/starlette/security/advisories).

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

List responses contain `data: []` and `pagination: {"total": 10, "limit": 25, "offset": 0, "next_offset": null}`. Totals are computed **after filtering**. Records are ordered by ID (findings by account/control); offset pagination is deterministic for an unchanged snapshot. `limit` defaults to 25 and is bounded 1–100. `offset` defaults to zero and is bounded 0–1,000,000. Beyond the end, data is empty and next_offset is null. A future DynamoDB repository will need cursor-based paging and a versioned API transition, not a table scan behind this interface.

Except for process health, endpoints accept `at`, a timezone-aware RFC 3339 timestamp. Omission uses the **fixed demo timestamp `2026-10-31T12:00:00Z`**, never wall-clock time. Timestamps are normalized to UTC; values whose UTC conversion overflows the supported datetime range return 422. Numeric epochs, naive timestamps, duplicate query parameters, unknown filter fields, invalid enum values, and evaluations predating account creation are rejected with 422.

| GET path | Data | Additional query filters |
| --- | --- | --- |
| `/api/v1/health` | Process status and authentication mode | None; does not read or verify the dataset; metadata carries the demo reference timestamp |
| `/api/v1/summary` | Fleet counts, four-state account/finding counts, environment counts | None beyond `at` |
| `/api/v1/accounts` | Account record and compliance summary | `environment`, `lifecycle_status`, `compliance_status`; pagination |
| `/api/v1/accounts/{account_id}` | Account, OU, compliance summary, five control findings | `at` |
| `/api/v1/findings` | Phase 1 finding records | `account_id`, `environment`, `control_id`, `status`; pagination |
| `/api/v1/deployments` | Simulated revision/deployment records | `account_id`, `environment`; pagination |
| `/api/v1/drift` | Simulated desired/observed drift records | `account_id`, `environment`; pagination |
| `/api/v1/exceptions` | Original exception plus evaluator-derived expiration state | `account_id`, `environment`; pagination |

Environment values are `production`, `pre-production`, `testing`, `development`. Compliance states are `compliant`, `noncompliant`, `unknown`, `stale`. Control values are defined by the Phase 1 contract. Account IDs must match `sim-account-NNN`. A well-formed absent account produces 404 in detail or account-filtered endpoints; malformed IDs produce 422. Valid filters with no matches return an empty page.

Health reports process availability, not datastore readiness. The evaluation time affects compliance and exception state only. Inventory, deployments, drift, and exception approval metadata remain the current fixture snapshot; `at` does not reconstruct historical account/deployment states or rerun drift detection. See [model semantics](GOVERNANCE_MODEL.md).

Example summary `data` at the reference timestamp:

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

The exception record above is abbreviated; actual responses include all Phase 1 required fields and provenance. The related encryption finding remains **noncompliant**. Missing evidence remains unknown; stale evidence remains stale.

Errors use `{"error":{"code":"invalid_request","message":"Request parameters are invalid"}}`. Statuses include 401 authentication required, 403 access denied, 404 unknown account/path, 405 unsupported method, 422 invalid request/time, and 500 internal failure. Validation input, exceptions, local file paths, and stack traces are not returned. Responses have no-store caching and nosniff headers. No durable error telemetry is implemented yet.

## Layers and integration boundaries

- `backend/api/routes.py`: versioned GET routes and filtering/pagination presentation.
- `backend/api/models.py`: typed Pydantic queries/responses and Phase 1 JSON Schema validation of returned domain records. It does not define compliance rules.
- `backend/service.py`: loads one request-owned snapshot, calls `governance.model.evaluate.evaluate` and `summarize`, assembles read views. Exception states come from evaluator output.
- `backend/repository.py`: `GovernanceRepository` protocol and read-only `FixtureRepository`. Future DynamoDB storage must preserve a consistent request snapshot or introduce a separately designed query contract.
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

Tests cover every route, Pydantic/Phase 1 contract validation, paging/filter combinations, invalid and absent IDs, default denial, demo peer/host/token restrictions, permission denial, metadata, exception expiration, evaluator parity, deterministic UTC-equivalent responses, safe internal errors, repository isolation, CLI defaults, OpenAPI, and fail-closed Mangum invocation. Existing Phase 1 tests run in the same suite.

References: [FastAPI response validation](https://fastapi.tiangolo.com/tutorial/response-model/), [Mangum adapter](https://mangum.fastapiexpert.com/adapter/).
