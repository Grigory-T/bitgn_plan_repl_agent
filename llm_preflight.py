#!/usr/bin/env python3

from typing import Literal

from pydantic import BaseModel

from plan_agent.utils import llm_structured


class PreflightResult(BaseModel):
    status: Literal["ok"]


def main() -> int:
    result = llm_structured(
        'Return exactly one JSON object with one field: {"status":"ok"}.',
        PreflightResult,
    )
    print(f"LLM preflight: {result.status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
