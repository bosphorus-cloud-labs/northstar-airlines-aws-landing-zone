"""Fail-closed authorization boundary; no JWT implementation or AWS calls."""

import re
from dataclasses import dataclass
from ipaddress import ip_address
from typing import Protocol

from fastapi import HTTPException, Request


@dataclass(frozen=True)
class Principal:
    subject: str
    permissions: frozenset[str]


class Authenticator(Protocol):
    def authenticate(self, request: Request) -> Principal:
        """Future Cognito implementation must verify JWT signature, issuer, audience,
        expiry and allowed algorithms before mapping verified claims to permissions.
        Never trust forwarded identity headers or unverified claims.
        """
        ...


class DenyAuthenticator:
    def authenticate(self, request: Request) -> Principal:
        raise HTTPException(status_code=401, detail="Authentication is not configured")


class LocalDemoAuthenticator:
    """Explicit loopback-only identity bypass, not production authentication."""

    def authenticate(self, request: Request) -> Principal:
        if request.headers.get("authorization") is not None:
            raise HTTPException(
                status_code=401, detail="Tokens are not accepted in local-demo mode"
            )
        try:
            local = request.client is not None and ip_address(request.client.host).is_loopback
        except ValueError:
            local = False
        if not local:
            raise HTTPException(
                status_code=403, detail="Local-demo mode requires a loopback client"
            )
        hosts = request.headers.getlist("host")
        if len(hosts) != 1 or not re.fullmatch(
            r"(?:localhost|127\.0\.0\.1|\[::1\])(?::[0-9]{1,5})?", hosts[0], re.IGNORECASE
        ):
            raise HTTPException(status_code=403, detail="Local-demo host is not allowed")
        return Principal("local-demo-reader", frozenset({"governance:read"}))


def authorize_read(request: Request) -> Principal:
    principal = request.app.state.authenticator.authenticate(request)
    if "governance:read" not in principal.permissions:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return principal
