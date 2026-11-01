"""Fail-closed GitHub metadata checks before any AWS OIDC credential request."""

import argparse
import json
import os
import re
import subprocess

REPOSITORY = "bosphorus-cloud-labs/northstar-airlines-aws-landing-zone"
ENVIRONMENT = "governance-production"


def api(path):
    result = subprocess.run(["gh", "api", path], check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def verify(sha, digest, *, get=api, env=None):
    env = os.environ if env is None else env
    if (
        env.get("GITHUB_REF") != "refs/heads/main"
        or env.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
        or env.get("GITHUB_REPOSITORY") != REPOSITORY
        or env.get("GITHUB_SHA") != sha
    ):
        raise ValueError("CD must run on the exact current main workflow commit")
    if not re.fullmatch(r"[a-f0-9]{40}", sha) or not re.fullmatch(r"[a-f0-9]{64}", digest):
        raise ValueError("Exact reviewed commit and approved snapshot digest are required")
    root = f"repos/{REPOSITORY}"
    environment = get(f"{root}/environments/{ENVIRONMENT}")
    reviews = [
        r for r in environment.get("protection_rules", []) if r["type"] == "required_reviewers"
    ]
    if (
        len(reviews) != 1
        or not reviews[0].get("reviewers")
        or reviews[0].get("prevent_self_review") is not True
    ):
        raise ValueError(
            "Protected environment needs required reviewers and self-review prevention"
        )
    # Public REST does not currently expose the UI's admin-bypass setting.
    # Require its manual owner review; reject it if a server explicitly reports bypass.
    if environment.get("can_admins_bypass") is True:
        raise ValueError("Disable administrator bypass of environment protection")
    rules = get(f"{root}/environments/{ENVIRONMENT}/deployment-branch-policies").get(
        "branch_policies", []
    )
    if len(rules) != 1 or rules[0]["name"] != "main" or rules[0].get("type", "branch") != "branch":
        raise ValueError("Protected environment must allow only the exact main branch")
    policy = environment.get("deployment_branch_policy") or {}
    if policy.get("custom_branch_policies") is not True:
        raise ValueError("Explicit main-only deployment policy is required")
    runs = get(
        f"{root}/actions/workflows/governance-ci.yml/runs?event=push&head_sha={sha}&per_page=100"
    ).get("workflow_runs", [])
    if not any(
        r.get("head_sha") == sha
        and r.get("event") == "push"
        and r.get("status") == "completed"
        and r.get("conclusion") == "success"
        for r in runs
    ):
        raise ValueError("Successful unprivileged main CI for the exact source commit is required")
    pulls = get(f"{root}/commits/{sha}/pulls?per_page=100")
    approved = False
    for pr in pulls:
        if (
            not pr.get("merged_at")
            or pr.get("merge_commit_sha") != sha
            or pr["base"]["ref"] != "main"
        ):
            continue
        latest = {}
        review_records = get(f"{root}/pulls/{pr['number']}/reviews?per_page=100")
        if len(review_records) >= 100:
            raise ValueError(
                "Review pagination budget reached; inspect all reviews before delivery"
            )
        for review in review_records:
            if (
                review.get("author_association") not in {"OWNER", "MEMBER", "COLLABORATOR"}
                or review["user"].get("type") == "Bot"
                or not review.get("submitted_at")
                or review["submitted_at"] > pr["merged_at"]
            ):
                continue
            if review["state"] in {"APPROVED", "CHANGES_REQUESTED", "DISMISSED"}:
                latest[review["user"]["login"]] = review
        if any(r["state"] == "CHANGES_REQUESTED" for r in latest.values()):
            continue
        approved = any(
            user != pr["user"]["login"]
            and r["state"] == "APPROVED"
            and r.get("commit_id") == pr["head"]["sha"]
            for user, r in latest.items()
        )
        if approved:
            break
    if not approved:
        raise ValueError(
            "The merged source PR needs an independent approval of its final head commit"
        )
    return {"source_commit": sha, "approved_digest": digest, "environment": ENVIRONMENT}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--digest", required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.sha, args.digest)))


if __name__ == "__main__":
    main()
