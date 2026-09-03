from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from plan_agent.executor import PERSISTENT_GLOBALS, reset_persistent_globals
from plan_agent.plan import AfterStepDecision, Plan, PlanStep
from plan_agent.prompt_agent import STEP_SYSTEM_PROMPT
from plan_agent.prompt_plan import build_plan_prompt
from plan_agent.run_agent import run_agent
from plan_agent.run_step import run_step


class AgentCoreTests(unittest.TestCase):
    def tearDown(self) -> None:
        reset_persistent_globals()

    def test_plan_requires_at_least_one_step(self) -> None:
        with self.assertRaises(ValueError):
            Plan(steps=[])

    def test_prompts_allow_evidence_based_empty_results(self) -> None:
        self.assertIn("Empty strings or containers are valid", STEP_SYSTEM_PROMPT)
        self.assertIn("never as placeholders", STEP_SYSTEM_PROMPT)
        self.assertNotIn("empty containers", STEP_SYSTEM_PROMPT)

    def test_plan_does_not_require_unnecessary_discovery(self) -> None:
        prompt = build_plan_prompt("create a new file")
        self.assertIn("only when the task depends", prompt)

    def test_decision_requires_reason_matching_its_action(self) -> None:
        with self.assertRaises(ValueError):
            AfterStepDecision(next_action="task_completed")

        decision = AfterStepDecision(
            next_action="task_completed", task_completed_reason="finished"
        )
        self.assertEqual(decision.task_completed_reason, "finished")

    def test_step_completion_markers_do_not_leak(self) -> None:
        plan = Plan(
            steps=[
                PlanStep(step_description="first"),
                PlanStep(step_description="second"),
            ]
        )
        seen_markers: list[tuple[str, str]] = []

        def fake_run_step(**kwargs) -> str:
            seen_markers.append(
                (
                    PERSISTENT_GLOBALS.get("step_status", "missing"),
                    PERSISTENT_GLOBALS.get("final_answer", "missing"),
                )
            )
            PERSISTENT_GLOBALS["step_status"] = "completed"
            PERSISTENT_GLOBALS["final_answer"] = kwargs["current_step"].step_description
            return kwargs["current_step"].step_description

        decisions = iter(
            [
                AfterStepDecision(next_action="continue", task_continue_reason="next"),
                AfterStepDecision(
                    next_action="task_completed",
                    task_completed_reason="done",
                ),
            ]
        )
        with (
            TemporaryDirectory() as directory,
            patch("plan_agent.run_agent.create_plan", return_value=(plan, [])),
            patch("plan_agent.run_agent.run_step", side_effect=fake_run_step),
            patch(
                "plan_agent.run_agent.make_after_step_decision",
                side_effect=lambda **_: next(decisions),
            ),
            patch("plan_agent.run_agent._init_log_dir", return_value=Path(directory)),
        ):
            result, _, step_results = run_agent("task")

        self.assertEqual(result, "done")
        self.assertEqual(step_results, ["first", "second"])
        self.assertEqual(seen_markers, [("", ""), ("", "")])

    def test_step_accepts_output_code_before_final_block(self) -> None:
        class Block:
            def __init__(self, block_text: str):
                self.block_type = "python"
                self.block_text = block_text

        blocks = [
            Block("result = 'value'"),
            Block("step_status = 'completed'\nfinal_answer = 'done'"),
        ]
        step = PlanStep(
            step_description="produce result",
            output_variables=[
                {
                    "variable_name": "result",
                    "variable_description": "result",
                    "variable_data_type": "str",
                }
            ],
        )
        with (
            TemporaryDirectory() as directory,
            patch("plan_agent.run_step.llm", return_value=("response", blocks, "")),
        ):
            answer = run_step(
                task="task",
                current_step=step,
                completed_steps=[],
                log_dir=Path(directory),
                step_index=1,
            )

        self.assertEqual(answer, "done")
        self.assertEqual(PERSISTENT_GLOBALS["result"], "value")


if __name__ == "__main__":
    unittest.main()
