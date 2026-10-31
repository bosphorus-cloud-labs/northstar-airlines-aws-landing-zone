"""Deterministic local lifecycle simulation. No SDK, subprocess, deployment or data publication."""

import argparse
import hashlib
import json
import tempfile
from collections import Counter
from copy import deepcopy
from datetime import timedelta
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker, ValidationError

from governance.model.contracts import ROOT, timestamp, validate_model
from governance.model.evaluate import evaluate, load_model, summarize

PROFILE = "policy-v2"
CONTROL = "audit-log-integrity"
SOURCE = "northstar-policy-rollout-v1"
REFERENCE_AT = "2026-10-31T12:00:00Z"
OUTPUT_ROOT = ROOT / "artifacts/policy-rollout"
PROVENANCE = {"schema_version": "1.0.0", "source": "northstar-synthetic-v1", "simulated": True}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def snapshot(fleet, policy, environments):
    return {"fleet": fleet, "policy": policy, "environments": environments}


def check_snapshot(value, profile="v1"):
    validate_model(value["fleet"], value["policy"], value["environments"], profile=profile)


def findings(value, at, profile="v1"):
    return evaluate(value["fleet"], value["policy"], value["environments"], at=at, profile=profile)


def counts(rows):
    return {
        status: Counter(r["status"] for r in rows)[status]
        for status in ("compliant", "noncompliant", "unknown", "stale")
    }


def proposal_snapshot(proposal):
    fleet = deepcopy(proposal["baseline"]["fleet"])
    for account in fleet["accounts"]:
        account["desired_policy_version"] = "2.0.0"
    return snapshot(fleet, proposal["policy"], proposal["environments"])


def validate_proposal(proposal):
    """Validate before approval; preserve all V1 controls/environment requirements."""
    baseline = proposal["baseline"]
    check_snapshot(baseline)
    target = proposal_snapshot(proposal)
    check_snapshot(target, PROFILE)
    original, policy = baseline["policy"], proposal["policy"]
    if (
        len(baseline["fleet"]["accounts"]) != 10
        or policy["id"] != original["id"]
        or policy["controls"][:-1] != original["controls"]
        or policy["controls"][-1]["id"] != CONTROL
        or policy["controls"][-1]["category"] != "detective-check"
        or {k: v for k, v in policy["baseline_requirements"].items() if k != CONTROL}
        != original["baseline_requirements"]
    ):
        raise ValueError(
            "Proposal must add exactly one detective control to the ten-account V1 model"
        )
    old_envs = {env["id"]: env for env in baseline["environments"]}
    for env in proposal["environments"]:
        previous = old_envs[env["id"]]
        old_requirements = [r for r in env["requirements"] if r["control_id"] != CONTROL]
        if old_requirements != previous["requirements"]:
            raise ValueError("Proposal changes existing environment requirements")
    scenario = proposal["scenario"]
    expected_ids = {a["id"] for a in baseline["fleet"]["accounts"]} | {"sim-account-011"}
    if (
        scenario.get("version") != "1.0.0"
        or scenario.get("simulated") is not True
        or set(scenario["new_control_observations"]) != expected_ids
        or any(
            v is not None and type(v) is not bool
            for v in scenario["new_control_observations"].values()
        )
    ):
        raise ValueError("Invalid synthetic observation scenario")
    canary = next((a for a in baseline["fleet"]["accounts"] if a["id"] == proposal["canary"]), None)
    if not canary or canary["lifecycle_status"] != "active":
        raise ValueError("Canary must be an existing active synthetic account")
    if not proposal["proposer"].startswith("sim-") or not proposal["proposer"].strip():
        raise ValueError("Use a synthetic proposer identity beginning sim-")
    findings(baseline, proposal["at"])


def clock(state):
    return (
        (timestamp(state["proposal"]["at"]) + timedelta(minutes=len(state["journal"])))
        .isoformat()
        .replace("+00:00", "Z")
    )


def record(state, action, detail, *, account_id=None, actor="sim-rollout-coordinator"):
    state["journal"].append(
        {
            "sequence": len(state["journal"]) + 1,
            "at": clock(state),
            "action": action,
            "detail": detail,
            "account_id": account_id,
            "actor": actor,
            "source": SOURCE,
            "simulated": True,
        }
    )


def plan(*, at=REFERENCE_AT, canary="sim-account-009", proposer="sim-policy-author"):
    proposal = {
        "baseline": snapshot(*load_model()),
        "policy": json.loads((ROOT / "governance/policies/v2.json").read_text()),
        "environments": [
            json.loads(p.read_text())
            for p in sorted((ROOT / "governance/environments/v2").glob("*.json"))
        ],
        "scenario": json.loads((ROOT / "governance/simulation/scenario.v1.json").read_text()),
        "at": at,
        "canary": canary,
        "proposer": proposer,
    }
    validate_proposal(proposal)
    state = {
        "format_version": "1.0.0",
        "source": SOURCE,
        "simulated": True,
        "contract_profile": PROFILE,
        "proposal": proposal,
        "proposal_digest": digest(proposal),
        "candidate": deepcopy(proposal_snapshot(proposal)),
        "phase": "planned",
        "approval": None,
        "results": {},
        "journal": [],
    }
    record(
        state,
        "policy.validated",
        "SIMULATED: contracts, references, baseline preservation and canary eligibility passed; no AWS policy was validated or deployed.",
        actor=proposer,
    )
    return state


def verify(state):
    schema = json.loads((ROOT / "governance/simulation/run.schema.json").read_text())
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(state)
    if (
        state.get("format_version") != "1.0.0"
        or state.get("source") != SOURCE
        or state.get("simulated") is not True
        or state.get("contract_profile") != PROFILE
        or state.get("phase") not in {"planned", "approved", "blocked", "rolled-out", "onboarded"}
        or digest(state["proposal"]) != state["proposal_digest"]
    ):
        raise ValueError("Invalid or changed simulation proposal")
    validate_proposal(state["proposal"])
    check_snapshot(state["candidate"], PROFILE)
    if (
        state["candidate"]["policy"] != state["proposal"]["policy"]
        or state["candidate"]["environments"] != state["proposal"]["environments"]
    ):
        raise ValueError("Candidate policy changed after proposal")
    approval = state["approval"]
    if approval and (
        approval["proposal_digest"] != state["proposal_digest"]
        or approval["approver"] == state["proposal"]["proposer"]
        or not approval["approver"].startswith("sim-")
    ):
        raise ValueError("Approval does not match the exact proposal and independent reviewer")
    if approval and not any(
        entry["action"] == "policy.approved"
        and entry["actor"] == approval["approver"]
        and entry["at"] == approval["at"]
        for entry in state["journal"]
    ):
        raise ValueError("Approval lacks a matching simulated audit event")
    if state["phase"] != "planned" and not approval:
        raise ValueError("Simulated approval required before rollout")
    for index, entry in enumerate(state["journal"]):
        expected = timestamp(state["proposal"]["at"]) + timedelta(minutes=index)
        if (
            entry["sequence"] != index + 1
            or timestamp(entry["at"]) != expected
            or entry["simulated"] is not True
        ):
            raise ValueError("Invalid simulation journal sequence")


def approve(state, approver):
    verify(state)
    if not approver.startswith("sim-") or approver == state["proposal"]["proposer"]:
        raise ValueError("An independent synthetic reviewer beginning sim- must approve")
    if state["approval"]:
        if state["approval"]["approver"] == approver:
            return
        raise ValueError("Proposal already approved by another simulated reviewer")
    state["approval"] = {
        "approver": approver,
        "proposal_digest": state["proposal_digest"],
        "at": clock(state),
    }
    state["phase"] = "approved"
    record(
        state,
        "policy.approved",
        "SIMULATED approval bound to the frozen policy, environments, baseline, scenario and canary.",
        actor=approver,
    )


def collect(state, account, attempt, at, *, new=False):
    """Explicit synthetic re-collection; never relabel historical evidence or erase failures."""
    fleet = state["candidate"]["fleet"]
    env = next(e for e in state["candidate"]["environments"] if e["id"] == account["environment"])
    for requirement in env["requirements"]:
        cid = requirement["control_id"]
        if cid == CONTROL:
            value = state["proposal"]["scenario"]["new_control_observations"][account["id"]]
        elif new:
            value = requirement["expected"]
        else:
            previous = [
                e
                for e in state["proposal"]["baseline"]["fleet"]["evidence"]
                if e["account_id"] == account["id"]
                and e["control_id"] == cid
                and timestamp(e["observed_at"]) <= timestamp(at)
            ]
            latest = max(previous, key=lambda e: timestamp(e["observed_at"])) if previous else None
            if not latest or timestamp(at) - timestamp(latest["observed_at"]) > timedelta(
                hours=requirement["max_age_hours"]
            ):
                continue
            value = latest["observed_value"]
        if value is not None:
            fleet["evidence"].append(
                {
                    **PROVENANCE,
                    "id": f"sim-phase5-evidence-{account['id']}-{attempt}-{cid}",
                    "account_id": account["id"],
                    "control_id": cid,
                    "observed_value": value,
                    "observed_at": at,
                    "observed_policy_version": "2.0.0",
                }
            )
        if cid == CONTROL:
            fleet["drift"] = [
                r
                for r in fleet["drift"]
                if not (r["account_id"] == account["id"] and r["control_id"] == CONTROL)
            ]
            fleet["drift"].append(
                {
                    **PROVENANCE,
                    "id": f"sim-phase5-drift-{account['id']}",
                    "account_id": account["id"],
                    "control_id": CONTROL,
                    "desired_value": True,
                    "observed_value": value,
                    "desired_revision": "policy-2.0.0",
                    "observed_revision": "policy-2.0.0" if value is not None else None,
                    "observed_at": at,
                    "status": "unknown" if value is None else "in-sync" if value else "drifted",
                }
            )


def attempt_account(state, account, *, fail=False, new=False):
    aid = account["id"]
    fleet = state["candidate"]["fleet"]
    attempts = (
        sum(d["id"].startswith(f"sim-phase5-deploy-{aid}-") for d in fleet["deployments"]) + 1
    )
    started = clock(state)
    record(
        state,
        "deployment.started",
        "SIMULATED AFT policy/checker distribution; no Terraform execution or security remediation.",
        account_id=aid,
    )
    completed = clock(state)
    deployment = {
        **PROVENANCE,
        "id": f"sim-phase5-deploy-{aid}-{attempts}",
        "account_id": aid,
        "tool": "aft",
        "desired_revision": "policy-2.0.0",
        "observed_revision": "policy-1.0.0" if fail else "policy-2.0.0",
        "status": "failed" if fail else "succeeded",
        "started_at": started,
        "completed_at": completed,
        "correlation_id": f"sim-phase5-{state['proposal_digest'][:12]}",
        "failure_reason": "SIMULATED AccessDenied: customization role permission check failed; no AWS call occurred."
        if fail
        else None,
    }
    fleet["deployments"].append(deployment)
    if fail:
        fleet["events"].append(
            {
                **PROVENANCE,
                "id": f"sim-phase5-event-{aid}-{attempts}",
                "account_id": aid,
                "type": "deployment.failed",
                "occurred_at": completed,
                "revision": "policy-2.0.0",
                "correlation_id": deployment["correlation_id"],
                "subject_id": deployment["id"],
            }
        )
    else:
        collect(state, account, attempts, completed, new=new)
    state["results"][aid] = deployment["status"]
    record(
        state,
        f"deployment.{deployment['status']}",
        deployment["failure_reason"]
        or "SIMULATED distribution succeeded. Compliance is evaluated independently.",
        account_id=aid,
    )
    return not fail


def rollout(state, *, fail_account=None):
    verify(state)
    if state["phase"] == "planned":
        raise ValueError("Simulated approval required before rollout")
    if state["phase"] in {"rolled-out", "onboarded"}:
        if fail_account:
            raise ValueError("Cannot inject a failure into an already completed rollout")
        return
    fleet = state["candidate"]["fleet"]
    canary = state["proposal"]["canary"]
    order = {"development": 0, "testing": 1, "pre-production": 2, "production": 3}
    targets = sorted(
        fleet["accounts"], key=lambda a: (a["id"] != canary, order[a["environment"]], a["id"])
    )
    pending = [
        a
        for a in targets
        if a["lifecycle_status"] == "active" and state["results"].get(a["id"]) != "succeeded"
    ]
    if fail_account and fail_account not in {a["id"] for a in pending}:
        raise ValueError("Failure injection must name a pending active synthetic account")
    for account in targets:
        aid = account["id"]
        if state["results"].get(aid) in {"succeeded", "deferred"}:
            continue
        if account["lifecycle_status"] != "active":
            state["results"][aid] = "deferred"
            record(
                state,
                "deployment.deferred",
                f"Lifecycle {account['lifecycle_status']}; target remains V2, no application or fresh evidence claimed.",
                account_id=aid,
            )
            continue
        if not attempt_account(state, account, fail=aid == fail_account):
            state["phase"] = "blocked"
            record(
                state,
                "rollout.blocked",
                "Stop on first deployment failure. Successful targets are preserved; pending targets remain unchanged.",
                account_id=aid,
            )
            return
        if aid == canary:
            result = summarize(findings(state["candidate"], state["journal"][-1]["at"], PROFILE))[
                aid
            ]
            if result["status"] != "compliant":
                state["results"][aid] = "gate-failed"
                state["phase"] = "blocked"
                record(
                    state,
                    "canary.rejected",
                    "All canary controls must be compliant; no fleet wave permitted.",
                    account_id=aid,
                )
                return
            record(
                state,
                "canary.passed",
                "All six synthetic controls passed; permit ordered fleet waves.",
                account_id=aid,
            )
    state["phase"] = "rolled-out"
    record(
        state,
        "rollout.completed",
        "Active targets distributed; inactive targets deferred. Findings are not remediated by policy distribution.",
    )


def onboard(state):
    verify(state)
    if state["phase"] == "onboarded":
        return
    if state["phase"] != "rolled-out":
        raise ValueError("Complete the active fleet rollout before onboarding")
    fleet = state["candidate"]["fleet"]
    aid = "sim-account-011"
    if any(a["id"] == aid for a in fleet["accounts"]):
        raise ValueError("New account ID already exists")
    account = {
        **PROVENANCE,
        "id": aid,
        "name": "NorthStar New Development",
        "environment": "development",
        "ou_id": "sim-ou-development",
        "lifecycle_status": "onboarding",
        "desired_policy_version": "2.0.0",
        "created_at": clock(state),
    }
    fleet["accounts"].append(account)
    fleet["events"].append(
        {
            **PROVENANCE,
            "id": "sim-phase5-account-created-011",
            "account_id": aid,
            "type": "account.created",
            "occurred_at": account["created_at"],
            "revision": "policy-2.0.0",
            "correlation_id": f"sim-phase5-{state['proposal_digest'][:12]}",
            "subject_id": aid,
        }
    )
    record(
        state,
        "account.created",
        "SIMULATED onboarding under approved V2; no AWS account provisioned.",
        account_id=aid,
    )
    attempt_account(state, account, new=True)
    summary = summarize(findings(state["candidate"], state["journal"][-1]["at"], PROFILE))
    if summary[aid]["status"] != "compliant":
        raise ValueError("New account must pass all six controls before activation")
    account["lifecycle_status"] = "active"
    state["phase"] = "onboarded"
    record(
        state,
        "account.activated",
        "Six synthetic controls evaluated under V2; existing findings/exceptions retained.",
        account_id=aid,
    )


def report(state):
    at = state["journal"][-1]["at"]
    rows = findings(state["candidate"], at, PROFILE)
    baseline = findings(state["proposal"]["baseline"], state["proposal"]["at"])
    summaries = summarize(rows)
    return {
        "source": SOURCE,
        "simulated": True,
        "contract_profile": PROFILE,
        "phase": state["phase"],
        "evaluated_at": at,
        "proposal_digest": state["proposal_digest"],
        "approval": state["approval"],
        "baseline": {
            "accounts": 10,
            "policy_version": "1.0.0",
            "finding_counts": counts(baseline),
            "account_summaries": summarize(baseline),
            "findings": baseline,
        },
        "current": {
            "accounts": len(summaries),
            "policy_version": "2.0.0",
            "finding_counts": counts(rows),
            "account_counts": counts(list(summaries.values())),
        },
        "rollout_results": state["results"],
        "accounts": summaries,
        "journal": state["journal"],
    }


def directory(path):
    resolved = path.resolve()
    if not resolved.is_relative_to(OUTPUT_ROOT.resolve()) or resolved == OUTPUT_ROOT.resolve():
        raise ValueError(
            "Run directories must be below artifacts/policy-rollout/; source and live data are never output targets"
        )
    return resolved


def save(path, state):
    verify(state)
    result = report(state)
    envelope = {"sha256": digest(state), "payload": state}
    outputs = {
        "report.json": result,
        "candidate-snapshot.json": {
            "source": SOURCE,
            "simulated": True,
            "contract_profile": PROFILE,
            "sha256": digest(state["candidate"]),
            "snapshot": state["candidate"],
        },
        "findings.json": findings(state["candidate"], result["evaluated_at"], PROFILE),
        "state.json": envelope,
    }
    path.mkdir(parents=True, exist_ok=True)
    if any((path / name).is_symlink() for name in outputs):
        raise ValueError("Simulation output files must not be symlinks")
    for name, value in outputs.items():
        with tempfile.NamedTemporaryFile(
            mode="w", dir=path, prefix=f".{name}.", suffix=".tmp", delete=False
        ) as output:
            temporary = Path(output.name)
            output.write(json.dumps(value, indent=2, sort_keys=True) + "\n")
        try:
            temporary.replace(path / name)
        finally:
            temporary.unlink(missing_ok=True)
    return result


def load(path):
    if (path / "state.json").is_symlink():
        raise ValueError("Simulation state must not be a symlink")
    envelope = json.loads((path / "state.json").read_text())
    if digest(envelope["payload"]) != envelope["sha256"]:
        raise ValueError("Simulation state checksum mismatch")
    verify(envelope["payload"])
    return envelope["payload"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    subcommands = {}
    for command in ["plan", "approve", "rollout", "onboard", "status"]:
        subcommands[command] = commands.add_parser(command)
        subcommands[command].add_argument("--run-dir", type=Path, default=OUTPUT_ROOT / "demo")
    subcommands["plan"].add_argument("--at", default=REFERENCE_AT)
    subcommands["plan"].add_argument("--canary", default="sim-account-009")
    subcommands["plan"].add_argument("--proposer", default="sim-policy-author")
    subcommands["approve"].add_argument("--approver", required=True)
    subcommands["rollout"].add_argument("--fail-account")
    args = parser.parse_args(argv)
    try:
        path = directory(args.run_dir)
        if args.command == "plan":
            if path.exists():
                raise ValueError("Run directory already exists; choose a new run name")
            state = plan(at=args.at, canary=args.canary, proposer=args.proposer)
            previous_entries = 0
        else:
            state = load(path)
            previous_entries = len(state["journal"])
            if args.command == "approve":
                if not args.approver:
                    raise ValueError("Explicit simulated approver required")
                approve(state, args.approver)
            elif args.command == "rollout":
                rollout(state, fail_account=args.fail_account)
            elif args.command == "onboard":
                onboard(state)
        result = report(state) if args.command == "status" else save(path, state)
        print("SIMULATED ONLY — no AWS calls, Terraform execution or DynamoDB publication")
        print(
            f"Phase: {result['phase']} | accounts: {result['current']['accounts']} | evaluated: {result['evaluated_at']}"
        )
        print("V1 baseline:", canonical(result["baseline"]["finding_counts"]))
        print("V2 findings:", canonical(result["current"]["finding_counts"]))
        print("Rollout:", canonical(result["rollout_results"]))
        print("Canary:", state["proposal"]["canary"])
        for entry in state["journal"][previous_entries:]:
            print(f"SIMULATED {entry['at']} {entry['action']} {entry['account_id'] or 'fleet'}")
        print(
            "Last event:", state["journal"][-1]["action"], "| proposal:", state["proposal_digest"]
        )
        return 2 if state["phase"] == "blocked" else 0
    except (ValueError, KeyError, OSError, TypeError, ValidationError) as exc:
        # No secrets/paths or arbitrary exception details are emitted.
        print(
            f"Simulation rejected ({type(exc).__name__}). Check inputs, approval, run directory and local JSON contracts."
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
