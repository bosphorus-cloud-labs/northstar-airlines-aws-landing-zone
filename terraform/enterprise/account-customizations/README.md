# Environment account customizations

The `production` and `development` directories are AFT account customization templates selected by `account_customizations_name`. Both inherit the global password and S3 public-access baseline. They own only environment budgets: Production uses a higher limit and forecast warning; Development uses a lower limit and actual-spend warning. Replace example notification addresses before use.

AWS Budgets notifications require email confirmation outside Terraform. These examples do not modify Control Tower-managed AWS Config, CloudTrail, IAM roles, or baseline resources.
