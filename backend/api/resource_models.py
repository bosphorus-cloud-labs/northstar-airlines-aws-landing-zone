"""Transport contracts for the current resource-compliance dataset."""

from typing import Literal

from pydantic import Field

from backend.api.models import StrictModel
from compliance_engine.resources import Account, Resource, Rule, Status


class ResourceFinding(StrictModel):
    id: str
    resource_id: str
    account_id: str
    environment: str
    control_id: str
    control: str
    expected: str | bool
    observed: str | bool | None
    observed_at: str
    evaluated_at: str
    status: Status
    reason: str
    source: Literal["northstar-synthetic-resources"]
    simulated: Literal[True]


class ResourceView(Resource):
    status: Status
    finding: ResourceFinding


class ResourceAccountView(Account):
    resource_count: int = Field(ge=0)
    status: Status


class ResourceCounts(StrictModel):
    accounts: int
    resources: int
    controls: int
    compliant: int
    noncompliant: int
    unknown: int
    stale: int


class Change(StrictModel):
    resource_id: str
    resource_name: str
    control: str
    before: Status | None
    after: Status | None
    old_value: str | bool | None
    new_value: str | bool | None
    reason: str


class Activity(StrictModel):
    operation: str
    generation: int
    source_commit: str
    actor: str
    published_at: str
    previous: str | None
    target: str
    changes: list[Change]


class ResourceRequirement(StrictModel):
    expected_json: str
    max_age_hours: int = Field(ge=1, le=168)


class ResourceAssignment(StrictModel):
    account_id: str
    environment: str
    approval_required: bool
    requirements: dict[str, ResourceRequirement]


class ResourceTerraformReceipt(StrictModel):
    source: Literal["northstar-terraform-resource-desired-v1"]
    simulated: Literal[True]
    input_digest: str
    accounts: dict[str, ResourceAssignment]
    terraform_version: Literal["1.14.6"]


class ResourceData(StrictModel):
    accounts: list[ResourceAccountView]
    resources: list[ResourceView]
    findings: list[ResourceFinding]
    controls: list[Rule]
    summary: ResourceCounts
    evaluated_at: str
    activity: list[Activity]
    terraform_validation: ResourceTerraformReceipt | None


class ResourceMetadata(StrictModel):
    api_version: Literal["v1"]
    source: Literal["northstar-synthetic-resources"]
    simulated: Literal[True]
    evaluated_at: str
    published_at: str | None
    source_commit: str | None
    workflow_run: str | None


class ResourceEnvelope(StrictModel):
    metadata: ResourceMetadata
    data: ResourceData
