# Enterprise requirements traceability

Status values describe repository evidence, not deployed AWS capability.

| Requirement | Evidence | Status / limitation |
| --- | --- | --- |
| Existing repository inspected and preserved | Repository docs, Terraform roots, governance model, and workflows reviewed before this change; enterprise diff review required | Implemented process; no deployment evidence |
| Official AFT bootstrap with account boundaries | `aft-bootstrap/main.tf`, `providers.tf`, `variables.tf`, examples | Implemented reference pinned to AFT 1.23.0; execution starts in Control Tower Management and requires four prepared accounts/roles |
| AFT prerequisites, identity, repositories, ordering, backend | `README.md`, `aft-bootstrap/backend.hcl.example` | Documented; backend/roles/repositories are external prerequisites |
| Production account request and OU/customization metadata | `account-requests/terraform/production.tf`, generated module/templates | Implemented example; example email and OU must be replaced |
| Global AFT customization | `global-customizations/terraform/main.tf` and AFT templates | Terraform resources and AFT 1.23.0 target-role template implemented; deployment not verified |
| Production/Development customization differences | `account-customizations/*/terraform/main.tf`, rendered-template tests | Distinct budget limits/notification semantics implemented; email confirmation and deployment external |
| Organizations SCPs and OU attachments | `organizations/main.tf`, `organizations/policies/*.json` | Real provider resources; existing Organization/OUs and management identity required |
| SCP ownership and safety | `organizations/main.tf`, policies, `README.md` | Customer-managed resources, `prevent_destroy`, region scope, and repair-role exclusions implemented; effective-policy/live repair testing external |
| Central TGW and RAM | `networking/core/main.tf` | Implemented resource reference; organization sharing prerequisite applies |
| Production/Development isolation and inspection routing | TGW route tables, explicit opt-in routes, `networking/README.md` | Environment isolation and attachment ownership implemented; end-to-end inspection intentionally design-only |
| Hybrid VPN | Customer gateway, VPN, opt-in propagation in `networking/core/main.tf` | VPN control plane implemented; direct propagation is explicitly uninspected and disabled by default |
| GWLB integration | GWLB, target group, endpoint service | Control-plane scaffold only; endpoints, targets, steering, return paths, and IDS/IPS are not implemented |
| Cross-account/state boundaries and route symmetry | Accepter/association resources, separate roots, `networking/README.md` | Staged ownership and acceptance implemented; route symmetry remains a deployment design prerequisite |
| Pull-request validation/security analysis | `ci/templates/pull-request-validation.yml.example` | Illustrative credential-free template; hardened runner/tooling required before activation |
| Scoped plan, protected reviewed apply, separate OIDC identity | CI examples and `ci/README.md` | Illustrative manifest-bound plan/handoff; deployment command and IAM implementation intentionally absent |
| Saved-plan handling, post-validation, failure/recovery | `ci/README.md`, CI examples | Encrypted cross-run provenance demonstrated; actual apply/post-validation and operational rehearsal missing |
| New/existing accounts and deployment waves | Enterprise `README.md` | Documented; actual AFT/Control Tower execution not performed |
| Drift, retries, failed customization lifecycle | Enterprise `README.md`, `ci/README.md` | Proposed operating model; no scheduler/remediation deployed |
| Config/Security Hub/dashboard integration | Enterprise `README.md` | Proposed only; existing dashboard remains synthetic |
| Offline tests and policy JSON checks | `tests/test_enterprise.py`, `tests/render_aft_templates.py` | Static, routing, policy, and rendered-template checks implemented; AWS behavior and deployment remain unverified |
| Isolation from deployed application and simulation | Directory boundary and isolation test | Implemented; no remote-state reference |
