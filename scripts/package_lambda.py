"""Reproducible ZIP assembly from preinstalled Linux ARM64 wheels; no network or AWS calls."""

import argparse
import hashlib
import json
import re
import zipfile
from email.parser import Parser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def runtime_pins(path=ROOT / "backend/requirements.txt") -> dict[str, str]:
    result = {}
    for line in path.read_text().splitlines():
        if line.startswith("-r "):
            result.update(runtime_pins((path.parent / line[3:]).resolve()))
        elif line and not line.startswith("#"):
            name, version = line.split("==")
            result[re.sub(r"[-_.]+", "-", name).lower()] = version
    return result


def package(vendor: Path, output: Path) -> str:
    wheels = list(vendor.glob("*.dist-info/WHEEL"))
    installed = {}
    for wheel in wheels:
        metadata = Parser().parsestr((wheel.parent / "METADATA").read_text())
        name = re.sub(r"[-_.]+", "-", metadata["Name"]).lower()
        if name in installed:
            raise ValueError("Duplicate installed dependency metadata")
        installed[name] = metadata["Version"]
    if installed != runtime_pins():
        raise ValueError(
            "Vendor must contain exactly the complete pinned runtime, with no stale dependencies"
        )
    for wheel in wheels:
        tags = [
            line.removeprefix("Tag: ")
            for line in wheel.read_text().splitlines()
            if line.startswith("Tag: ")
        ]
        if not tags or not any(
            tag.endswith("-none-any")
            or (
                "manylinux" in tag
                and "aarch64" in tag
                and (tag.startswith("cp313-") or "-abi3-" in tag)
            )
            for tag in tags
        ):
            raise ValueError("Vendor contains non-Linux/ARM64/Python 3.13 wheels")
    files = {}
    for path in vendor.rglob("*"):
        relative = path.relative_to(vendor)
        if (
            any(part in {".aws", ".git"} for part in relative.parts)
            or path.name.startswith(".env")
            or path.suffix == ".tfstate"
        ):
            raise ValueError("Local configuration or credentials must not enter the artifact")
        if path.is_symlink():
            raise ValueError("Vendor symlinks are not supported")
        if (
            path.is_file()
            and not any(part in {"__pycache__", "tests"} for part in relative.parts)
            and path.suffix != ".pyc"
            and path.relative_to(vendor).parts[0] != "bin"
        ):
            content = path.read_bytes()
            if (
                b"-----BEGIN PRIVATE KEY-----" in content
                or b"-----BEGIN RSA PRIVATE KEY-----" in content
            ):
                raise ValueError("Private keys must not enter the artifact")
            files[path.relative_to(vendor).as_posix()] = content
    for directory in ["backend", "governance"]:
        for path in (ROOT / directory).rglob("*.py"):
            if "__pycache__" not in path.parts:
                files[path.relative_to(ROOT).as_posix()] = path.read_bytes()
    for name in ["v1.schema.json", "policy-v2.profile.json"]:
        schema = ROOT / "governance/contracts" / name
        files[f"governance/contracts/{name}"] = schema.read_bytes()
    # Never ship local fixture data, tests, local environments, Terraform, or credentials.
    files["PACKAGE_MANIFEST.json"] = json.dumps(
        {
            "runtime": "python3.13",
            "architecture": "arm64",
            "files": {
                name: hashlib.sha256(content).hexdigest() for name, content in sorted(files.items())
            },
        },
        sort_keys=True,
    ).encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, content in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, content)
    return hashlib.sha256(output.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vendor", type=Path, default=ROOT / "artifacts/lambda/vendor")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/lambda/function.zip")
    args = parser.parse_args()
    print("Offline Lambda artifact SHA-256:", package(args.vendor, args.output))


if __name__ == "__main__":
    main()
