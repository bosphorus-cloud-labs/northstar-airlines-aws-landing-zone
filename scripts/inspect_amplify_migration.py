"""Inspect a saved migration plan locally; print only checked scope, never secrets."""

import argparse
import importlib.util
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stage", required=True, choices=["retire_manual", "connect_repository", "create_main"]
    )
    parser.add_argument("--plan", required=True, type=Path)
    args = parser.parse_args()
    path = args.plan.resolve()
    if not path.is_relative_to((ROOT / "artifacts").resolve()) or path.suffix != ".tfplan":
        parser.error("Only protected ignored .tfplan artifacts are accepted")
    env = os.environ.copy()
    for name in ("TF_LOG", "TF_LOG_PATH", "TF_CLI_ARGS", "TF_CLI_ARGS_show"):
        env.pop(name, None)
    result = subprocess.run(
        ["terraform", "-chdir=terraform/poc", "show", "-json", str(path)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise RuntimeError("Local plan inspection failed; full output suppressed")
    spec = importlib.util.spec_from_file_location(
        "hosting_plan_check", ROOT / "terraform/poc/tests/check_github_hosting_plans.py"
    )
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    guard.check_live(json.loads(result.stdout), args.stage)


if __name__ == "__main__":
    main()
