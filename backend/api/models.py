"""Pydantic transport models backed by the existing Phase 1 record contracts."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, ClassVar, Literal, Self

from jsonschema import FormatChecker
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from governance.model.contracts import validate

DEMO_AT = "2026-10-31T12:00:00Z"
AccountId = Annotated[str, Field(pattern=r"^sim-account-[0-9]{3}$")]


class Environment(StrEnum):
    production = "production"
    pre_production = "pre-production"
    testing = "testing"
    development = "development"


class Status(StrEnum):
    compliant = "compliant"
    noncompliant = "noncompliant"
    unknown = "unknown"
    stale = "stale"


class Control(StrEnum):
    approval = "deployment-approval"
    encryption = "baseline-encryption"
    public_access = "public-access"
    logging = "logging"
    monitoring = "security-monitoring"
    integrity = "audit-log-integrity"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HealthQuery(StrictModel):
    """Health accepts no query parameters."""


class EvaluationQuery(StrictModel):
    at: AwareDatetime | None = None
    policy_version: str | None = Field(
        default=None, pattern=r"^[1-9][0-9]*\.[0-9]+\.[0-9]+$", max_length=32
    )

    @field_validator("at", mode="before")
    @classmethod
    def validate_timestamp(cls, value):
        if (
            isinstance(value, str)
            and len(value) <= 64
            and FormatChecker().conforms(value, "date-time")
        ):
            return value
        if isinstance(value, datetime) and value.tzinfo is not None:
            return value
        raise ValueError("Use a timezone-aware RFC 3339 timestamp")

    @field_validator("at")
    @classmethod
    def normalize_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        try:
            return value.astimezone(UTC)
        except (OverflowError, ValueError) as exc:
            raise ValueError("Timestamp is outside the supported UTC range") from exc

    @property
    def evaluation_timestamp(self) -> str | None:
        if self.at is None:
            return None
        return self.at.astimezone(UTC).isoformat().replace("+00:00", "Z")


class SummaryQuery(EvaluationQuery):
    catalog: bool = False


class PageQuery(EvaluationQuery):
    limit: int = Field(default=25, ge=1, le=100)
    offset: int = Field(default=0, ge=0, le=1_000_000)


class AccountQuery(PageQuery):
    environment: Environment | None = None
    lifecycle_status: Literal["active", "onboarding", "suspended"] | None = None
    compliance_status: Status | None = None


class FindingQuery(PageQuery):
    account_id: AccountId | None = None
    environment: Environment | None = None
    control_id: Control | None = None
    status: Status | None = None


class RecordQuery(PageQuery):
    account_id: AccountId | None = None
    environment: Environment | None = None


class Metadata(StrictModel):
    api_version: Literal["v1"] = "v1"
    source: Literal["northstar-synthetic-v1"] = "northstar-synthetic-v1"
    simulated: Literal[True] = True
    evaluated_at: str


class VersionDescriptor(StrictModel):
    policy_version: str
    profile: str
    evaluated_at: str
    snapshot_id: str | None
    generator: str


class VersionMetadata(Metadata, VersionDescriptor):
    evidence_timestamps: dict[str, str]


class Envelope[T](StrictModel):
    metadata: Metadata | VersionMetadata
    data: T


class PageInfo(StrictModel):
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
    next_offset: int | None = None


class Page[T](Envelope[list[T]]):
    pagination: PageInfo


class Record(StrictModel):
    contract: ClassVar[str]
    schema_version: Literal["1.0.0"]
    source: Literal["northstar-synthetic-v1"]
    simulated: Literal[True]
    id: str

    @model_validator(mode="after")
    def validate_phase_one(self) -> Self:
        value = self.model_dump()
        profile = (
            "policy-v2"
            if value.get("control_id") == "audit-log-integrity"
            or value.get("policy_version") == "2.0.0"
            else "v1"
        )
        validate(self.contract, value, profile=profile)
        return self


class Account(Record):
    contract = "account"
    id: AccountId
    name: str
    environment: Environment
    ou_id: str
    lifecycle_status: Literal["active", "onboarding", "suspended"]
    desired_policy_version: str
    created_at: str


class ExceptionState(StrictModel):
    id: str
    state: Literal["active", "expired", "not-yet-active", "pending", "rejected"]


class Counts(StrictModel):
    compliant: int = Field(default=0, ge=0)
    noncompliant: int = Field(default=0, ge=0)
    unknown: int = Field(default=0, ge=0)
    stale: int = Field(default=0, ge=0)


class Compliance(StrictModel):
    status: Status
    controls: Counts
    exceptions: list[ExceptionState]


class AccountView(StrictModel):
    account: Account
    compliance: Compliance


class OrganizationalUnit(StrictModel):
    schema_version: Literal["1.0.0"]
    id: str
    parent_id: str | None
    environment: Literal["root", "production", "pre-production", "testing", "development"]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        validate("ou", self.model_dump())
        return self


class AccountDetail(AccountView):
    ou: OrganizationalUnit
    findings: list["Finding"]


class Finding(Record):
    contract = "finding"
    account_id: AccountId
    control_id: Control
    evaluated_at: str
    policy_version: str
    desired_value: bool
    observed_value: bool | None
    evidence_id: str | None
    status: Status
    reason: Literal[
        "match",
        "mismatch",
        "missing-evidence",
        "future-evidence",
        "stale-evidence",
        "revision-mismatch",
    ]
    exceptions: list[ExceptionState]


class Deployment(Record):
    contract = "deployment"
    account_id: AccountId
    tool: Literal["terraform", "aft"]
    desired_revision: str
    observed_revision: str | None
    status: Literal["succeeded", "failed", "pending"]
    started_at: str
    completed_at: str | None
    correlation_id: str
    failure_reason: str | None


class Drift(Record):
    contract = "drift"
    account_id: AccountId
    control_id: Control
    desired_value: bool
    observed_value: bool | None
    desired_revision: str
    observed_revision: str | None
    observed_at: str
    status: Literal["in-sync", "drifted", "unknown"]


class AuditEntry(StrictModel):
    at: str
    action: str
    actor: str


class GovernanceException(Record):
    contract = "exception"
    account_id: AccountId
    control_id: Control
    status: Literal["approved", "pending", "rejected"]
    rationale: str
    owner: str
    approver: str | None
    approval_reference: str | None
    approved_at: str | None
    created_at: str
    expires_at: str
    audit: list[AuditEntry]


class ExceptionView(StrictModel):
    exception: GovernanceException
    expiration_state: ExceptionState


class Summary(StrictModel):
    account_count: int = Field(ge=0)
    finding_count: int = Field(ge=0)
    account_counts: Counts
    finding_counts: Counts
    environment_counts: dict[Environment, int]


class RolloutEvent(StrictModel):
    sequence: int
    at: str
    action: str
    detail: str
    account_id: str | None
    actor: str
    source: str
    simulated: Literal[True]


class EnvironmentRequirement(StrictModel):
    control_id: Control
    expected: bool
    max_age_hours: int = Field(ge=1)


class VersionSummary(Summary):
    current: VersionDescriptor
    current_run: str | None
    versions: list[VersionDescriptor]
    journal: list[RolloutEvent]
    environment_requirements: dict[Environment, list[EnvironmentRequirement]]


class Health(StrictModel):
    status: Literal["ok"] = "ok"
    authentication_mode: Literal["disabled", "local-demo", "external"]


class ErrorDetail(StrictModel):
    code: str
    message: str


class ErrorResponse(StrictModel):
    error: ErrorDetail
