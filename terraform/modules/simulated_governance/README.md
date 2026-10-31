# Simulated account governance module

Pure Terraform calculation with no provider, resource or data source. Inputs: a synthetic account, central policy and assigned environment. Output `desired` includes account/OU/lifecycle, target revision, baseline and control requirements with category, expected value and maximum evidence age.

Plan-time preconditions reject unresolved environment/policy assignments, missing controls and weakened central baseline settings. Real AWS enforcement is outside this module: a detective check, CI/CD approval requirement or preventive intent is not transformed into an AWS policy/resource. Full source contracts and plan/proposal parity are checked by the Python verifier in the isolated [simulation root](../../simulation/README.md).
