"""Validate saved public Terraform outputs and write ignored Vite production settings; no cloud calls."""

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

KEYS = {
    "VITE_AUTH_MODE",
    "VITE_API_BASE_URL",
    "VITE_COGNITO_ISSUER",
    "VITE_COGNITO_CLIENT_ID",
    "VITE_COGNITO_DOMAIN",
    "VITE_APP_ORIGIN",
}


def render(settings: dict) -> str:
    if set(settings) != KEYS or settings["VITE_AUTH_MODE"] != "cognito":
        raise ValueError("Only the exact public Cognito frontend settings are accepted")
    for key, value in settings.items():
        if not isinstance(value, str) or any(c in value for c in '\n\r"\\'):
            raise ValueError("Invalid public configuration value")
        if key in {"VITE_AUTH_MODE", "VITE_COGNITO_CLIENT_ID"}:
            continue
        url = urlsplit(value)
        if (
            url.scheme != "https"
            or not url.hostname
            or url.username
            or url.password
            or url.query
            or url.fragment
        ):
            raise ValueError(
                "Public endpoints must be HTTPS URLs without credentials/query/fragment"
            )
    api = urlsplit(settings["VITE_API_BASE_URL"])
    issuer = urlsplit(settings["VITE_COGNITO_ISSUER"])
    domain = urlsplit(settings["VITE_COGNITO_DOMAIN"])
    origin = urlsplit(settings["VITE_APP_ORIGIN"])
    if (
        not re.fullmatch(r"[a-z0-9]+\.execute-api\.eu-central-1\.amazonaws\.com", api.hostname)
        or api.path != "/poc"
        or issuer.hostname != "cognito-idp.eu-central-1.amazonaws.com"
        or not re.fullmatch(r"/eu-central-1_[A-Za-z0-9]+", issuer.path)
        or not re.fullmatch(r"[a-z0-9-]+\.auth\.eu-central-1\.amazoncognito\.com", domain.hostname)
        or domain.path not in {"", "/"}
        or origin.path not in {"", "/"}
    ):
        raise ValueError("Settings must match the Frankfurt POC deployment contract")
    if not re.fullmatch(r"[A-Za-z0-9]{1,128}", settings["VITE_COGNITO_CLIENT_ID"]):
        raise ValueError("Invalid public app client identifier")
    return "# Public settings only; generated offline from saved Terraform output.\n" + "".join(
        f"{key}={json.dumps(settings[key])}\n" for key in sorted(KEYS)
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("frontend/.env.production.local"))
    args = parser.parse_args()
    text = render(json.loads(args.input.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text)
    print("Wrote public build settings; no credentials or cloud requests involved.")


if __name__ == "__main__":
    main()
