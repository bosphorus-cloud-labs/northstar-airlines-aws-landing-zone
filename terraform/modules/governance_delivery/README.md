# Protected synthetic-data publisher

Optional module composed only by the POC root. Creates a GitHub OIDC provider (or uses an explicitly supplied existing ARN), role and inline table policy. Trust is restricted to the exact NorthStar repository, `sts.amazonaws.com` audience and `governance-production` environment. GitHub must enforce independent approval and main-only deployment rules; IAM's environment subject does not itself prove CI/review status.

Publisher actions: Query/GetItem/PutItem on the existing table's snapshot/catalogue partitions, with an explicit PutItem deny for the pinned V1 partition. No deletes, scans, Lambda/IAM/Amplify modifications or Terraform deployment permissions. Conditions/idempotence/digest checks are enforced by reviewed publisher code; this is not DynamoDB WORM. Runtime gets separate read-only Query/GetItem permissions. No AWS client is constructed on module import and Terraform never inserts data.

See [deployment sequencing and acceptance](../../../docs/GOVERNANCE_DELIVERY.md). A validated plan is not proof of a working OIDC session or cloud publication.
