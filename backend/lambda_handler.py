"""ASGI compatibility only: no deployment and no local-demo Lambda bypass."""

import asyncio

from mangum import Mangum

from backend.app import create_app

_adapter = Mangum(create_app(local_demo=False), lifespan="off")


def handler(event, context):
    # Own the synchronous adapter's event loop explicitly on Python 3.13.
    with asyncio.Runner() as runner:
        runner.get_loop()
        return _adapter(event, context)
