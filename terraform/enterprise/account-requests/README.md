# AFT account request example

This directory mirrors the generated `aft-account-request` repository: AFT renders the provider and backend templates, then runs the Terraform files under `terraform/`. Replace all example identity, email, and OU values through a reviewed change. The `ManagedOrganizationalUnit` value uses `OU Name (OU-ID)`, which is required for unambiguous nested OU targeting.

The bundled request module represents AFT 1.23.0 boilerplate and writes the request to AFT's DynamoDB table. When initializing a real repository, prefer copying the templates produced by the deployed AFT version and review any upstream schema changes before replacing this pinned example.
