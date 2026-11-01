# Security boundaries and vulnerability reporting

This is a public, single-owner interview POC, not a certified enterprise security platform. Account inventory, evidence, Terraform/AFT distribution and compliance findings are synthetic. Real deployment/approval evidence is recorded separately in [deployment acceptance](docs/DEPLOYMENT_ACCEPTANCE.md).

## Report safely

Do not post credentials, tokens, state, saved plans, customer information or exploit details in public issues/PRs. Contact the repository owner privately, or use GitHub private vulnerability reporting if enabled. Include affected file/commit locations and a redacted description. If a real credential was committed, revoke/rotate it first, assess use/logs and coordinate explicit history/artifact cleanup; deleting the current file alone is insufficient. Do not rewrite history or conceal development provenance without authorization.

## Implemented controls

- Cognito code/S256 PKCE with memory-only tokens, API Gateway JWT/read scope and server-side reader-group enforcement. Deployed Lambda cannot enable local-demo identity.
- Exact approved HTTPS origins; no browser AWS identity, direct DynamoDB access, public write routes or Lambda function URL.
- Separate read-only runtime and data-only OIDC publisher. Trust pins immutable owner/repository IDs, exact environment and STS audience; publisher cannot deploy infrastructure, delete records or write V1.
- Protected main/CI and actual environment approval. Single-owner self-review is explicit; administrator bypass stays disabled. This is not independent enterprise review.
- Conditional manifest-last publication, strong digest verification, generation-based Current/history and safe registered-revision reselection. This is application-enforced integrity, not WORM storage; administrators/publisher code remain trusted.
- Pinned dependencies/action revisions, reviewed lockfiles, no persisted checkout credentials, bounded logs and enumerated synthetic Actions artifacts. State/plans/local settings/ZIPs stay ignored and private.

## Audit and maintenance

On 1 November 2026, Gitleaks 8.30.1 found no leaks in the fetched complete reachable history, full historical file trees, commit messages or tracked source. npm audit reported zero known advisories; pip-audit 2.10.1 checked all 35 pinned runtime/development Python distributions without skips and found no known vulnerabilities. These are point-in-time advisory/pattern checks, not proof that vulnerabilities cannot exist.

Repeat in a clean checkout after fetching relevant branch/tag/PR refs:

```sh
gitleaks git . --log-opts="--all --full-history" --redact=100 --ignore-gitleaks-allow
npm --prefix frontend audit
# Use a separately installed pip-audit tool; never add auditor dependencies to Lambda.
pip-audit -r requirements-dev.txt --no-deps --disable-pip --strict
.venv/bin/python -m scripts.check_source_security
```

Keep reports redacted/local; never print secret values or upload full state/plan/log payloads. Full-tree/commit-message scanning and historical path checks complement Gitleaks' diff scan. Ignore rules do not remove a file already committed. The CI source guard also rejects credential/key files, sensitive HCL/JSON tfvars and saved-plan/state formats even if force-added; sanitized example settings remain allowed. Runtime dependency pins are intentionally complete for reproducible packaging; test-only API response fixtures and generated TypeScript contracts are meaningful and excluded from production runtime imports.

Real Config/Security Hub collection, multi-account enforcement, independent production approvals, dedicated budgets/alerting, fleet-scale read models and retention/recovery hardening remain future work. See [security review](docs/AWS_DEPLOYMENT_REVIEW.md) and [architecture](docs/ARCHITECTURE.md). Repository hygiene does not authorize AWS writes, data publication, identity changes, state operations or teardown.
