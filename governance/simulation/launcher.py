"""One-command offline rehearsal. Only fixed local subprocesses, never AWS or Terraform apply."""

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

from backend.repository import FixtureRepository
from governance.simulation import rollout
from governance.simulation.publication import candidate, prepare

ROOT = rollout.ROOT
INTERVIEW = rollout.OUTPUT_ROOT / "interview"


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as output:
        json.dump(value, output, indent=2, sort_keys=True)
        name = output.name
    Path(name).replace(path)


def install(snapshot, entries):
    version = prepare(snapshot, INTERVIEW / "snapshots")
    entries.append(
        {
            "policy_version": snapshot.policy["version"],
            "profile": "v1" if snapshot.context is None else snapshot.context["profile"],
            "evaluated_at": rollout.REFERENCE_AT
            if snapshot.context is None
            else snapshot.context["evaluated_at"],
            "snapshot_id": version,
            "generator": "northstar-synthetic-v1"
            if snapshot.context is None
            else snapshot.context["generator"],
            "file": f"snapshots/{version}.json",
        }
    )
    return version


def promote(entries, current_policy, current_run):
    """Move only the local current marker. Previously registered immutable history survives."""
    from backend.versions import LocalCatalog

    path = INTERVIEW / "catalog.json"
    if path.exists():
        LocalCatalog(path).view()  # Validate existing references before retaining history.
        known = {entry["policy_version"] for entry in entries}
        for entry in json.loads(path.read_text())["versions"]:
            if entry["policy_version"] not in known:
                entries.append(entry)
    atomic_json(
        path,
        {
            "format_version": "1.0.0",
            "simulated": True,
            "versions": entries,
            "current_policy_version": current_policy,
            "current_run": current_run,
        },
    )
    return path


def rehearse(version="v2"):
    INTERVIEW.mkdir(parents=True, exist_ok=True)
    entries = []
    print("[1/7] V1 baseline preserved — 10 synthetic accounts; no cloud access", flush=True)
    install(FixtureRepository().read_snapshot(), entries)
    if version in {"v1", "reset"}:
        promote(entries, "1.0.0", "baseline")
        print("V1 selected locally. Historical snapshots retained. Live AWS is unchanged.")
        return INTERVIEW / "catalog.json"
    run = next(
        INTERVIEW / f"run-{index:04}"
        for index in range(1, 10000)
        if not (INTERVIEW / f"run-{index:04}").exists()
    )
    state = rollout.plan()
    rollout.save(run, state)
    print(
        "[2/7] REAL Terraform fmt / init -backend=false / validate / plan (zero providers/resources)",
        flush=True,
    )
    tf = ["terraform", f"-chdir={ROOT / 'terraform/simulation'}"]
    commands = [
        ["terraform", "fmt", "-check", "-recursive", str(ROOT / "terraform/simulation")],
        [
            "terraform",
            "fmt",
            "-check",
            "-recursive",
            str(ROOT / "terraform/modules/simulated_governance"),
        ],
        [*tf, "init", "-backend=false", "-input=false", "-no-color"],
        [*tf, "validate", "-no-color"],
        [
            *tf,
            "plan",
            "-input=false",
            "-refresh=false",
            "-no-color",
            f"-var=run_directory={run}",
            f"-out={run / 'v2.tfplan'}",
        ],
    ]
    # Never inherit a POC backend/cache, workspace, injected CLI arguments or variables.
    terraform_env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("TF_CLI_ARGS", "TF_VAR_"))
        and key
        not in {
            "TF_DATA_DIR",
            "TF_WORKSPACE",
            "TF_CLI_CONFIG_FILE",
            "TF_PLUGIN_CACHE_DIR",
            "TF_REATTACH_PROVIDERS",
        }
    }
    terraform_env.update(
        CHECKPOINT_DISABLE="1", TF_IN_AUTOMATION="1", TF_DATA_DIR=str(run / "terraform-data")
    )
    with (run / "terraform.log").open("w") as log:
        for command in commands:
            subprocess.run(
                command,
                cwd=ROOT,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=True,
                timeout=60,
                env=terraform_env,
            )
    plan = json.loads(
        subprocess.check_output(
            [*tf, "show", "-json", str(run / "v2.tfplan")],
            cwd=ROOT,
            timeout=30,
            env=terraform_env,
        )
    )
    from governance.simulation.terraform_plan import verify_plan

    verify_plan(plan, state)
    atomic_json(run / "v2.plan.json", plan)
    print("      Desired policy matches the Python proposal for all 10 accounts.", flush=True)
    rollout.approve(state, "sim-security-reviewer")
    print(
        "[3/7] SIMULATED independent approval bound to proposal",
        state["proposal_digest"][:12],
        flush=True,
    )
    rollout.rollout(state, fail_account="sim-account-005")
    if state["phase"] != "blocked" or not any(
        e["action"] == "canary.passed" for e in state["journal"]
    ):
        raise ValueError("Expected canary success and controlled failure")
    rollout.save(run, state)
    print(
        "[4/7] SIMULATED canary 009 passed; account 005 failed; stopped before Production",
        flush=True,
    )
    rollout.rollout(state)
    print(
        "[5/7] SIMULATED retry completed; successful targets preserved; 2 inactive accounts deferred",
        flush=True,
    )
    rollout.onboard(state)
    result = rollout.save(run, state)
    print("[6/7] SIMULATED onboarding: account 011; 11 accounts / 66 findings", flush=True)
    version_id = install(candidate(state, plan), entries)
    promote(entries, "2.0.0", run.name)
    print("[7/7] LOCAL immutable V2 snapshot ready:", version_id[:16], flush=True)
    print("      Findings:", rollout.canonical(result["current"]["finding_counts"]), flush=True)
    print(
        "      Offline publication package prepared. NOTHING published to DynamoDB or AWS.",
        flush=True,
    )
    return INTERVIEW / "catalog.json"


def serve(catalog):
    owner_file = INTERVIEW / "servers.json"
    occupied = []
    for port in (8000, 5173):
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                occupied.append(port)
    if occupied:
        if len(occupied) == 2 and owner_file.exists():
            owner = json.loads(owner_file.read_text())
            if owner.get("catalog") == str(catalog.resolve()):
                try:
                    for pid in [owner["launcher"], *owner["children"]]:
                        if type(pid) is not int or pid <= 1:
                            raise ValueError("Invalid local server ownership")
                        os.kill(pid, 0)
                    print(
                        "Existing owned rehearsal servers retained. Refresh the browser once to see CURRENT governance."
                    )
                    return
                except (ProcessLookupError, PermissionError, KeyError):
                    pass
        raise ValueError(
            "Local port occupied by an unverified service; no process stopped. Use --prepare-only or free the port."
        )
    children = []
    logs = []

    def interrupted(signum, frame):
        raise KeyboardInterrupt

    old = signal.signal(signal.SIGTERM, interrupted)
    try:
        for name, command, cwd, env in [
            (
                "api",
                [sys.executable, "-m", "backend", "--local-demo", "--demo-catalog", str(catalog)],
                ROOT,
                os.environ,
            ),
            (
                "frontend",
                ["npm", "run", "dev"],
                ROOT / "frontend",
                {**os.environ, "VITE_AUTH_MODE": "local"},
            ),
        ]:
            log = (INTERVIEW / f"{name}.log").open("w")
            logs.append(log)
            children.append(
                subprocess.Popen(
                    command,
                    cwd=cwd,
                    env=env,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
            )
        atomic_json(
            owner_file,
            {
                "launcher": os.getpid(),
                "children": [child.pid for child in children],
                "catalog": str(catalog.resolve()),
            },
        )
        print(
            "\nOpen http://127.0.0.1:5173 — CURRENT follows the governance marker; History retains prior snapshots.",
            flush=True,
        )
        print(
            "LOCAL LOOPBACK DEMO ONLY. Hosted Cognito authentication is unchanged. Ctrl-C stops owned servers.",
            flush=True,
        )
        while True:
            for child in children:
                try:
                    code = child.wait(timeout=0.5)
                    raise RuntimeError(
                        f"Local server exited ({code}); inspect local rehearsal logs."
                    )
                except subprocess.TimeoutExpired:
                    pass
    except KeyboardInterrupt:
        print("\nLocal servers stopped. Snapshots retained; no AWS changes.")
    finally:
        signal.signal(signal.SIGTERM, old)
        if (
            owner_file.exists()
            and json.loads(owner_file.read_text()).get("launcher") == os.getpid()
        ):
            owner_file.unlink()
        for child in children:
            try:
                os.killpg(child.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        for child in children:
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                child.wait()
        for log in logs:
            log.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", choices=["v1", "v2", "reset"])
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    try:
        catalog = rehearse(args.version)
        if args.version != "reset" and not args.prepare_only:
            serve(catalog)
        return 0
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"Rehearsal stopped safely: {exc}", file=sys.stderr)
        print(
            "No AWS publication attempted. Use V1 or the existing hosted dashboard as fallback.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
