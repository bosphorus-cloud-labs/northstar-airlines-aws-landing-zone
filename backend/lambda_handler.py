"""Deployment ASGI composition: verified gateway permissions; no local-demo bypass."""

import asyncio

from mangum import Mangum

from backend.deployment.application import deployed_app

# HTTP API's named stage can be present in requestContext.http.path. Strip only
# our fixed deployment prefix; GatewayIdentity still verifies the trusted stage.
_adapter = Mangum(deployed_app(), lifespan="off", api_gateway_base_path="/poc")


def handler(event, context):
    # Own the synchronous adapter's event loop explicitly on Python 3.13.
    with asyncio.Runner() as runner:
        runner.get_loop()
        return _adapter(event, context)
