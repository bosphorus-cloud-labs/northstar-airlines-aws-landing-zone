"""Approval metadata is required before an OIDC role can be requested."""

import copy
import unittest

from deployment.delivery_gate import ENVIRONMENT, REPOSITORY, verify


class DeliveryGateTests(unittest.TestCase):
    def setUp(self):
        self.sha, self.digest = "a" * 40, "b" * 64
        self.env = {
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_EVENT_NAME": "workflow_dispatch",
            "GITHUB_REPOSITORY": REPOSITORY,
            "GITHUB_SHA": self.sha,
        }
        root = f"repos/{REPOSITORY}"
        self.environment = f"{root}/environments/{ENVIRONMENT}"
        self.runs = f"{root}/actions/workflows/governance-ci.yml/runs?event=push&head_sha={self.sha}&per_page=100"
        self.pulls = f"{root}/commits/{self.sha}/pulls?per_page=100"
        self.reviews = f"{root}/pulls/1/reviews?per_page=100"
        self.data = {
            self.environment: {
                "can_admins_bypass": False,
                "protection_rules": [
                    {
                        "type": "required_reviewers",
                        "prevent_self_review": True,
                        "reviewers": [{"type": "User", "reviewer": {"id": 1}}],
                    }
                ],
                "deployment_branch_policy": {"custom_branch_policies": True},
            },
            self.environment + "/deployment-branch-policies": {
                "branch_policies": [{"name": "main", "type": "branch"}]
            },
            self.runs: {
                "workflow_runs": [
                    {
                        "head_sha": self.sha,
                        "event": "push",
                        "status": "completed",
                        "conclusion": "success",
                    }
                ]
            },
            self.pulls: [
                {
                    "number": 1,
                    "merged_at": "2026-11-01T00:00:00Z",
                    "merge_commit_sha": self.sha,
                    "base": {"ref": "main"},
                    "head": {"sha": "c" * 40},
                    "user": {"login": "engineer"},
                }
            ],
            self.reviews: [
                {
                    "state": "APPROVED",
                    "author_association": "COLLABORATOR",
                    "submitted_at": "2026-10-31T23:59:00Z",
                    "commit_id": "c" * 40,
                    "user": {"login": "reviewer"},
                }
            ],
        }

    def test_exact_reviewed_ci_commit_and_protected_environment_pass(self):
        self.assertEqual(
            verify(self.sha, self.digest, get=self.data.__getitem__, env=self.env)["source_commit"],
            self.sha,
        )

    def single_owner(self):
        owner = REPOSITORY.split("/")[0]
        self.env.update(GOVERNANCE_APPROVAL_MODEL="single-owner-poc", GITHUB_ACTOR=owner)
        self.data[f"repos/{REPOSITORY}"] = {
            "owner": {"login": owner, "type": "User"},
            "default_branch": "main",
        }
        self.data[f"repos/{REPOSITORY}/branches/main"] = {"protected": True}
        rule = self.data[self.environment]["protection_rules"][0]
        rule.update(
            prevent_self_review=False, reviewers=[{"type": "User", "reviewer": {"login": owner}}]
        )
        self.data[self.pulls][0]["user"]["login"] = owner
        self.data[self.reviews] = []

    def test_explicit_single_owner_model_does_not_fabricate_pr_reviews(self):
        self.single_owner()
        result = verify(self.sha, self.digest, get=self.data.__getitem__, env=self.env)
        self.assertEqual(result["approval_model"], "single-owner-poc")
        self.assertEqual(self.data[self.reviews], [])

    def test_single_owner_rejects_wrong_actor_unprotected_main_or_admin_bypass(self):
        self.single_owner()
        for change in ("actor", "protection", "bypass", "reviewer", "missing_pr", "failed_ci"):
            data, env = copy.deepcopy(self.data), dict(self.env)
            if change == "actor":
                env["GITHUB_ACTOR"] = "outsider"
            if change == "protection":
                data[f"repos/{REPOSITORY}/branches/main"]["protected"] = False
            if change == "bypass":
                data[self.environment]["can_admins_bypass"] = True
            if change == "reviewer":
                data[self.environment]["protection_rules"][0]["reviewers"] = []
            if change == "missing_pr":
                data[self.pulls] = []
            if change == "failed_ci":
                data[self.runs]["workflow_runs"][0]["conclusion"] = "failure"
            with self.subTest(change=change), self.assertRaises(ValueError):
                verify(self.sha, self.digest, get=data.__getitem__, env=env)

    def test_single_owner_cannot_skip_outstanding_changes_requested(self):
        self.single_owner()
        self.data[self.reviews] = [
            {
                "state": "CHANGES_REQUESTED",
                "author_association": "COLLABORATOR",
                "submitted_at": "2026-10-31T23:59:00Z",
                "commit_id": "c" * 40,
                "user": {"login": "reviewer"},
            }
        ]
        with self.assertRaises(ValueError):
            verify(self.sha, self.digest, get=self.data.__getitem__, env=self.env)

    def test_unknown_approval_model_is_rejected(self):
        with self.assertRaises(ValueError):
            verify(
                self.sha,
                self.digest,
                get=self.data.__getitem__,
                env={**self.env, "GOVERNANCE_APPROVAL_MODEL": "bypass"},
            )

    def test_wrong_ref_commit_or_event_cannot_enter_cd(self):
        for key, value in [
            ("GITHUB_REF", "refs/heads/feature"),
            ("GITHUB_SHA", "d" * 40),
            ("GITHUB_EVENT_NAME", "pull_request"),
        ]:
            env = {**self.env, key: value}
            with self.subTest(key=key), self.assertRaises(ValueError):
                verify(self.sha, self.digest, get=self.data.__getitem__, env=env)

    def test_missing_or_bypassable_approval_environment_fails(self):
        for update in [
            {"can_admins_bypass": True},
            {"protection_rules": []},
            {
                "protection_rules": [
                    {"type": "required_reviewers", "reviewers": [], "prevent_self_review": False}
                ]
            },
        ]:
            data = copy.deepcopy(self.data)
            data[self.environment].update(update)
            with self.assertRaises(ValueError):
                verify(self.sha, self.digest, get=data.__getitem__, env=self.env)
        data = copy.deepcopy(self.data)
        data[self.environment + "/deployment-branch-policies"]["branch_policies"][0]["name"] = "*"
        with self.assertRaises(ValueError):
            verify(self.sha, self.digest, get=data.__getitem__, env=self.env)

    def test_failed_ci_or_stale_self_approval_fails(self):
        for section, mutation in [
            (self.runs, lambda value: value["workflow_runs"][0].update(conclusion="failure")),
            (self.reviews, lambda value: value[0].update(commit_id="d" * 40)),
            (self.reviews, lambda value: value[0]["user"].update(login="engineer")),
        ]:
            data = copy.deepcopy(self.data)
            mutation(data[section])
            with self.assertRaises(ValueError):
                verify(self.sha, self.digest, get=data.__getitem__, env=self.env)

    def test_pending_changes_requested_blocks_promotion(self):
        self.data[self.reviews].append(
            {
                "state": "CHANGES_REQUESTED",
                "author_association": "COLLABORATOR",
                "submitted_at": "2026-10-31T23:59:30Z",
                "commit_id": "c" * 40,
                "user": {"login": "second-reviewer"},
            }
        )
        with self.assertRaises(ValueError):
            verify(self.sha, self.digest, get=self.data.__getitem__, env=self.env)

    def test_public_environment_response_without_admin_bypass_field_is_supported(self):
        del self.data[self.environment]["can_admins_bypass"]
        self.assertEqual(
            verify(self.sha, self.digest, get=self.data.__getitem__, env=self.env)["source_commit"],
            self.sha,
        )

    def test_tracked_source_rejects_generated_files_and_credentials(self):
        from deployment.check_source_security import validate

        validate("terraform/poc/settings.example.tfvars", b'owner = "synthetic"')
        validate("terraform/poc/settings.example.tfvars.json", b'{"owner":"synthetic"}')
        validate("frontend/.env.example", b"VITE_COGNITO_CLIENT_ID=REPLACE")
        for path in [
            "artifacts/release.json",
            "terraform/poc/settings.auto.tfvars",
            "function.zip",
            "state.tfstate",
            "terraform/poc/settings.auto.tfvars.json",
            "saved.tfplan.json",
            "snapshot.tfstate.backup",
            "release.plan",
            "tfplan",
            "plan.out",
            "credentials",
            "credentials.json",
            "id_rsa",
            "id_ed25519",
            "signing.pem",
            "signing.key",
            "identity.p12",
            "identity.pfx",
        ]:
            with self.assertRaises(ValueError):
                validate(path, b"synthetic")
        with self.assertRaises(ValueError):
            validate("unsafe.txt", ("ghp_" + "a" * 30).encode())

    def test_public_outsider_or_post_merge_review_cannot_authorize_release(self):
        for change in [{"author_association": "NONE"}, {"submitted_at": "2026-11-01T01:00:00Z"}]:
            data = copy.deepcopy(self.data)
            data[self.reviews][0].update(change)
            with self.assertRaises(ValueError):
                verify(self.sha, self.digest, get=data.__getitem__, env=self.env)


class WorkflowRunGateTests(unittest.TestCase):
    def setUp(self):
        DeliveryGateTests.setUp(self)
        self.env["GITHUB_EVENT_NAME"] = "workflow_run"
        root = f"repos/{REPOSITORY}"
        self.run_path = f"{root}/actions/runs/123"
        self.data[self.run_path] = {
            "head_sha": self.sha,
            "head_branch": "main",
            "event": "push",
            "status": "completed",
            "conclusion": "success",
            "path": ".github/workflows/governance-ci.yml",
            "head_repository": {"full_name": REPOSITORY},
        }
        self.data[f"{root}/git/ref/heads/main"] = {"object": {"sha": self.sha}}

    def test_verified_exact_main_workflow_run_passes(self):
        result = verify(
            self.sha, self.digest, get=self.data.__getitem__, env=self.env, validation_run_id="123"
        )
        self.assertEqual(result["source_commit"], self.sha)

    def test_untrusted_or_outdated_runs_are_denied(self):
        for field, value in [
            ("head_sha", "d" * 40),
            ("head_branch", "feature"),
            ("event", "pull_request"),
            ("conclusion", "failure"),
            ("path", ".github/workflows/untrusted.yml"),
            ("head_repository", {"full_name": "attacker/fork"}),
        ]:
            data = copy.deepcopy(self.data)
            data[self.run_path][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                verify(
                    self.sha,
                    self.digest,
                    get=data.__getitem__,
                    env=self.env,
                    validation_run_id="123",
                )
        with self.assertRaises(ValueError):
            verify(self.sha, self.digest, get=self.data.__getitem__, env=self.env)
