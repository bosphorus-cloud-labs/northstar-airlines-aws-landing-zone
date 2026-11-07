# NorthStar Governance Console

The React/TypeScript/Vite console runs locally against FastAPI and on the existing Amplify application with Cognito Authorization Code + PKCE. The browser has no alternative mock-data source, AWS SDK, credentials, deployment role or mutation operations. The deployed API reads the verified DynamoDB Current/History catalogue; see [deployment evidence](DEPLOYMENT_ACCEPTANCE.md) and [security boundaries](../SECURITY.md).

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

Production builds require public Cognito settings and never permit a local-demo authentication fallback. A build without settings compiles to a configuration-required screen and makes no API calls. `npm run preview` serves that static bundle on `127.0.0.1:4173`; it cannot substitute the local-demo API for Cognito. Use `npm run dev` for the existing local demonstration. A configured production build uses its absolute deployed API URL, not the Vite proxy.

## Experience and navigation

A dark teal navigation rail, light workspace, understated aviation branding, text-and-icon status badges, and a persistent amber **SIMULATED DATA** banner distinguish the demo from actual cloud assessments. System fonts and bundled icons avoid remote font/image dependencies. CSS reflows cards and filters on smaller screens. Tables scroll within their panels, with keyboard focus and mobile hints. Navigation and tables remain usable on smaller screens. Controls have explicit labels, visible focus styles, a skip link, and reduced-motion support.

| Page | Current API-backed behavior |
| --- | --- |
| Overview | 100 synthetic accounts, resource status totals, environment distribution and verified provider-free Terraform receipt |
| Accounts | Account/resource status, environment/search/status filters, 5/10/25/50-row pagination and resource details |
| Resources & Drift | Individual resources with desired/observed values, evidence time, status/reason, filtering and account navigation |
| Compliance | Three central controls with compliant/noncompliant/unknown/stale counts derived from backend findings, plus environment filtering |
| Deployment Activity | Actual approved publication audit and before/after changes; historical simulated account distribution is separate |
| Governance Exceptions | Existing account-governance exceptions and expiration; these do not exempt the resource controls |

The current console loads one bounded, immutable resource view through `GET /api/v1/summary?view=resources`. Resource details, Compliance totals and publication activity derive from that same response. The browser aggregates returned evidence; it does not evaluate AWS policies or manufacture findings. Refresh retrieves Current again. Exceptions and historical account distribution use their existing read endpoints and remain separate. No browser mutation or alternative fixture source exists.

## Cognito session management

The deployed public client was read on 7 November 2026: access and ID tokens last ten minutes, refresh tokens one day, revocation is enabled, and Authorization Code/PKCE requires no client secret. No application idle timeout exists. The previous `AuthGate` cleared the session on access-token expiry without using the already-issued refresh token, which caused the reported short-session sign-outs.

The proposed session fix uses the pinned `oidc-client-ts` refresh-token grant, sixty seconds before expiry. Generic automatic iframe renewal stays disabled, and an empty silent redirect prevents iframe fallback. `AuthGate` permits renewal only while an OIDC-established refresh token exists. Both API clients await a fresh token before sending requests; tab focus/visibility also checks freshness after background suspension. Renewal is single-flight and updates the token used by later requests, rather than retaining the original callback token.

All access, ID and refresh tokens remain memory-only. PKCE transaction state alone uses sessionStorage. Full reload intentionally loses the memory session and requires Cognito sign-in/SSO again; use the console's **Refresh** button during a walkthrough. No localStorage token, password, client secret, AWS credential, new IAM permission or longer access-token lifetime is introduced.

A revoked/expired refresh grant clears identity, cached queries and library storage with a sanitized sign-in message. A transient refresh error retains a still-valid access token, but expired tokens are never sent. A governance API 401 ends the session without an unlimited retry loop; 403 remains a permission error. Logout/unmount prevent a late refresh from restoring a cleared session. Actual server-side JWT/scope/group checks are unchanged.

`frontend/src/test/auth.test.tsx` accelerates thirty minutes with the actual OIDC library timers and three mocked token-endpoint refresh grants. Additional tests cover concurrent renewal, wake after expiry, revoked grants, transient failure, stale completion, no persistent credentials and 401 versus 403. This is **offline protocol/lifecycle verification**, not a claim that this unmerged fix has passed a real thirty-minute Cognito session. After reviewed merge and Amplify release, sign in and verify the live console at 0, 10, 20 and 30 minutes, without recording tokens or changing Cognito lifetimes.

Sources: [Cognito token endpoint](https://docs.aws.amazon.com/cognito/latest/developerguide/token-endpoint.html), [OIDC client guidance](https://github.com/authts/oidc-client-ts/blob/main/docs/index.md).

## Retained account-catalogue client

The following version-scoped behavior belongs to the retained account-catalogue client, not the default resource console. Both clients use generated OpenAPI types and the same Cognito session.

- `src/api/schema.d.ts` is generated from the real FastAPI OpenAPI document. No HTTP server or AWS access is required to regenerate it.
- `src/api/client.ts` uses the generated route/response types. Every data request is pinned to its selected policy version, snapshot digest and reference evaluation timestamp. V1 uses 2026-10-31T12:00:00Z and V2 uses 2026-10-31T12:28:00Z. No wall-clock time affects evaluation.
- The client accepts only v1, `northstar-synthetic-v1`, `simulated: true`, and the matching evaluation timestamp. Missing summary counts, status/environment distributions inconsistent with returned records, duplicate account/finding IDs, or incomplete/malformed pagination cause visible errors rather than fabricated zeros or a partial fleet. HTTP error bodies and internal exceptions are not displayed verbatim.
- Each dataset refresh retrieves the summary and all pages of accounts, findings, deployments, drift, and exceptions. API pages are bounded at 100 records, with a 100-page guard per collection. Details use the account-detail endpoint. Requests have a 15-second timeout and cancellation on abandoned queries.
- Dataset caching lasts one minute, with explicit refresh, no automatic retries and no window-focus refresh. The Current catalogue polls every 30 seconds while the page is active; historical selection remains a read-only comparison. Browser credentials are omitted. No local storage contains evidence or credentials.
- Compliance statuses and exception expiration states come directly from the backend. The browser only joins records for display and aggregates already-returned counts; it never implements the evaluator, grants exceptions, or changes a failed result to compliant.

A refresh is not a transaction across the six endpoints. Each read is bound to the same immutable version/digest/time, with client reconciliation of totals and provenance; a Current promotion cannot silently mix revisions within that selected dataset. This console intentionally loads a small fleet in memory; enterprise pagination and search will need indexed server queries/cursors. Real observations require separately reviewed contracts instead of changing the simulation indicator.

The API exposes evidence IDs and reason classifications; versioned metadata also provides recorded evidence observation times. The UI distinguishes freshness at evaluation from missing/stale evidence and shows recorded timestamps where available; it does not invent observations. Deployment, drift, and exception records remain snapshot data, not historical reconstructions at `at`.

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

Dependencies are exact-pinned with an included npm lockfile. Development-only overrides pin minimatch 11.0.1 and Undici 6.29.1 to address transitive advisories; Node 24 satisfies their runtime requirements. Revisit these overrides when upstream tools adopt patched versions, and rerun contract generation, linting, tests, and npm audit after updates.

## Deployment and remaining limits

Amplify builds the frontend from protected main; Terraform supplies public API/Cognito settings and exact origins. Actual sign-in, API data, Current/History and main-only auto-build were verified in [deployment acceptance](DEPLOYMENT_ACCEPTANCE.md). The local proxy/identity bypass cannot be used for deployed authentication. Automated accessibility certification, durable frontend telemetry and fleet-scale server queries remain future work.

## Historical catalogue compatibility

The retained `LegacyConsole` reads the version catalogue from the API summary and renders options dynamically. Each dataset/detail query is scoped by policy version, immutable hash and evaluation time, and validates returned identity before displaying data. Switching resets page filters and does not show another version's data during loading/error. A failed V2 load is visible; return to V1 explicitly. Catalogue-unavailable legacy APIs remain V1-only. Authentication and deployed configuration are unchanged.

The UI shows simulated rollout stages and environment-specific requirements from API responses, plus evidence observation timestamps. The generated V1/V2 fixtures are test-only, not a frontend fallback. Hosted Current/History is deployed; [LOCAL_DEMONSTRATION.md](LOCAL_DEMONSTRATION.md) provides the live demonstration and local fallback.

The operations-console refinement follows the server-owned Current marker by default, with no persisted policy selection. History is explicitly labeled Historical evaluation with revision/time/hash options; it is not an application-version switch. A fresh page opens Current, and Refresh current state returns to the latest marker. The console does not show baseline data as Current when marker resolution fails. Deployments prioritizes target/approval/stage/retry outcomes and explicitly separates successful distribution from compliance evidence.

## Hosting migration compatibility

`VITE_GOVERNANCE_API_MODE=baseline-v1` is an explicit temporary mode for the deployed V1 backend: it requests the normal fixed-time baseline summary without catalogue/version parameters, clearly labels baseline-only data and disables history. It retains Cognito authentication and all API error/provenance checks. It never catches authorization errors to substitute data. Default `catalog` retains full Current/History/V2 behavior; the active hosted main branch uses `resources`. Retain baseline mode for explicit compatibility testing, not as an error fallback. See the [hosting migration procedure](AMPLIFY_GITHUB_INTEGRATION.md).
