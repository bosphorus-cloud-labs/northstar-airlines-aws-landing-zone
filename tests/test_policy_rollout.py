"""Offline policy lifecycle, approval gates and backward compatibility."""

import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from jsonschema import Draft202012Validator, ValidationError

from compliance_engine.contracts import SCHEMA, schema_for, validate, validate_model
from compliance_engine.evaluate import evaluate, load_model
from governance.simulation import rollout as sim

V1_COUNTS = {"compliant": 31, "noncompliant": 3, "unknown": 6, "stale": 10}
V2_COUNTS = {"compliant": 37, "noncompliant": 4, "unknown": 9, "stale": 10}
FINAL_COUNTS = {"compliant": 43, "noncompliant": 4, "unknown": 9, "stale": 10}


class PolicyRolloutTests(unittest.TestCase):
    def test_run_schema_and_matching_approval_audit_are_required(self):
        with self.assertRaises(ValidationError):
            sim.verify([])
        state = self.approved()
        state["approval"]["at"] = "2026-10-31T12:01:01Z"
        with self.assertRaisesRegex(ValueError, "audit"):
            sim.verify(state)
        state = self.approved()
        state["journal"][0]["simulated"] = False
        with self.assertRaises(ValidationError):
            sim.verify(state)

    def test_output_directory_and_file_symlinks_cannot_escape(self):
        with tempfile.TemporaryDirectory() as temp, tempfile.TemporaryDirectory() as outside:
            root = Path(temp)
            external = Path(outside)
            sentinel = external / "sentinel.json"
            sentinel.write_text("must-not-read-or-write")
            (root / "escape").symlink_to(external, target_is_directory=True)
            with patch.object(sim, "OUTPUT_ROOT", root):
                with self.assertRaises(ValueError):
                    sim.directory(root / "escape/demo")
                run = root / "demo"
                run.mkdir()
                (run / "state.json").symlink_to(sentinel)
                with self.assertRaises(ValueError):
                    sim.load(run)
                with self.assertRaises(ValueError):
                    sim.save(run, sim.plan())
            self.assertEqual(sentinel.read_text(), "must-not-read-or-write")

    def approved(self, **kwargs):
        state = sim.plan(**kwargs)
        sim.approve(state, "sim-security-reviewer")
        return state

    def deployments(self, state):
        return [
            d
            for d in state["candidate"]["fleet"]["deployments"]
            if d["id"].startswith("sim-phase5-")
        ]

    def test_v1_defaults_and_source_fixtures_are_unchanged(self):
        before = copy.deepcopy(load_model())
        schema = copy.deepcopy(SCHEMA)
        state = self.approved()
        sim.rollout(state)
        sim.onboard(state)
        self.assertEqual(load_model(), before)
        self.assertEqual(SCHEMA, schema)
        self.assertEqual(sim.counts(evaluate(*load_model(), at=sim.REFERENCE_AT)), V1_COUNTS)
        self.assertEqual(len(load_model()[2]), 4)
        with self.assertRaises(ValidationError):
            validate_model(**state["candidate"])
        with self.assertRaises(ValidationError):
            validate(
                "finding",
                next(
                    f
                    for f in sim.findings(
                        state["candidate"], sim.report(state)["evaluated_at"], sim.PROFILE
                    )
                    if f["control_id"] == sim.CONTROL
                ),
            )

    def test_opt_in_schema_preserves_v1_record_shapes_and_rejects_unknown_profiles(self):
        Draft202012Validator.check_schema(schema_for(sim.PROFILE))
        state = sim.plan()
        sim.check_snapshot(state["candidate"], sim.PROFILE)
        for row in state["candidate"]["fleet"]["accounts"]:
            self.assertTrue(row["simulated"])
            self.assertEqual(row["schema_version"], "1.0.0")
        with self.assertRaises(ValueError):
            schema_for("unknown")

    def test_policy_adds_exactly_one_requirement_in_all_four_environments(self):
        state = sim.plan()
        self.assertEqual(len(state["candidate"]["policy"]["controls"]), 6)
        for env in state["candidate"]["environments"]:
            self.assertEqual(env["policy_version"], "2.0.0")
            self.assertEqual(len(env["requirements"]), 6)
            self.assertTrue(
                next(r["expected"] for r in env["requirements"] if r["control_id"] == sim.CONTROL)
            )

    def test_validation_rejects_baseline_weakening_or_changed_requirements(self):
        for mutate in [
            lambda p: p["policy"]["baseline_requirements"].update(logging=False),
            lambda p: p["environments"][0]["requirements"][0].update(max_age_hours=1000),
            lambda p: p["policy"]["controls"][0].update(description="changed"),
            lambda p: p["scenario"]["new_control_observations"].update({"sim-account-001": "true"}),
        ]:
            proposal = copy.deepcopy(sim.plan()["proposal"])
            mutate(proposal)
            with self.assertRaises((ValueError, ValidationError)):
                sim.validate_proposal(proposal)

    def test_missing_self_or_changed_proposal_approval_prevents_rollout(self):
        state = sim.plan()
        with self.assertRaisesRegex(ValueError, "approval"):
            sim.rollout(state)
        self.assertEqual(self.deployments(state), [])
        with self.assertRaises(ValueError):
            sim.approve(state, state["proposal"]["proposer"])
        with self.assertRaises(ValueError):
            sim.approve(state, "real-person")
        sim.approve(state, "sim-security-reviewer")
        state["proposal"]["canary"] = "sim-account-001"
        with self.assertRaises(ValueError):
            sim.rollout(state)
        state["proposal_digest"] = sim.digest(state["proposal"])
        with self.assertRaisesRegex(ValueError, "Approval"):
            sim.rollout(state)

    def test_canary_failure_stops_before_any_other_target_and_can_resume(self):
        state = self.approved()
        sim.rollout(state, fail_account="sim-account-009")
        self.assertEqual(state["phase"], "blocked")
        self.assertEqual([d["account_id"] for d in self.deployments(state)], ["sim-account-009"])
        self.assertEqual(
            state["candidate"]["fleet"]["evidence"],
            state["proposal"]["baseline"]["fleet"]["evidence"],
        )
        with self.assertRaises(ValueError):
            sim.onboard(state)
        sim.rollout(state)
        self.assertEqual(state["phase"], "rolled-out")
        self.assertEqual(sim.report(state)["current"]["finding_counts"], V2_COUNTS)

    def test_canary_compliance_gate_also_blocks_successful_distribution(self):
        state = self.approved(canary="sim-account-002")
        sim.rollout(state)
        self.assertEqual(state["phase"], "blocked")
        self.assertEqual(state["results"], {"sim-account-002": "gate-failed"})
        self.assertEqual(self.deployments(state)[0]["status"], "succeeded")
        self.assertEqual(state["journal"][-1]["action"], "canary.rejected")

    def test_mid_wave_failure_stops_and_retry_does_not_redeploy_successes(self):
        state = self.approved()
        sim.rollout(state, fail_account="sim-account-005")
        self.assertEqual(state["phase"], "blocked")
        self.assertEqual(self.deployments(state)[0]["account_id"], "sim-account-009")
        self.assertFalse(
            any(
                d["account_id"] in {"sim-account-001", "sim-account-002", "sim-account-003"}
                for d in self.deployments(state)
            )
        )
        successful_ids = {d["id"] for d in self.deployments(state) if d["status"] == "succeeded"}
        sim.rollout(state)
        self.assertEqual(len(self.deployments(state)), 9)
        self.assertTrue(successful_ids.issubset({d["id"] for d in self.deployments(state)}))
        self.assertEqual(
            sum(d["account_id"] == "sim-account-009" for d in self.deployments(state)), 1
        )
        self.assertEqual(sim.report(state)["current"]["finding_counts"], V2_COUNTS)
        sim.check_snapshot(state["candidate"], sim.PROFILE)

    def test_inactive_accounts_deferred_without_claiming_application(self):
        state = self.approved()
        sim.rollout(state)
        for aid in ["sim-account-007", "sim-account-010"]:
            self.assertEqual(state["results"][aid], "deferred")
            self.assertFalse(any(d["account_id"] == aid for d in self.deployments(state)))
            self.assertFalse(
                any(
                    e["account_id"] == aid and e["control_id"] == sim.CONTROL
                    for e in state["candidate"]["fleet"]["evidence"]
                )
            )

    def test_evidence_semantics_exceptions_and_deployment_success_remain_independent(self):
        state = self.approved()
        sim.rollout(state)
        rows = sim.findings(state["candidate"], sim.report(state)["evaluated_at"], sim.PROFILE)

        def finding(aid, control):
            return next(f for f in rows if f["account_id"] == aid and f["control_id"] == control)

        self.assertEqual(finding("sim-account-004", sim.CONTROL)["status"], "noncompliant")
        self.assertEqual(state["results"]["sim-account-004"], "succeeded")
        self.assertEqual(finding("sim-account-006", sim.CONTROL)["reason"], "missing-evidence")
        self.assertEqual(finding("sim-account-003", "logging")["status"], "stale")
        self.assertEqual(
            finding("sim-account-002", "baseline-encryption")["exceptions"][0]["state"], "active"
        )
        self.assertEqual(
            finding("sim-account-002", "baseline-encryption")["status"], "noncompliant"
        )
        self.assertEqual(
            finding("sim-account-008", "security-monitoring")["exceptions"][0]["state"], "expired"
        )
        original = state["proposal"]["baseline"]["fleet"]["evidence"]
        self.assertEqual(state["candidate"]["fleet"]["evidence"][: len(original)], original)
        # While unrolled observations have revision mismatches, V1 violations remain in the report.
        baseline = sim.report(sim.plan())["baseline"]["findings"]
        self.assertEqual(sum(f["status"] == "noncompliant" for f in baseline), 3)

    def test_onboarding_has_eleven_accounts_and_six_validated_new_account_controls(self):
        state = self.approved()
        sim.rollout(state)
        sim.onboard(state)
        result = sim.report(state)
        self.assertEqual(result["current"]["accounts"], 11)
        self.assertEqual(result["current"]["finding_counts"], FINAL_COUNTS)
        self.assertEqual(result["accounts"]["sim-account-011"]["controls"], {"compliant": 6})
        self.assertEqual(result["baseline"]["finding_counts"], V1_COUNTS)
        self.assertEqual(len(state["proposal"]["baseline"]["fleet"]["accounts"]), 10)
        sim.check_snapshot(state["candidate"], sim.PROFILE)

    def test_completed_commands_are_idempotent_and_bad_failure_targets_rejected(self):
        state = self.approved()
        for aid in ["sim-account-999", "sim-account-010"]:
            with self.assertRaises(ValueError):
                sim.rollout(state, fail_account=aid)
        sim.rollout(state)
        sim.onboard(state)
        before = copy.deepcopy(state)
        sim.rollout(state)
        sim.onboard(state)
        sim.approve(state, "sim-security-reviewer")
        self.assertEqual(state, before)

    def test_deterministic_without_clock_aws_or_subprocess_operations(self):
        def run():
            state = self.approved()
            sim.rollout(state, fail_account="sim-account-005")
            sim.rollout(state)
            sim.onboard(state)
            return state, sim.report(state)

        with (
            patch("boto3.client", side_effect=AssertionError("AWS forbidden")),
            patch("time.time", side_effect=AssertionError("Wall clock forbidden")),
            patch("subprocess.run", side_effect=AssertionError("External command forbidden")),
        ):
            self.assertEqual(run(), run())
        with self.assertRaises(ValueError):
            sim.plan(at="2026-10-31T12:00:00")
        with self.assertRaises(ValueError):
            sim.plan(at="2020-01-01T00:00:00Z")

    def test_cli_persistence_exit_codes_checksum_idempotence_and_output_boundary(self):
        with (
            tempfile.TemporaryDirectory() as temp,
            patch.object(sim, "OUTPUT_ROOT", Path(temp)),
            redirect_stdout(io.StringIO()) as output,
        ):
            directory = Path(temp) / "demo"
            args = ["--run-dir", str(directory)]
            self.assertEqual(sim.main(["plan", *args]), 0)
            self.assertEqual(sim.main(["plan", *args]), 1)
            self.assertEqual(sim.main(["rollout", *args]), 1)
            self.assertEqual(sim.main(["approve", *args, "--approver", "sim-security-reviewer"]), 0)
            self.assertEqual(sim.main(["rollout", *args, "--fail-account", "sim-account-005"]), 2)
            self.assertEqual(sim.main(["rollout", *args]), 0)
            self.assertEqual(sim.main(["onboard", *args]), 0)
            before = (directory / "state.json").read_bytes()
            self.assertEqual(sim.main(["status", *args]), 0)
            self.assertEqual((directory / "state.json").read_bytes(), before)
            candidate = json.loads((directory / "candidate-snapshot.json").read_text())
            self.assertTrue(candidate["simulated"])
            self.assertEqual(candidate["sha256"], sim.digest(candidate["snapshot"]))
            envelope = json.loads(before)
            envelope["payload"]["phase"] = "approved"
            (directory / "state.json").write_text(json.dumps(envelope))
            self.assertEqual(sim.main(["status", *args]), 1)
            self.assertEqual(sim.main(["plan", "--run-dir", str(Path(temp).parent / "outside")]), 1)
            self.assertIn("SIMULATED ONLY", output.getvalue())
