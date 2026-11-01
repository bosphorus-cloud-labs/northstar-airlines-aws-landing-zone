"""Server-owned version allowlists. No browser-controlled snapshot IDs or write operations."""

import json
import re
from dataclasses import dataclass
from pathlib import Path

from backend.deployment.snapshot import digest
from backend.repository import GovernanceRepository
from governance.model.contracts import timestamp

DEMO_AT = "2026-10-31T12:00:00Z"


class UnknownVersion(Exception):
    pass


@dataclass(frozen=True)
class Version:
    policy_version: str
    profile: str
    evaluated_at: str
    repository: GovernanceRepository
    snapshot_id: str | None = None
    generator: str = "northstar-synthetic-v1"

    def descriptor(self):
        return {
            "policy_version": self.policy_version,
            "profile": self.profile,
            "evaluated_at": self.evaluated_at,
            "snapshot_id": self.snapshot_id,
            "generator": self.generator,
        }


def validate_version(version):
    if not re.fullmatch(r"[1-9][0-9]*\.[0-9]+\.[0-9]+", version.policy_version):
        raise ValueError("Invalid policy version")
    timestamp(version.evaluated_at)
    supported = {
        "v1": ("1.0.0", "northstar-synthetic-v1"),
        "policy-v2": ("2.0.0", "northstar-policy-rollout-v1"),
    }
    if supported.get(version.profile) != (version.policy_version, version.generator):
        raise ValueError("Version/profile/generator must be explicitly supported")
    if version.profile not in {"v1", "policy-v2"}:
        raise ValueError("Unsupported profile; register future contracts explicitly")
    if version.snapshot_id is not None and not re.fullmatch(r"[a-f0-9]{64}", version.snapshot_id):
        raise ValueError("Invalid snapshot digest")


class FileSnapshot:
    def __init__(self, path, expected):
        self.path, self.expected = Path(path), expected

    def read_snapshot(self):
        from backend.deployment.snapshot import from_document

        snapshot = from_document(json.loads(self.path.read_text()))
        if digest(snapshot) != self.expected:
            raise ValueError("Local immutable snapshot digest mismatch")
        return snapshot


class LocalCatalog:
    """Explicit local CLI only; refresh a validated index without restarting the API."""

    def __init__(self, path):
        self.path = Path(path).resolve()

    def view(self):
        data = json.loads(self.path.read_text())
        if data.get("format_version") != "1.0.0" or data.get("simulated") is not True:
            raise ValueError("Invalid local version catalogue")
        entries = {}
        for item in data["versions"]:
            file = (self.path.parent / item["file"]).resolve()
            if not file.is_relative_to(self.path.parent) or file.suffix != ".json":
                raise ValueError("Snapshot path outside catalogue")
            version = Version(
                item["policy_version"],
                item["profile"],
                item["evaluated_at"],
                FileSnapshot(file, item["snapshot_id"]),
                item["snapshot_id"],
                item["generator"],
            )
            validate_version(version)
            if version.policy_version in entries:
                raise ValueError("Duplicate policy version")
            entries[version.policy_version] = version
        if "1.0.0" not in entries:
            raise ValueError("V1 must remain available")
        current = data.get("current_policy_version", "1.0.0")
        run = data.get("current_run")
        if current not in entries or (
            run is not None
            and (not isinstance(run, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,100}", run))
        ):
            raise ValueError("Current governance marker must reference a registered snapshot")
        return entries, current, run

    def entries(self):
        return self.view()[0]


class ConfiguredCatalog:
    def __init__(self, entries, current_policy_version="1.0.0", current_run=None):
        if current_policy_version not in entries:
            raise ValueError("Current policy must be registered")
        if current_run is not None and (
            not isinstance(current_run, str)
            or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,100}", current_run)
        ):
            raise ValueError("Invalid current run reference")
        self._entries = entries
        self.current_policy_version = current_policy_version
        self.current_run = current_run

    def entries(self):
        return dict(self._entries)

    def view(self):
        return self.entries(), self.current_policy_version, self.current_run


def deployment_catalog(config, baseline):
    """Optional server-only allowlist; absent configuration preserves the original V1 path."""
    if not config.get("GOVERNANCE_VERSIONS_JSON"):
        if config.get("CURRENT_POLICY_VERSION", "1.0.0") != "1.0.0":
            raise ValueError("A non-baseline current policy requires an explicit allowlist")
        return None
    from backend.deployment.dynamodb import DynamoSnapshotRepository

    data = json.loads(config["GOVERNANCE_VERSIONS_JSON"])
    if not isinstance(data, list) or len(data) > 8:
        raise ValueError("Invalid version allowlist")
    entries = {"1.0.0": Version("1.0.0", "v1", DEMO_AT, baseline, config["SNAPSHOT_ID"])}
    for item in data:
        if set(item) != {"policy_version", "profile", "evaluated_at", "snapshot_id", "generator"}:
            raise ValueError("Unexpected version configuration")
        version = Version(
            repository=DynamoSnapshotRepository(config["GOVERNANCE_TABLE"], item["snapshot_id"]),
            **item,
        )
        validate_version(version)
        if version.policy_version in entries:
            raise ValueError("Cannot replace an existing version, including V1")
        entries[version.policy_version] = version
    return ConfiguredCatalog(
        entries, config.get("CURRENT_POLICY_VERSION", "1.0.0"), config.get("CURRENT_GOVERNANCE_RUN")
    )
