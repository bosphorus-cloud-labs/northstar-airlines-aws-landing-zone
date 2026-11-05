"""Frozen unit-test scenarios, independent from editable operator observations."""

import json
from pathlib import Path

from compliance_engine.resources import load as load_current
from compliance_engine.resources import validate


def load(directory=None):
    if directory is not None:
        return load_current(directory)
    return validate(
        json.loads((Path(__file__).parent / "fixtures/resource-compliance.json").read_text())
    )
