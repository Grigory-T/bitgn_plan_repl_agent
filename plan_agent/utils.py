import os
import json
import ast
from typing import Literal, List
from openai import OpenAI
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

LLM_REQUEST_TIMEOUT_SECONDS = 300

LLM_MODEL_PLAN = "openai/gpt-4.1"
LLM_MODEL_DECISION = "openai/gpt-4.1"
LLM_MODEL_REPLAN = "openai/gpt-4.1"
LLM_MODEL_RESPONSE = "openai/gpt-4.1"

LLM_MODEL_AGENT = "openai/gpt-oss-120b:nitro"

# minimax/minimax-m2.7
# openai/gpt-oss-120b:nitro
# google/gemini-3-flash-preview
# "openai/gpt-4.1"
# "moonshotai/kimi-k2-thinking"
# z-ai/glm-4.6
# "deepseek/deepseek-v3.2"
# deepseek/deepseek-v3.2-speciale
# "qwen/qwen3-32b"
# "google/gemini-3-flash-preview"
# minimax/minimax-m2.5


# :nitro

def llm_structured(prompt: str, response_model: type[BaseModel], model: str | None = None) -> BaseModel:
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.getenv("OPENROUTER_API_KEY"))
    schema = response_model.model_json_schema()
    req = json.dumps(schema, ensure_ascii=False)
    full = f"{prompt}\n\nReturn only JSON matching this: {req}"
    try:
        resp = client.chat.completions.create(
            model=model or LLM_MODEL_PLAN,
            messages=[{"role": "user", "content": full}],
            temperature=0,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "response_schema",
                    "strict": False,
                    "schema": schema
                }
            },
            max_tokens=5_000,
            timeout=LLM_REQUEST_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        raise RuntimeError(f"Structured LLM request failed: {exc}") from exc
    content = resp.choices[0].message.content
    return response_model.model_validate_json(content)



def llm(messages: list, model: str | None = None) -> tuple[str, str]:
    provider = (os.getenv("LLM_AGENT_PROVIDER") or "openrouter").strip().lower()
    chosen_model = model or LLM_MODEL_AGENT

    if provider == "cerebras":
        from cerebras.cloud.sdk import Cerebras

        if chosen_model == LLM_MODEL_AGENT:
            chosen_model = os.getenv("LLM_MODEL_AGENT_CEREBRAS", "qwen-3-235b-a22b-instruct-2507")

        client = Cerebras(api_key=os.getenv("CEREBRAS_API_KEY"))
        try:
            resp = client.chat.completions.create(
                model=chosen_model,
                messages=messages,
                temperature=0,
                max_tokens=10_000,
                timeout=LLM_REQUEST_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            raise RuntimeError(f"Cerebras LLM request failed: {exc}") from exc
        message = resp.choices[0].message
        content = message.content or ""
        reasoning = ""
        raw_reasoning = getattr(message, "reasoning", None)
        if isinstance(raw_reasoning, str) and raw_reasoning.strip():
            reasoning = raw_reasoning.strip()
    else:
        client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.getenv("OPENROUTER_API_KEY"))
        try:
            resp = client.chat.completions.create(
                model=chosen_model,
                messages=messages,
                # temperature=0,
                max_tokens=15_000,
                extra_body={
                    "reasoning": {
                        "effort": "xhigh",  #  "minimal", "low", "medium", "high", "xhigh"
                        "provider": {
                            "ignore": ["Parasail"],
                            "sort": "throughput",  # latency
                        },
                    },
                },
                timeout=LLM_REQUEST_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            raise RuntimeError(f"OpenRouter LLM request failed: {exc}") from exc
        message = resp.choices[0].message
        content = message.content or ""

        reasoning = ''
        reasoning_details = getattr(message, 'reasoning_details', None)
        if reasoning_details:
            reasoning_parts = []
            for detail in reasoning_details:
                if detail.get('type') == 'reasoning.text':
                    reasoning_parts.append(detail.get('text', ''))
                elif detail.get('type') == 'reasoning.summary':
                    reasoning_parts.append(detail.get('summary', ''))
            reasoning = '\n\n'.join(reasoning_parts)

    class ResponseBlock(BaseModel):
        block_id: int
        block_type: Literal["python", "bash", "text"]
        block_text: str

    blocks: list[ResponseBlock] = []

    # Parse content into ordered blocks using strict XML-like tags.
    idx = 0
    block_idx = 0
    open_tag = "<python>"
    close_tag = "</python>"
    while True:
        start = content.find(open_tag, idx)
        if start == -1:
            tail = content[idx:]
            if tail:
                blocks.append(ResponseBlock(block_id=block_idx, block_type="text", block_text=tail))
                block_idx += 1
            break

        if start > idx:
            text_part = content[idx:start]
            blocks.append(ResponseBlock(block_id=block_idx, block_type="text", block_text=text_part))
            block_idx += 1

        code_start = start + len(open_tag)
        close = content.find(close_tag, code_start)
        if close == -1:
            code_part = content[code_start:]
            idx = len(content)
        else:
            code_part = content[code_start:close]
            idx = close + len(close_tag)

        blocks.append(ResponseBlock(block_id=block_idx, block_type="python", block_text=code_part))
        block_idx += 1

    return content, blocks, reasoning.strip()


def check_assigned_variables(code: str) -> bool:
    """Check if final_answer or step_status is assigned in the code string."""
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in ("final_answer", "step_status"):
                        return True
                    if isinstance(target, (ast.Tuple, ast.List)):
                        for elt in target.elts:
                            if isinstance(elt, ast.Name) and elt.id in ("final_answer", "step_status"):
                                return True
        return False
    except Exception:
        return False


def format_step_variables(variables: List) -> str:
    """Format list of StepVariable objects into readable string."""
    if not variables:
        return "None"
    
    lines = []
    for var in variables:
        lines.append(f"  - {var.variable_name} ({var.variable_data_type}): {var.variable_description}")
    
    return "\n" + "\n".join(lines)
