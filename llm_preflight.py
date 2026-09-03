#!/usr/bin/env python3

import argparse
import sys

from pydantic import BaseModel

from plan_agent.config import default_config_path, load_runtime_config


class PreflightResult(BaseModel):
    status: str


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Test the configured LLM endpoint.")
    parser.add_argument(
        "--config",
        default=str(default_config_path()),
        help="Plain-text LLM configuration file",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        load_runtime_config(args.config)
    except RuntimeError as exc:
        print(f"CONFIG ERROR: {exc}", file=sys.stderr)
        return 2

    from plan_agent.utils import llm_structured

    result = llm_structured(
        'Return exactly one JSON object with one field: {"status":"ok"}.',
        PreflightResult,
    )
    if result.status != "ok":
        raise RuntimeError(f"Unexpected preflight status: {result.status!r}")
    print(f"LLM preflight: {result.status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
