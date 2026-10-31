"""Production composition: no environment flag can select local-demo authentication."""

import os

from backend.app import create_app
from backend.deployment.dynamodb import DynamoSnapshotRepository
from backend.deployment.identity import GatewayIdentity


def deployed_app(config=None):
    config = os.environ if config is None else config
    required = [
        "GOVERNANCE_TABLE",
        "SNAPSHOT_ID",
        "GATEWAY_API_ID",
        "GATEWAY_STAGE",
        "COGNITO_ISSUER",
        "COGNITO_CLIENT_ID",
    ]
    if not all(config.get(name) for name in required):
        # Missing deployment config must never fall back to local fixtures or demo identity.
        return create_app(local_demo=False)
    return create_app(
        local_demo=False,
        repository=DynamoSnapshotRepository(config["GOVERNANCE_TABLE"], config["SNAPSHOT_ID"]),
        authenticator=GatewayIdentity(
            config["GATEWAY_API_ID"],
            config["GATEWAY_STAGE"],
            config["COGNITO_ISSUER"],
            config["COGNITO_CLIENT_ID"],
        ),
    )
