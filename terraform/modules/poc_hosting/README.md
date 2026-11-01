# Existing Amplify app: staged repository migration

The existing `aws_amplify_app.console` address and `app_id/default_domain` outputs remain unchanged. Optional `github_repository_url`, sensitive `github_access_token` and `github_build_spec` configure that app in place. `prevent_destroy=true` protects it; no repository ignore_changes or second app is used. Security headers/rewrite and app-wide automatic-build default stay unchanged.

AWS rejects repository association while a manually deployed branch exists. Root therefore separates legacy-branch retirement, repository connection, and main creation into explicit checkpoints. Provider 6.71.0 sends a token only on an attribute change; a failed apply can record a token without connecting GitHub. Do not blindly reuse/remove that input or print state. See the [staged migration procedure](../../../docs/AMPLIFY_GITHUB_INTEGRATION.md).
