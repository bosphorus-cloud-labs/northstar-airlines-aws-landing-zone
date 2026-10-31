"""Application factory. All HTTP surfaces, including health and docs, are protected."""

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.api.models import ErrorResponse
from backend.api.routes import router
from backend.auth import Authenticator, DenyAuthenticator, LocalDemoAuthenticator, authorize_read
from backend.repository import FixtureRepository, GovernanceRepository
from backend.service import AccountNotFound, GovernanceService, InvalidEvaluationTime


def error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message}},
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


def create_app(
    *,
    local_demo: bool = False,
    repository: GovernanceRepository | None = None,
    authenticator: Authenticator | None = None,
) -> FastAPI:
    if local_demo and authenticator is not None:
        raise ValueError("Choose local-demo mode or an external authenticator")
    app = FastAPI(
        title="NorthStar Governance API",
        version="1.0.0",
        debug=False,
        docs_url="/docs",
        redoc_url=None,
        responses={code: {"model": ErrorResponse} for code in [400, 401, 403, 404, 422, 500]},
    )
    app.state.authenticator = (
        authenticator
        if authenticator is not None
        else LocalDemoAuthenticator()
        if local_demo
        else DenyAuthenticator()
    )
    app.state.authentication_mode = (
        "local-demo" if local_demo else "external" if authenticator is not None else "disabled"
    )
    app.state.service = GovernanceService(
        repository if repository is not None else FixtureRepository()
    )

    @app.middleware("http")
    async def security_boundary(request: Request, call_next):
        try:
            authorize_read(request)
            if any(len(request.query_params.getlist(key)) > 1 for key in request.query_params):
                return error(422, "invalid_request", "Duplicate query parameters are not allowed")
            response = await call_next(request)
        except HTTPException as exc:
            return error(
                exc.status_code,
                "unauthorized" if exc.status_code == 401 else "forbidden",
                "Authentication required" if exc.status_code == 401 else "Access denied",
            )
        except Exception:
            # Never serialize exceptions, validation input, filesystem paths or stack traces.
            return error(500, "internal_error", "An internal error occurred")
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        return error(422, "invalid_request", "Request parameters are invalid")

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        messages = {404: "Resource not found", 405: "Method not allowed"}
        return error(
            exc.status_code, "http_error", messages.get(exc.status_code, "Request rejected")
        )

    @app.exception_handler(AccountNotFound)
    async def unknown_account(request: Request, exc: AccountNotFound):
        return error(404, "account_not_found", "Account not found")

    @app.exception_handler(InvalidEvaluationTime)
    async def invalid_time(request: Request, exc: InvalidEvaluationTime):
        return error(422, "invalid_evaluation_time", "Evaluation predates the dataset")

    app.include_router(router)
    return app


# Importable ASGI entry point intentionally denies all requests by default.
app = create_app()
