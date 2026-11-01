"""Approval metadata is required before an OIDC role can be requested."""

import copy
import unittest

from scripts.delivery_gate import ENVIRONMENT, REPOSITORY, verify


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
        from scripts.check_source_security import validate

        validate("terraform/poc/settings.example.tfvars", b'owner = "synthetic"')
        for path in [
            "artifacts/release.json",
            "terraform/poc/settings.auto.tfvars",
            "function.zip",
            "state.tfstate",
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
