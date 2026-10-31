"""Trust only API Gateway's JWT-authorizer context, never browser identity headers."""

import json
from dataclasses import dataclass

from fastapi import HTTPException, Request

from backend.auth import Principal


@dataclass(frozen=True)
class GatewayIdentity:
    api_id: str
    stage: str
    issuer: str
    client_id: str
    required_scope: str = "northstar-governance/read"
    required_group: str = "governance-readers"

    def authenticate(self, request: Request) -> Principal:
        event = request.scope.get("aws.event", {})
        context = event.get("requestContext", {})
        if (
            event.get("version") != "2.0"
            or context.get("apiId") != self.api_id
            or context.get("stage") != self.stage
            or not request.scope.get("aws.context")
        ):
            raise HTTPException(401, "Verified gateway context required")
        jwt = context.get("authorizer", {}).get("jwt", {})
        claims = jwt.get("claims", {})
        if (
            claims.get("iss") != self.issuer
            or claims.get("client_id") != self.client_id
            or claims.get("token_use") != "access"
            or not claims.get("sub")
        ):
            raise HTTPException(401, "Verified access-token identity required")
        # API Gateway verifies signature/expiry/audience; this layer checks permissions.
        scopes = claims.get("scope", "")
        if not isinstance(scopes, str) or self.required_scope not in scopes.split():
            raise HTTPException(403, "Read scope required")
        raw_groups = claims.get("cognito:groups", [])
        if isinstance(raw_groups, str):
            try:
                groups = json.loads(raw_groups)
            except ValueError:
                # HTTP API authorizer context can flatten arrays into a bracketed list.
                groups = [g.strip() for g in raw_groups.strip("[]").split(",")]
        else:
            groups = raw_groups
        if (
            not isinstance(groups, list)
            or not all(isinstance(g, str) for g in groups)
            or self.required_group not in groups
        ):
            raise HTTPException(403, "Reader group required")
        return Principal(str(claims["sub"]), frozenset({"governance:read"}))
