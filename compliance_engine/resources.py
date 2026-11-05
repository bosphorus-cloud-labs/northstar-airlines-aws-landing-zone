"""Deterministic synthetic resource evaluation. No AWS access or wall-clock evaluation."""

import hashlib
import json
from datetime import timedelta
from pathlib import Path
from typing import Literal

from jsonschema import FormatChecker
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from compliance_engine.contracts import ROOT, timestamp

Environment = Literal["production", "pre-production", "testing", "development"]
Status = Literal["compliant", "noncompliant", "unknown", "stale"]
ENVIRONMENTS = {"production", "pre-production", "testing", "development"}
FIELDS = {
    "ec2-imdsv2": ("ec2_instance", ("metadata_options", "http_tokens"), "required"),
    "s3-public-access": ("s3_bucket", ("public_access_blocked",), True),
    "ebs-encryption": ("ebs_volume", ("encrypted",), True),
}


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Account(Strict):
    id: str = Field(pattern=r"^sim-account-[0-9]{3}$")
    name: str = Field(min_length=1, max_length=100)
    environment: Environment
    ou_id: str = Field(pattern=r"^sim-ou-[a-z-]+$")
    lifecycle_status: Literal["active", "onboarding", "suspended"] = "active"

    @model_validator(mode="after")
    def ou_assignment(self):
        if self.ou_id != "sim-ou-" + self.environment:
            raise ValueError("Account OU must match its environment")
        return self


class Accounts(Strict):
    simulated: Literal[True]
    accounts: list[Account] = Field(min_length=1, max_length=100)


class Resource(Strict):
    id: str = Field(pattern=r"^sim-(ec2|s3|ebs)-[a-z0-9-]{1,60}$")
    name: str = Field(min_length=1, max_length=100)
    account_id: str = Field(pattern=r"^sim-account-[0-9]{3}$")
    environment: Environment
    region: Literal["eu-central-1"]
    resource_type: Literal["ec2_instance", "s3_bucket", "ebs_volume"]
    source: Literal["northstar-synthetic-resources"]
    simulated: Literal[True]
    observed_at: str
    configuration: dict

    @field_validator("observed_at")
    @classmethod
    def explicit_time(cls, value):
        if len(value) > 64 or not FormatChecker().conforms(value, "date-time"):
            raise ValueError("Explicit RFC3339 evaluation/observation timestamp required")
        timestamp(value)
        return value

    @model_validator(mode="after")
    def configuration_contract(self):
        config = self.configuration
        if self.resource_type == "ec2_instance":
            if set(config) != {"metadata_options"} or not isinstance(
                config["metadata_options"], dict
            ):
                raise ValueError("Use the explicit EC2 metadata options")
            options = config["metadata_options"]
            if (
                set(options) != {"http_endpoint", "http_tokens"}
                or options["http_endpoint"] != "enabled"
                or options["http_tokens"] not in ("required", "optional", None)
            ):
                raise ValueError("Unsupported synthetic metadata configuration")
        else:
            key = "public_access_blocked" if self.resource_type == "s3_bucket" else "encrypted"
            if set(config) != {key} or (config[key] is not None and type(config[key]) is not bool):
                raise ValueError(
                    "Use a boolean configuration observation or null for missing evidence"
                )
        return self


class Inventory(Strict):
    format: Literal["resource-compliance/1"]
    simulated: Literal[True]
    evaluated_at: str
    resources: list[Resource] = Field(min_length=1, max_length=200)

    @field_validator("evaluated_at")
    @classmethod
    def explicit_time(cls, value):
        if len(value) > 64 or not FormatChecker().conforms(value, "date-time"):
            raise ValueError("Explicit RFC3339 evaluation/observation timestamp required")
        timestamp(value)
        return value


class Rule(Strict):
    id: Literal["ec2-imdsv2", "s3-public-access", "ebs-encryption"]
    name: str = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=1, max_length=300)
    expected: str | bool
    max_age_hours: dict[Environment, int]

    @model_validator(mode="after")
    def baseline(self):
        expected = FIELDS[self.id][2]
        if type(self.expected) is not type(expected) or self.expected != expected:
            raise ValueError("Resource rules cannot weaken the security baseline")
        ceilings = {"production": 24, "pre-production": 48, "testing": 72, "development": 168}
        if set(self.max_age_hours) != ENVIRONMENTS or any(
            type(value) is not int or not 1 <= value <= ceilings[environment]
            for environment, value in self.max_age_hours.items()
        ):
            raise ValueError("Explicit bounded freshness is required in all four environments")
        return self


class Rules(Strict):
    simulated: Literal[True]
    rules: list[Rule] = Field(min_length=3, max_length=3)


class Document(Strict):
    accounts: Accounts
    inventory: Inventory
    controls: Rules
    terraform_validation: dict | None = None

    @model_validator(mode="after")
    def relationships(self):
        accounts = {a.id: a for a in self.accounts.accounts}
        if len(accounts) != len(self.accounts.accounts) or len(
            {r.id for r in self.inventory.resources}
        ) != len(self.inventory.resources):
            raise ValueError("Duplicate synthetic identity")
        if {r.id for r in self.controls.rules} != set(FIELDS):
            raise ValueError("Exactly the reviewed three resource controls are required")
        for resource in self.inventory.resources:
            if (
                resource.account_id not in accounts
                or accounts[resource.account_id].environment != resource.environment
            ):
                raise ValueError("Unresolved resource account/environment")
            if timestamp(resource.observed_at) > timestamp(self.inventory.evaluated_at):
                raise ValueError("Observation is after the explicit evaluation time")
        if len(canonical(self.model_dump()).encode()) > 200_000:
            raise ValueError("Synthetic dataset exceeds the POC read budget")
        if self.terraform_validation is not None:
            verify_receipt(self.model_dump())
        return self


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def validate(value):
    return Document.model_validate(value).model_dump()


def load(directory=ROOT):
    directory = Path(directory)
    return validate(
        {
            "accounts": json.loads((directory / "mock-aws-resources/accounts.json").read_text()),
            "inventory": json.loads((directory / "mock-aws-resources/resources.json").read_text()),
            "controls": json.loads(
                (directory / "compliance-rules/resource-controls.json").read_text()
            ),
        }
    )


def digest(value):
    return hashlib.sha256(canonical(validate(value)).encode()).hexdigest()


def overall(statuses):
    return next(
        (s for s in ("noncompliant", "stale", "unknown") if s in statuses),
        "compliant" if statuses else "unknown",
    )


def evaluate(value):
    value = validate(value)
    rules = {r["id"]: r for r in value["controls"]["rules"]}
    at = value["inventory"]["evaluated_at"]
    resources, findings = [], []
    for resource in sorted(value["inventory"]["resources"], key=lambda r: r["id"]):
        rule_id = next(key for key, spec in FIELDS.items() if spec[0] == resource["resource_type"])
        rule = rules[rule_id]
        observed = resource["configuration"]
        for part in FIELDS[rule_id][1]:
            observed = observed[part]
        status, reason = "compliant", "Configuration meets the control requirement."
        if observed is None:
            status, reason = "unknown", "Configuration evidence is missing."
        elif timestamp(at) - timestamp(resource["observed_at"]) > timedelta(
            hours=rule["max_age_hours"][resource["environment"]]
        ):
            status, reason = (
                "stale",
                "Configuration evidence is older than the environment freshness limit.",
            )
        elif observed != rule["expected"]:
            status, reason = "noncompliant", rule["reason"]
        finding = {
            "id": resource["id"] + ":" + rule_id,
            "resource_id": resource["id"],
            "account_id": resource["account_id"],
            "environment": resource["environment"],
            "control_id": rule_id,
            "control": rule["name"],
            "expected": rule["expected"],
            "observed": observed,
            "observed_at": resource["observed_at"],
            "evaluated_at": at,
            "status": status,
            "reason": reason,
            "source": resource["source"],
            "simulated": True,
        }
        findings.append(finding)
        resources.append({**resource, "status": status, "finding": finding})
    accounts = []
    for account in sorted(value["accounts"]["accounts"], key=lambda a: a["id"]):
        rows = [r for r in resources if r["account_id"] == account["id"]]
        accounts.append(
            {**account, "resource_count": len(rows), "status": overall([r["status"] for r in rows])}
        )
    counts = {
        s: sum(f["status"] == s for f in findings)
        for s in ("compliant", "noncompliant", "unknown", "stale")
    }
    return {
        "accounts": accounts,
        "resources": resources,
        "findings": findings,
        "controls": list(rules.values()),
        "summary": {
            "accounts": len(accounts),
            "resources": len(resources),
            "controls": len(rules),
            **counts,
        },
        "evaluated_at": at,
    }


def input_digest(value):
    inputs = {key: value[key] for key in ("accounts", "inventory", "controls")}
    return hashlib.sha256(canonical(inputs).encode()).hexdigest()


def resource_assignments(value):
    return {
        account["id"]: {
            "account_id": account["id"],
            "environment": account["environment"],
            "approval_required": account["environment"] in {"production", "pre-production"},
            "requirements": {
                rule["id"]: {
                    "expected_json": canonical(rule["expected"]),
                    "max_age_hours": rule["max_age_hours"][account["environment"]],
                }
                for rule in value["controls"]["rules"]
            },
        }
        for account in value["accounts"]["accounts"]
    }


def verify_receipt(value):
    receipt = value["terraform_validation"]
    if set(receipt) != {"source", "simulated", "input_digest", "accounts", "terraform_version"}:
        raise ValueError("Invalid Terraform receipt")
    if (
        receipt["source"] != "northstar-terraform-resource-desired-v1"
        or receipt["simulated"] is not True
        or receipt["input_digest"] != input_digest(value)
        or receipt["accounts"] != resource_assignments(value)
        or receipt["terraform_version"] != "1.14.6"
    ):
        raise ValueError("Terraform receipt does not match the exact resource inputs")
    return receipt
