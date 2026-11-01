# Protected synthetic-data publisher

Optional module composed only by the POC root. Creates a GitHub OIDC provider (or uses an explicitly supplied existing ARN), role and inline table policy. Trust is restricted to the exact NorthStar repository, `sts.amazonaws.com` audience and `governance-production` environment. GitHub must enforce independent approval and main-only deployment rules; IAM's environment subject does not itself prove CI/review status.

Publisher actions: Query/GetItem/PutItem on the existing table's snapshot/catalogue partitions, with an explicit PutItem deny for the pinned V1 partition. No deletes, scans, Lambda/IAM/Amplify modifications or Terraform deployment permissions. Conditions/idempotence/digest checks are enforced by reviewed publisher code; this is not DynamoDB WORM. Runtime gets separate read-only Query/GetItem permissions. No AWS client is constructed on module import and Terraform never inserts data.

See [deployment sequencing and acceptance](../../../docs/GOVERNANCE_DELIVERY.md). A validated plan is not proof of a working OIDC session or cloud publication.

The repository uses GitHub immutable OIDC subjects. Trust pins owner ID `319390912`, repository ID `1440849538`, and exact environment `governance-production`, using StringEquals with audience `sts.amazonaws.com`. It does not accept the older name-only subject or wildcard branches/repositories. Verify `sub_claim_prefix` and `use_immutable_subject` through GitHub's OIDC customization API before deployment; `use_default=true` alone does not mean legacy subject syntax. See [GitHub reference](https://docs.github.com/en/actions/reference/security/oidc).
