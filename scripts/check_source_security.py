"""Small deterministic tracked-source credential/artifact guard; never prints matched values."""

import re
import subprocess
from pathlib import Path

PATTERNS = [
    re.compile(rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    re.compile(rb"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
    re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----\s*[A-Za-z0-9+/=]{64,}"),
]


def validate(path, content):
    p = Path(path)
    if (
        any(
            part in {".aws", ".terraform", "node_modules", ".venv", "artifacts", "dist"}
            for part in p.parts
        )
        or p.suffix in {".zip", ".tfplan", ".tfstate"}
        or ".tfstate." in p.name
        or (p.suffix == ".tfvars" and not p.name.endswith(".example.tfvars"))
        or (p.name.startswith(".env") and not p.name.endswith(".example"))
    ):
        raise ValueError(f"Local/generated/sensitive path must not be tracked: {path}")
    if any(pattern.search(content) for pattern in PATTERNS):
        raise ValueError(f"Credential-shaped content detected in {path}; value suppressed")


def main():
    paths = subprocess.check_output(["git", "ls-files", "-z"]).decode().strip("\0").split("\0")
    for path in paths:
        validate(path, Path(path).read_bytes())
    print(
        f"Tracked-source security boundary passed for {len(paths)} files (pattern guard, not an exhaustive secret audit)."
    )


if __name__ == "__main__":
    main()
