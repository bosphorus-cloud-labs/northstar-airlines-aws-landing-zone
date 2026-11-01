#!/bin/sh
# Local-only rehearsal; no AWS commands, credentials, deployment or publication.
set -eu
DEMO_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$DEMO_ROOT"
if [ ! -x .venv/bin/python ]; then
  echo 'Create the Python 3.13 .venv and install requirements-dev.txt first.' >&2
  exit 1
fi
exec .venv/bin/python -m governance.simulation.launcher "$@"
