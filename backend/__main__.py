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
    args = parser.parse_args()
    uvicorn.run(
        create_app(local_demo=args.local_demo),
        host="127.0.0.1",
        port=args.port,
        proxy_headers=False,
        server_header=False,
        access_log=False,
    )


if __name__ == "__main__":
    main()
