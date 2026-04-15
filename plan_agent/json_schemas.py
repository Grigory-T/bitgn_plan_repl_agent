import json
from copy import deepcopy


def _make_provider_strict(schema: dict) -> dict:
    strict_schema = deepcopy(schema)
    _strictify_node(strict_schema)
    return strict_schema


def _strictify_node(node):
    if isinstance(node, dict):
        if node.get("type") == "object" and "properties" in node:
            properties = node["properties"]
            node["required"] = list(properties.keys())
            node["additionalProperties"] = False
            for child in properties.values():
                _strictify_node(child)

        if node.get("type") == "array" and "items" in node:
            _strictify_node(node["items"])

        for key in ("anyOf", "oneOf", "allOf"):
            if key in node and isinstance(node[key], list):
                for child in node[key]:
                    _strictify_node(child)

    elif isinstance(node, list):
        for child in node:
            _strictify_node(child)


_PLAN_SCHEMA = {
    "title": "Plan",
    "type": "object",
    "properties": {
        "steps": {
            "title": "Steps",
            "description": "List of steps to execute",
            "type": "array",
            "items": {
                "type": "object",
                "title": "PlanStep",
                "properties": {
                    "input_variables": {
                        "title": "Input Variables",
                        "description": "Input variables and their dtypes",
                        "type": "array",
                        "items": {
                            "type": "object",
                            "title": "StepVariable",
                            "properties": {
                                "variable_name": {
                                    "title": "Variable Name",
                                    "description": "Name of the python variable in global scope",
                                    "type": "string",
                                },
                                "variable_description": {
                                    "title": "Variable Description",
                                    "description": "Description of the python variable, in natural language",
                                    "type": "string",
                                },
                                "variable_data_type": {
                                    "title": "Variable Data Type",
                                    "description": "Python type of the variable (python typing). Allowed values: str, int, float, bool, list, dict, tuple, set. Use nested dtypes e.g. list[tuple[int, str]]. Do not use `any` type.",
                                    "type": "string",
                                },
                            },
                            "required": [
                                "variable_name",
                                "variable_description",
                                "variable_data_type",
                            ],
                        },
                        "default": [],
                    },
                    "step_description": {
                        "title": "Step Description",
                        "description": "What this step should accomplish using input variables. The result of the step should be stored in output variables. Include all relevant information from the task, related to this step.",
                        "type": "string",
                    },
                    "output_variables": {
                        "title": "Output Variables",
                        "description": "Output variables and their dtypes",
                        "type": "array",
                        "items": {
                            "type": "object",
                            "title": "StepVariable",
                            "properties": {
                                "variable_name": {
                                    "title": "Variable Name",
                                    "description": "Name of the python variable in global scope",
                                    "type": "string",
                                },
                                "variable_description": {
                                    "title": "Variable Description",
                                    "description": "Description of the python variable, in natural language",
                                    "type": "string",
                                },
                                "variable_data_type": {
                                    "title": "Variable Data Type",
                                    "description": "Python type of the variable (python typing). Allowed values: str, int, float, bool, list, dict, tuple, set. Use nested dtypes e.g. list[tuple[int, str]]. Do not use `any` type.",
                                    "type": "string",
                                },
                            },
                            "required": [
                                "variable_name",
                                "variable_description",
                                "variable_data_type",
                            ],
                        },
                        "default": [],
                    },
                },
            },
            "default": [],
        },
    },
}


_AFTER_STEP_DECISION_SCHEMA = {
    "title": "AfterStepDecision",
    "type": "object",
    "properties": {
        "next_action": {
            "title": "Next Action",
            "description": "What to do next",
            "type": "string",
            "enum": [
                "continue",
                "abort",
                "replan_remaining_steps",
                "task_completed",
            ],
        },
        "abort_reason": {
            "title": "Abort Reason",
            "description": "Why task cannot be completed (for `abort` decision)",
            "anyOf": [{"type": "string"}, {"type": "null"}],
            "default": None,
        },
        "reasons_for_replan_remaining_steps": {
            "title": "Reasons For Replan Remaining Steps",
            "description": "Reason for replanning remaining steps (for `replan_remaining_steps` decision)",
            "anyOf": [{"type": "string"}, {"type": "null"}],
            "default": None,
        },
        "task_completed_reason": {
            "title": "Task Completed Reason",
            "description": "Reason for task completion (for `task_completed` decision)",
            "anyOf": [{"type": "string"}, {"type": "null"}],
            "default": None,
        },
        "task_continue_reason": {
            "title": "Task Continue Reason",
            "description": "Reason for continuing the task (for `continue` decision)",
            "anyOf": [{"type": "string"}, {"type": "null"}],
            "default": None,
        },
    },
}


_RESPONSE_DECISION_SCHEMA = {
    "title": "ResponseDecision",
    "type": "object",
    "properties": {
        "message": {
            "title": "Message",
            "type": "string",
        },
        "reasoning": {
            "title": "Reasoning",
            "type": "string",
        },
    },
}


_STRICT_PLAN_SCHEMA = _make_provider_strict(_PLAN_SCHEMA)
_STRICT_AFTER_STEP_DECISION_SCHEMA = _make_provider_strict(_AFTER_STEP_DECISION_SCHEMA)
_STRICT_RESPONSE_DECISION_SCHEMA = _make_provider_strict(_RESPONSE_DECISION_SCHEMA)


PLAN_SCHEMA_JSON = json.dumps(_STRICT_PLAN_SCHEMA, ensure_ascii=False, indent=4)
AFTER_STEP_DECISION_SCHEMA_JSON = json.dumps(_STRICT_AFTER_STEP_DECISION_SCHEMA, ensure_ascii=False, indent=4)
RESPONSE_DECISION_SCHEMA_JSON = json.dumps(_STRICT_RESPONSE_DECISION_SCHEMA, ensure_ascii=False, indent=4)


_SCHEMA_BY_MODEL_NAME = {
    "Plan": _STRICT_PLAN_SCHEMA,
    "AfterStepDecision": _STRICT_AFTER_STEP_DECISION_SCHEMA,
    "ResponseDecision": _STRICT_RESPONSE_DECISION_SCHEMA,
}


def get_schema_dict(model_name: str) -> dict | None:
    schema = _SCHEMA_BY_MODEL_NAME.get(model_name)
    if schema is None:
        return None
    return deepcopy(schema)
