"""Versioned, read-only REST endpoints; data and governance logic live elsewhere."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request

from backend.api.models import (
    DEMO_AT,
    AccountDetail,
    AccountQuery,
    AccountView,
    Deployment,
    Drift,
    Envelope,
    EvaluationQuery,
    ExceptionView,
    Finding,
    FindingQuery,
    Health,
    HealthQuery,
    Metadata,
    Page,
    PageQuery,
    RecordQuery,
    Summary,
    SummaryQuery,
    VersionMetadata,
    VersionSummary,
)
from backend.api.resource_models import ResourceEnvelope
from backend.service import Evaluation

router = APIRouter(prefix="/api/v1")


def evaluation(request: Request, query: Annotated[EvaluationQuery, Query()]) -> Evaluation:
    return request.app.state.service.evaluate(query.evaluation_timestamp, query.policy_version)


def envelope(data, at: str, result=None) -> dict:
    metadata = Metadata(evaluated_at=at)
    if result is not None and result.version is not None:
        descriptor = result.version.descriptor()
        descriptor["evaluated_at"] = at
        metadata = VersionMetadata(
            **descriptor,
            evidence_timestamps={
                e["id"]: e["observed_at"] for e in result.snapshot.fleet["evidence"]
            },
        )
    return {"metadata": metadata, "data": data}


def page(rows: list[dict], query: PageQuery, result: Evaluation) -> dict:
    end = query.offset + query.limit
    return {
        **envelope(rows[query.offset : end], result.at, result),
        "pagination": {
            "total": len(rows),
            "limit": query.limit,
            "offset": query.offset,
            "next_offset": end if end < len(rows) else None,
        },
    }


@router.get("/health", response_model=Envelope[Health])
def health(request: Request, query: Annotated[HealthQuery, Query()]):
    return envelope(
        {"status": "ok", "authentication_mode": request.app.state.authentication_mode}, DEMO_AT
    )


@router.get("/summary", response_model=Envelope[Summary | VersionSummary] | ResourceEnvelope)
def summary(request: Request, query: Annotated[SummaryQuery, Query()]):
    if query.view == "resources":
        if query.at is not None or query.policy_version is not None or query.catalog:
            raise HTTPException(status_code=422, detail="Resource data follows approved Current")
        try:
            return ResourceEnvelope.model_validate(request.app.state.resources.read())
        except Exception as exc:
            raise HTTPException(
                status_code=503, detail="Approved resource data is unavailable"
            ) from exc
    service = request.app.state.service
    result = service.evaluate(query.evaluation_timestamp, query.policy_version)
    data = result.summary()
    if query.catalog or result.version is not None or result.snapshot.context is not None:
        entries, current_policy, current_run = result.catalog_view or service.catalogue()
        data.update(
            current=entries[current_policy].descriptor(),
            current_run=current_run,
            versions=[v.descriptor() for v in entries.values()],
            journal=(result.snapshot.context or {}).get("journal", []),
            environment_requirements={
                e["id"]: e["requirements"] for e in result.snapshot.environments
            },
        )
    return envelope(data, result.at, result)


@router.get("/accounts", response_model=Page[AccountView])
def accounts(request: Request, query: Annotated[AccountQuery, Query()]):
    result = request.app.state.service.evaluate(query.evaluation_timestamp, query.policy_version)
    rows = [
        r
        for r in result.inventory()
        if (query.environment is None or r["account"]["environment"] == query.environment)
        and (
            query.lifecycle_status is None
            or r["account"]["lifecycle_status"] == query.lifecycle_status
        )
        and (
            query.compliance_status is None or r["compliance"]["status"] == query.compliance_status
        )
    ]
    return page(rows, query, result)


@router.get("/accounts/{account_id}", response_model=Envelope[AccountDetail])
def account_detail(
    account_id: Annotated[str, Path(pattern=r"^sim-account-[0-9]{3}$")],
    result: Annotated[Evaluation, Depends(evaluation)],
):
    return envelope(result.account_detail(account_id), result.at, result)


@router.get("/findings", response_model=Page[Finding])
def findings(request: Request, query: Annotated[FindingQuery, Query()]):
    result = request.app.state.service.evaluate(query.evaluation_timestamp, query.policy_version)
    rows = result.filter_records(
        result.findings, account_id=query.account_id, environment=query.environment
    )
    rows = [
        r
        for r in rows
        if (query.control_id is None or r["control_id"] == query.control_id)
        and (query.status is None or r["status"] == query.status)
    ]
    return page(rows, query, result)


@router.get("/deployments", response_model=Page[Deployment])
def deployments(request: Request, query: Annotated[RecordQuery, Query()]):
    return record_page(request, query, "deployments")


@router.get("/drift", response_model=Page[Drift])
def drift(request: Request, query: Annotated[RecordQuery, Query()]):
    return record_page(request, query, "drift")


@router.get("/exceptions", response_model=Page[ExceptionView])
def exceptions(request: Request, query: Annotated[RecordQuery, Query()]):
    return record_page(request, query, "exceptions")


def record_page(request: Request, query: RecordQuery, collection: str) -> dict:
    result = request.app.state.service.evaluate(query.evaluation_timestamp, query.policy_version)
    return page(
        result.filter_records(
            result.records(collection), account_id=query.account_id, environment=query.environment
        ),
        query,
        result,
    )
