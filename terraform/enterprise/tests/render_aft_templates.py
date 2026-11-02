#!/usr/bin/env python3
import argparse
import pathlib
import re


OSS_BLOCK = re.compile(
    r'{% if tf_distribution_type == "oss" -%}\n(?P<oss>.*?){% else -%}\n.*?{% endif %}',
    re.DOTALL,
)
PLACEHOLDER = re.compile(r"{{\s*([a-zA-Z0-9_]+)\s*}}")


def render(text: str, values: dict[str, str]) -> str:
    match = OSS_BLOCK.search(text)
    if match:
        text = match.group("oss")

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in values:
            raise ValueError(f"missing template value: {key}")
        return values[key]

    rendered = PLACEHOLDER.sub(replace, text)
    if "{{" in rendered or "{%" in rendered:
        raise ValueError("unresolved Jinja syntax remains")
    return rendered


def render_directory(source: pathlib.Path, output: pathlib.Path) -> None:
    values = {
        "aft_admin_role_arn": "arn:aws:iam::111111111111:role/AWSAFTAdmin",
        "bucket": "northstar-aft-state-example",
        "dynamodb_table": "northstar-aft-lock-example",
        "key": "customizations/example.tfstate",
        "kms_key_id": "arn:aws:kms:eu-central-1:111111111111:key/00000000-0000-0000-0000-000000000000",
        "provider_region": "eu-central-1",
        "region": "eu-central-1",
        "target_admin_role_arn": "arn:aws:iam::222222222222:role/AWSAFTAdmin",
        "tf_version": "1.14.6",
    }
    output.mkdir(parents=True, exist_ok=True)
    for template in source.glob("*.jinja"):
        target = output / template.name.removesuffix(".jinja").replace("aft-providers", "providers")
        target.write_text(render(template.read_text(), values))


def main() -> None:
    parser = argparse.ArgumentParser(description="Render the OSS branch of an AFT Terraform template directory.")
    parser.add_argument("source", type=pathlib.Path)
    parser.add_argument("output", type=pathlib.Path)
    args = parser.parse_args()
    render_directory(args.source, args.output)


if __name__ == "__main__":
    main()
