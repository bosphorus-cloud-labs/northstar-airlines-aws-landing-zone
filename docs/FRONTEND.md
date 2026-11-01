# NorthStar Governance Console

Phase 3 implements a local React/TypeScript/Vite console over the existing read-only FastAPI API. The browser has no alternative mock-data source, AWS SDK, credentials, deployment role, or mutation operations. Phase 4A adds Cognito/PKCE sign-in and Terraform deployment source; no hosting resources or deployment workflow have been executed. See [deployment foundation](AWS_DEPLOYMENT_FOUNDATION.md).

## Start locally

Prerequisites: Python 3.13 and Node.js 24 (tested with 24.19.0; pinned in `frontend/.nvmrc`). Run both terminals from the repository root unless a command changes directory.

Terminal 1 — API:

```sh
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m backend --local-demo
```

Terminal 2 — console:

```sh
cd frontend
npm ci
npm run dev
```

Open [the console](http://127.0.0.1:5173). The API must be listening on `127.0.0.1:8000`. Vite uses `127.0.0.1:5173` with strict port selection, and proxies only `/api` to the fixed local API target. `changeOrigin` rewrites Host to the backend's allowed loopback address. No CORS relaxation, browser token, or backend authentication change is required. Stop both servers with Ctrl+C.

This proxy is an explicitly scoped local-demo integration: the backend sees the loopback Vite process, not an authenticated browser identity. Keep both processes on a trusted workstation. Do not publish, tunnel, bind publicly, or place this setup behind a public reverse proxy. Default backend mode still denies requests, and the Lambda entry point remains fail-closed. All authorization remains server-side; the console does not pretend to verify JWTs or grant permissions.

Phase 4A production builds require public Cognito settings and never permit a local-demo authentication fallback. A build without settings compiles to a configuration-required screen and makes no API calls. `npm run preview` serves that static bundle on `127.0.0.1:4173`; it cannot substitute the local-demo API for Cognito. Use `npm run dev` for the existing local demonstration. A configured production build uses its absolute deployed API URL, not the Vite proxy.

## Experience and navigation

A dark teal navigation rail, light workspace, understated aviation branding, text-and-icon status badges, and a persistent amber **SIMULATED DATA** banner distinguish the demo from actual cloud assessments. System fonts and bundled icons avoid remote font/image dependencies. CSS reflows cards and filters on smaller screens. Tables scroll within their panels, with keyboard focus and mobile hints. Mobile navigation supports focus containment and Escape; route changes focus the page heading. Controls have explicit labels, visible focus styles, a skip link, and reduced-motion support.

| Page | API-backed behavior |
| --- | --- |
| Overview | Summary totals, four-state account posture, environment distribution, finding counts, latest deployment records, and links to violations/failures/drift |
| Accounts | Complete inventory, name/ID/OU search, environment/compliance filters, five-row pagination, and API-backed account details |
| Compliance | Individual findings; account/environment/control/status filters; evidence classification from API reasons; linked exception states and status explanations |
| Deployments | Simulated Terraform/AFT history, environment/tool/status filters, desired/observed revisions, failures, completion context, correlation IDs |
| Configuration Drift | Desired/observed values and revisions, affected account/control, observation date, drift-state filter |
| Governance Exceptions | Rationale, owners, approvers, approval references, expiry, evaluated exception state, and the original finding status; pending states render when returned, with an empty state when absent |

Accounts and findings retain their deterministic API order. Deployments sort by started timestamp descending with ID as tie-breaker. Pagination and search operate over the **entire API-returned dataset**, not only the first API page. Environment/control display labels are presentation mappings, not policy evaluation logic.

## Contracts and data flow

`backend OpenAPI → generated TypeScript contracts → typed GET client → TanStack Query cache → React routes`.

- `src/api/schema.d.ts` is generated from the real FastAPI OpenAPI document. No HTTP server or AWS access is required to regenerate it.
- `src/api/client.ts` uses the generated route/response types. Every data request supplies `2026-10-31T12:00:00Z`; the displayed reference time derives from this constant. No wall-clock time affects evaluation.
- The client accepts only v1, `northstar-synthetic-v1`, `simulated: true`, and the matching evaluation timestamp. Missing summary counts, status/environment distributions inconsistent with returned records, duplicate account/finding IDs, or incomplete/malformed pagination cause visible errors rather than fabricated zeros or a partial fleet. HTTP error bodies and internal exceptions are not displayed verbatim.
- Each dataset refresh retrieves the summary and all pages of accounts, findings, deployments, drift, and exceptions. API pages are bounded at 100 records, with a 100-page guard per collection. Details use the account-detail endpoint. Requests have a 15-second timeout and cancellation on abandoned queries.
- Query caching lasts one minute, with explicit refresh, no automatic retries, and no background window-focus refresh. Browser credentials are omitted. No local storage contains evidence or credentials.
- Compliance statuses and exception expiration states come directly from the backend. The browser only joins records for display and aggregates already-returned counts; it never implements the evaluator, grants exceptions, or changes a failed result to compliant.

A refresh is not a transaction across the six endpoints. This is consistent for the immutable local fixture dataset; a future changing datastore needs server-side snapshot/version semantics. This console intentionally loads a small fleet in memory; enterprise pagination and search will need indexed server queries/cursors. Real observations require separately reviewed contracts instead of changing the simulation indicator.

The API exposes evidence IDs and reason classifications, but not raw evidence observation timestamps. The UI therefore says “Fresh at evaluation”, “Evidence expired”, or “No evidence recorded” from those reasons; it does not invent an observation time. Deployment, drift, and exception records remain snapshot data, not historical reconstructions at `at`.

## Contract generation and tests

From `frontend/`, with the repository's Python `.venv` installed:

```sh
npm run api:generate
npm run api:check
npm run typecheck
npm run lint
npm run format:check
npm test
npm run build
```

From the repository root, keep backend tests passing:

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/ruff check backend governance tests
.venv/bin/ruff format --check backend governance tests
git diff --check
```

The generation script also captures test-only API responses using FastAPI TestClient and explicit local-demo mode in process. `src/test/api-responses.json` is imported only by tests and never included in the production entry point. It is a regression fixture generated from the same backend, not an alternative frontend runtime. `api:check` verifies both generated files against current backend output.

Frontend tests cover all six routes, account details, loading, HTTP/network/authorization errors and retry, API rendering, provenance/timestamp rejection, filters, UI and API pagination, incomplete data, exceptions preserving violations, simulation indicators, refresh, and keyboard navigation. Browser QA checks the live proxy on desktop and mobile; unit tests alone do not certify visual accessibility.

Dependencies are exact-pinned with an included npm lockfile. Development-only overrides pin minimatch 11.0.1 and Undici 6.29.1 to address transitive advisories; Node 24 satisfies their runtime requirements. Revisit these overrides when upstream tools adopt patched versions, and rerun contract generation, linting, tests, and npm audit after updates. No dependency installation scripts need broad approval; the optional macOS fsevents watcher can remain unapproved because Vite runs without it.

## Remaining deployment work

The production build is validated as a static bundle, not deployed. Phase 4A prepares Amplify SPA rewrites, absolute API routing, Cognito Code + PKCE, and verified gateway identity checks in source. Real sign-in/MFA/gateway integration, durable telemetry, and deployed accessibility/security verification remain future acceptance gates. The local proxy and identity bypass must not be used as production authentication. See [architecture](ARCHITECTURE.md) and [backend boundaries](BACKEND_API.md).

## Read-only policy selector

The interview source reads the version catalogue from the API summary and renders options dynamically. Each dataset/detail query is scoped by policy version, immutable hash and evaluation time, and validates returned identity before displaying data. Switching resets page filters and does not show another version's data during loading/error. A failed V2 load is visible; return to V1 explicitly. Catalogue-unavailable legacy APIs remain V1-only. Authentication and deployed configuration are unchanged.

The UI shows simulated rollout stages and environment-specific requirements from API responses, plus evidence observation timestamps. The generated V1/V2 fixtures are test-only, not a frontend fallback. Hosted availability requires the separately approved backend/frontend deployment and data registration described in [INTERVIEW_DEMO.md](INTERVIEW_DEMO.md).

The operations-console refinement follows the server-owned Current marker by default, with no persisted policy selection. History is explicitly labeled Historical evaluation with revision/time/hash options; it is not an application-version switch. A fresh page opens Current, and Refresh current state returns to the latest marker. The console does not show baseline data as Current when marker resolution fails. Deployments prioritizes target/approval/stage/retry outcomes and explicitly separates successful distribution from compliance evidence.
