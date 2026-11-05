"""Contract integrity and deterministic synthetic policy behavior."""

import copy
import unittest
from collections import Counter

from jsonschema import Draft202012Validator, ValidationError

from compliance_engine.contracts import SCHEMA, validate, validate_model
from compliance_engine.evaluate import evaluate, load_model, summarize

AT = "2026-10-31T12:00:00Z"


class GovernanceTests(unittest.TestCase):
    def setUp(self):
        self.fleet, self.policy, self.envs = copy.deepcopy(load_model())

    def run_model(self, at=AT):
        return evaluate(self.fleet, self.policy, self.envs, at=at)

    def finding(self, aid, control):
        return next(
            f
            for f in self.run_model()
            if f["account_id"] == f"sim-account-{aid:03}" and f["control_id"] == control
        )

    def test_schema_and_fleet_distribution(self):
        Draft202012Validator.check_schema(SCHEMA)
        validate_model(self.fleet, self.policy, self.envs)
        self.assertEqual(
            Counter(a["environment"] for a in self.fleet["accounts"]),
            {"production": 3, "pre-production": 2, "testing": 2, "development": 3},
        )
        self.assertEqual(len(self.run_model()), 50)

    def test_repeatable_and_order_independent(self):
        expected = self.run_model()
        for key in self.fleet:
            if isinstance(self.fleet[key], list):
                self.fleet[key].reverse()
        self.assertEqual(expected, self.run_model())

    def test_pass_and_environment_specific_approval(self):
        self.assertEqual(self.finding(1, "baseline-encryption")["status"], "compliant")
        row = self.finding(9, "deployment-approval")
        self.assertFalse(row["desired_value"])
        self.assertFalse(row["observed_value"])
        self.assertEqual(row["status"], "compliant")

    def test_fail_with_active_exception_does_not_pass(self):
        row = self.finding(2, "baseline-encryption")
        self.assertEqual(row["status"], "noncompliant")
        self.assertEqual(row["exceptions"], [{"id": "exc-002", "state": "active"}])

    def test_expired_exception_does_not_pass(self):
        row = self.finding(8, "security-monitoring")
        self.assertEqual(row["status"], "noncompliant")
        self.assertEqual(row["exceptions"][0]["state"], "expired")

    def test_expiry_boundary(self):
        rows = self.run_model("2026-11-15T00:00:00Z")
        row = next(
            f
            for f in rows
            if f["account_id"] == "sim-account-002" and f["control_id"] == "baseline-encryption"
        )
        self.assertEqual(row["exceptions"][0]["state"], "expired")
        self.assertEqual(row["status"], "stale")

    def test_approval_not_yet_effective(self):
        self.fleet["exceptions"][0]["approved_at"] = "2026-11-01T00:00:00Z"
        self.fleet["exceptions"][0]["audit"][0]["at"] = "2026-11-01T00:00:00Z"
        row = self.finding(2, "baseline-encryption")
        self.assertEqual(row["exceptions"][0]["state"], "not-yet-active")
        self.assertEqual(row["status"], "noncompliant")

    def test_pending_exception(self):
        exc = self.fleet["exceptions"][0]
        exc.update(status="pending", approved_at=None, approver=None, approval_reference=None)
        exc["audit"] = [{"at": exc["created_at"], "action": "requested", "actor": exc["owner"]}]
        self.assertEqual(
            self.finding(2, "baseline-encryption")["exceptions"][0]["state"], "pending"
        )

    def test_missing_evidence(self):
        row = self.finding(4, "logging")
        self.assertEqual(
            (row["status"], row["reason"], row["observed_value"]),
            ("unknown", "missing-evidence", None),
        )
        self.assertEqual(summarize(self.run_model())["sim-account-007"]["controls"], {"unknown": 5})

    def test_stale_and_freshness_boundary(self):
        self.assertEqual(self.finding(3, "logging")["status"], "stale")
        self.fleet["evidence"][0]["observed_at"] = "2026-10-30T12:00:00Z"
        self.assertEqual(self.finding(1, "deployment-approval")["status"], "compliant")
        self.fleet["evidence"][0]["observed_at"] = "2026-10-30T11:59:59Z"
        self.assertEqual(self.finding(1, "deployment-approval")["status"], "stale")

    def test_future_evidence_and_revision_mismatch(self):
        self.fleet["evidence"][0]["observed_at"] = "2026-11-01T00:00:00Z"
        self.assertEqual(self.finding(1, "deployment-approval")["reason"], "future-evidence")
        self.fleet["evidence"][1]["observed_policy_version"] = "0.9.0"
        self.assertEqual(self.finding(1, "baseline-encryption")["status"], "unknown")
        self.assertEqual(self.finding(1, "baseline-encryption")["reason"], "revision-mismatch")

    def test_latest_evidence_selected(self):
        evidence = copy.deepcopy(self.fleet["evidence"][1])
        evidence.update(id="ev-new", observed_at="2026-10-31T11:00:00Z", observed_value=False)
        self.fleet["evidence"].append(evidence)
        self.assertEqual(self.finding(1, "baseline-encryption")["status"], "noncompliant")

    def test_required_explicit_timezone_and_timestamp(self):
        with self.assertRaises(TypeError):
            evaluate(self.fleet, self.policy, self.envs)
        for at in ["2026-10-31T12:00:00", "invalid", "2026-09-01T00:00:00Z"]:
            with self.subTest(at=at), self.assertRaises(ValueError):
                self.run_model(at)

    def test_schema_rejects_real_ids_missing_provenance_and_bad_types(self):
        for field, value in [
            ("id", "1" * 12),
            ("simulated", False),
            ("created_at", "bad"),
            ("schema_version", "2.0.0"),
        ]:
            row = copy.deepcopy(self.fleet["accounts"][0])
            row[field] = value
            with self.subTest(field=field), self.assertRaises(ValidationError):
                validate("account", row)
        for kind, row in [
            ("evidence", self.fleet["evidence"][0]),
            ("deployment", self.fleet["deployments"][0]),
        ]:
            row = copy.deepcopy(row)
            del row["source"]
            with self.assertRaises(ValidationError):
                validate(kind, row)
        row = copy.deepcopy(self.fleet["evidence"][0])
        row["observed_value"] = "true"
        with self.assertRaises(ValidationError):
            validate("evidence", row)

    def test_negative_semantic_contracts(self):
        mutations = [
            lambda f, p, e: f["accounts"].append(copy.deepcopy(f["accounts"][0])),
            lambda f, p, e: f["accounts"][0].update(ou_id="missing"),
            lambda f, p, e: f["accounts"][0].update(ou_id="sim-ou-testing"),
            lambda f, p, e: f["ous"][0].update(parent_id="sim-ou-production"),
            lambda f, p, e: f["ous"][1].update(parent_id=f["ous"][1]["id"]),
            lambda f, p, e: f["evidence"][0].update(account_id="sim-account-999"),
            lambda f, p, e: f["evidence"].append(dict(f["evidence"][0], id="duplicate-time")),
            lambda f, p, e: e[0]["requirements"].pop(),
            lambda f, p, e: e[0].update(policy_version="2.0.0"),
            lambda f, p, e: f["exceptions"][0].update(approver=None),
            lambda f, p, e: f["exceptions"][0].update(expires_at=f["exceptions"][0]["created_at"]),
            lambda f, p, e: f["deployments"][0].update(completed_at=None),
            lambda f, p, e: f["deployments"][0].update(observed_revision="wrong"),
            lambda f, p, e: f["drift"][0].update(status="in-sync"),
            lambda f, p, e: f["events"][0].update(subject_id="missing"),
            lambda f, p, e: f["events"][0].update(
                subject_id="deploy-001", account_id="sim-account-001"
            ),
            lambda f, p, e: f["events"][0].update(occurred_at="2026-10-31T11:00:00Z"),
        ]
        for index, mutate in enumerate(mutations):
            f, p, e = copy.deepcopy((self.fleet, self.policy, self.envs))
            mutate(f, p, e)
            with self.subTest(index=index), self.assertRaises((ValueError, ValidationError)):
                validate_model(f, p, e)

    def test_failure_dominates_incomplete_evidence(self):
        self.fleet["evidence"] = [
            e
            for e in self.fleet["evidence"]
            if not (e["account_id"] == "sim-account-002" and e["control_id"] == "logging")
        ]
        row = summarize(self.run_model())["sim-account-002"]
        self.assertEqual(row["status"], "noncompliant")
        self.assertEqual(row["controls"], {"compliant": 3, "noncompliant": 1, "unknown": 1})

    def test_baseline_cannot_be_weakened(self):
        for env_index in range(4):
            for cid in self.policy["baseline_requirements"]:
                with self.subTest(environment=env_index, control=cid):
                    envs = copy.deepcopy(self.envs)
                    next(r for r in envs[env_index]["requirements"] if r["control_id"] == cid)[
                        "expected"
                    ] = False
                    with self.assertRaisesRegex(ValueError, "weakens"):
                        validate_model(self.fleet, self.policy, envs)
        policy = copy.deepcopy(self.policy)
        policy["baseline_requirements"]["logging"] = False
        with self.assertRaises(ValidationError):
            validate_model(self.fleet, policy, self.envs)

    def test_expected_environment_profiles(self):
        for env in self.envs:
            requirements = {r["control_id"]: r for r in env["requirements"]}
            self.assertEqual(
                requirements["deployment-approval"]["expected"],
                env["id"] in {"production", "pre-production"},
            )
            expected_age = {
                "production": 24,
                "pre-production": 48,
                "testing": 72,
                "development": 168,
            }[env["id"]]
            self.assertTrue(all(r["max_age_hours"] == expected_age for r in requirements.values()))

    def test_event_subject_lookup_is_scoped_by_type(self):
        # IDs are unique per collection; collisions in other collections are valid.
        self.fleet["evidence"][0]["id"] = "deploy-005"
        validate_model(self.fleet, self.policy, self.envs)
        self.fleet["exceptions"][0]["id"] = "deploy-005"
        validate_model(self.fleet, self.policy, self.envs)

    def test_approval_requires_matching_audit(self):
        self.fleet["exceptions"][0]["audit"][0]["actor"] = "sim-unrelated-reviewer"
        with self.assertRaisesRegex(ValueError, "audit"):
            self.run_model()

    def test_evaluation_does_not_mutate_inputs(self):
        original = copy.deepcopy((self.fleet, self.policy, self.envs))
        self.run_model()
        self.assertEqual(original, (self.fleet, self.policy, self.envs))

    def test_exact_demo_summary(self):
        summary = summarize(self.run_model())
        self.assertEqual(
            [r["status"] for r in summary.values()],
            [
                "compliant",
                "noncompliant",
                "stale",
                "unknown",
                "noncompliant",
                "compliant",
                "unknown",
                "noncompliant",
                "compliant",
                "stale",
            ],
        )
        self.assertEqual(
            Counter(f["status"] for f in self.run_model()),
            {"compliant": 31, "noncompliant": 3, "unknown": 6, "stale": 10},
        )


if __name__ == "__main__":
    unittest.main()
