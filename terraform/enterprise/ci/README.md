# Enterprise delivery reference

Files under `templates/` are illustrative `.example` files, not working automation and not active GitHub workflows. Copying them into `.github/workflows` requires a separate threat model, IAM implementation, runner hardening, testing, and approval.

Pull-request validation has no OIDC permission. A separate manual plan template checks that the exact commit is reachable from `main`, selects an allow-listed root, initializes its exact backend, and assumes a root-scoped planning identity. The illustrative runner label assumes Terraform, Trivy, age, jq, and standard checksum/archive tools are installed and independently patched.

The plan artifact contains a manifest binding source commit, root, plan digest, provider lock digest, and plan workflow run. The encrypted archive is retained for two days. The handoff template retrieves it by exact run ID, verifies the encrypted and plaintext digests, checks commit ancestry and manifest fields, waits for the protected environment, and only then assumes a distinct deployment identity.

No template contains `terraform apply`. The final job stops after initializing the approved state and proving the saved plan is readable. Before activation, implement exact OIDC trust conditions, least-privilege plan/apply roles, runner isolation, state-serial freshness enforcement, reviewer separation, and the reviewed apply/post-validation commands.

After an authorized apply, use a separate read-only validation identity to inspect Control Tower/AFT execution status, SCP attachments, TGW routes, VPN tunnels, Config recorder delivery, and Security Hub aggregation. On failure, stop the wave, preserve logs without state or secrets, release locks only after proving no run is active, correct forward through a new reviewed plan, and use provider-supported restore/import procedures only under incident approval. Never blindly reapply a stale plan or edit state. AFT customization retries are idempotent only when customization resources and helper scripts are idempotent.
