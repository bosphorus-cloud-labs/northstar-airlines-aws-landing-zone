"""Loopback-only development server; demo identity bypass requires explicit opt-in."""

import argparse

import uvicorn

from backend.app import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--local-demo",
        action="store_true",
        help="Enable loopback-only demo reader; never production authentication",
    )
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--demo-catalog", help="Explicit local immutable snapshot catalogue")
    args = parser.parse_args()
    if args.demo_catalog and not args.local_demo:
        parser.error("--demo-catalog requires explicit loopback --local-demo mode")
    from backend.versions import LocalCatalog

    uvicorn.run(
        create_app(
            local_demo=args.local_demo,
            catalog=LocalCatalog(args.demo_catalog) if args.demo_catalog else None,
        ),
        host="127.0.0.1",
        port=args.port,
        proxy_headers=False,
        server_header=False,
        access_log=False,
    )


if __name__ == "__main__":
    main()
