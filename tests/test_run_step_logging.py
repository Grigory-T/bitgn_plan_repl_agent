import tempfile
import unittest
from pathlib import Path

from plan_agent import run_step as run_step_mod
from plan_agent.executor import PERSISTENT_GLOBALS, reset_persistent_globals
from plan_agent.plan import PlanStep, StepVariable


class _FakeBitgn:
    def tree_with_line_counts(self, path="/", level=0):
        return "/\n  products/\n    SKU.json [3]"


class RunStepLoggingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_llm = run_step_mod.llm
        reset_persistent_globals()

    def tearDown(self) -> None:
        run_step_mod.llm = self.original_llm
        reset_persistent_globals()

    def test_initial_tree_and_input_variables_are_logged_old_style(self) -> None:
        PERSISTENT_GLOBALS["bitgn"] = _FakeBitgn()
        PERSISTENT_GLOBALS["catalog_match"] = {"sku": "SKU"}

        def fake_llm(messages, model=None):
            return (
                "<python>\nstep_status = 'completed'\nfinal_answer = 'done\\nRelevant files: none'\n</python>",
                [
                    type(
                        "Block",
                        (),
                        {
                            "block_type": "python",
                            "block_text": "step_status = 'completed'\nfinal_answer = 'done\\nRelevant files: none'",
                        },
                    )()
                ],
                "",
            )

        run_step_mod.llm = fake_llm
        current_step = PlanStep(
            step_description="Use previous catalogue match.",
            input_variables=[
                StepVariable(
                    variable_name="catalog_match",
                    variable_description="Matched catalogue record",
                    variable_data_type="dict",
                )
            ],
            output_variables=[],
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            result = run_step_mod.run_step(
                task="answer catalogue question",
                current_step=current_step,
                completed_steps=[],
                log_dir=Path(temp_dir),
                step_index=1,
            )
            messages = (Path(temp_dir) / "step_1" / "messages.txt").read_text(encoding="utf-8")

        self.assertIn("done", result)
        self.assertIn("print(bitgn.tree_with_line_counts('/'))", messages)
        self.assertIn("SKU.json [3]", messages)
        self.assertIn("INPUT VARIABLES SNAPSHOT", messages)
        self.assertIn("NAME: catalog_match", messages)


if __name__ == "__main__":
    unittest.main()
