"""Versioned, read-only REST endpoints; data and governance logic live elsewhere."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request

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
)
from backend.service import Evaluation

router = APIRouter(prefix="/api/v1")


def evaluation(request: Request, query: Annotated[EvaluationQuery, Query()]) -> Evaluation:
    return request.app.state.service.evaluate(query.evaluation_timestamp)


def envelope(data, at: str) -> dict:
    return {"metadata": Metadata(evaluated_at=at), "data": data}


def page(rows: list[dict], query: PageQuery) -> dict:
    end = query.offset + query.limit
    return {
        **envelope(rows[query.offset : end], query.evaluation_timestamp),
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


@router.get("/summary", response_model=Envelope[Summary])
def summary(result: Annotated[Evaluation, Depends(evaluation)]):
    return envelope(result.summary(), result.at)


@router.get("/accounts", response_model=Page[AccountView])
def accounts(request: Request, query: Annotated[AccountQuery, Query()]):
    result = request.app.state.service.evaluate(query.evaluation_timestamp)
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
    return page(rows, query)


@router.get("/accounts/{account_id}", response_model=Envelope[AccountDetail])
def account_detail(
    account_id: Annotated[str, Path(pattern=r"^sim-account-[0-9]{3}$")],
    result: Annotated[Evaluation, Depends(evaluation)],
):
    return envelope(result.account_detail(account_id), result.at)


@router.get("/findings", response_model=Page[Finding])
def findings(request: Request, query: Annotated[FindingQuery, Query()]):
    result = request.app.state.service.evaluate(query.evaluation_timestamp)
    rows = result.filter_records(
        result.findings, account_id=query.account_id, environment=query.environment
    )
    rows = [
        r
        for r in rows
        if (query.control_id is None or r["control_id"] == query.control_id)
        and (query.status is None or r["status"] == query.status)
    ]
    return page(rows, query)


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
    result = request.app.state.service.evaluate(query.evaluation_timestamp)
    return page(
        result.filter_records(
            result.records(collection), account_id=query.account_id, environment=query.environment
        ),
        query,
    )
