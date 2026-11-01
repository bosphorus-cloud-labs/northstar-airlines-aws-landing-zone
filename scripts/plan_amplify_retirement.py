"""Read-only Stage A plan; preserve recorded token input without exposing it."""

import importlib.util
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_json(command, env):
    result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError("Read-only Terraform inspection failed; full output suppressed")
    return json.loads(result.stdout)


def main():
    os.umask(0o077)
    env = os.environ.copy()
    for name in ("TF_LOG", "TF_LOG_PATH", "TF_CLI_ARGS", "TF_CLI_ARGS_plan", "TF_CLI_ARGS_show"):
        env.pop(name, None)
    env.update(AWS_PROFILE="north", AWS_REGION="eu-central-1", TF_INPUT="0", TF_IN_AUTOMATION="1")
    state = run_json(["terraform", "-chdir=terraform/poc", "state", "pull"], env)
    app = next(
        resource
        for resource in state["resources"]
        if resource.get("module") == "module.hosting"
        and resource["type"] == "aws_amplify_app"
        and resource["name"] == "console"
    )
    recorded_token = app["instances"][0]["attributes"].get("access_token")
    # A failed UpdateApp may have recorded the secret. A null/different input
    # would introduce an unrelated app update while planning branch retirement.
    if recorded_token:
        env["TF_VAR_github_access_token"] = recorded_token
    else:
        env.pop("TF_VAR_github_access_token", None)
    (ROOT / "artifacts").mkdir(exist_ok=True)
    plan_path = "../../artifacts/amplify-retire-manual.tfplan"
    command = [
        "terraform",
        "-chdir=terraform/poc",
        "plan",
        "-input=false",
        "-lock=false",
        "-no-color",
        "-detailed-exitcode",
        "-var=enable_github_hosting=true",
        "-var=github_auto_build_enabled=false",
        "-var=hosting_migration_stage=retire_manual",
        f"-out={plan_path}",
    ]
    result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
    if result.returncode not in (0, 2):
        raise RuntimeError(
            "Stage A plan failed; full output suppressed to protect state/token data"
        )
    plan = run_json(["terraform", "-chdir=terraform/poc", "show", "-json", plan_path], env)
    path = ROOT / "terraform/poc/tests/check_github_hosting_plans.py"
    spec = importlib.util.spec_from_file_location("hosting_plan_check", path)
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    guard.check_live(plan, "retire_manual")
    print("Recorded token input preserved in memory; no token output or settings file changes.")
    print(
        "Protected ignored plan: artifacts/amplify-retire-manual.tfplan (contains state/secrets)."
    )
    print(
        "Plan used read-only refresh without lock writes. No apply, deletion or build was executed."
    )


if __name__ == "__main__":
    main()
