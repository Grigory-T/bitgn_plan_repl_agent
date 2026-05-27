import unittest

from run_bitgn_task import parse_task_spec, _tasks_to_run_from_state


class TaskIdParsingTests(unittest.TestCase):
    def test_zero_based_single_task_ids(self) -> None:
        self.assertEqual(parse_task_spec("0"), ["t00"])
        self.assertEqual(parse_task_spec("t00"), ["t00"])

    def test_three_digit_single_task_ids(self) -> None:
        self.assertEqual(parse_task_spec("100"), ["t100"])
        self.assertEqual(parse_task_spec("t100"), ["t100"])

    def test_zero_based_ranges_do_not_force_three_digit_padding(self) -> None:
        task_ids = parse_task_spec("t00-t100")
        self.assertEqual(task_ids[:3], ["t00", "t01", "t02"])
        self.assertEqual(task_ids[-3:], ["t98", "t99", "t100"])
        self.assertNotIn("t000", task_ids)

    def test_explicit_three_digit_padding_is_preserved(self) -> None:
        self.assertEqual(
            parse_task_spec("t095-t100"),
            ["t095", "t096", "t097", "t098", "t099", "t100"],
        )


class TaskIdStateSelectionTests(unittest.TestCase):
    def test_state_selection_normalizes_zero_based_numeric_ids(self) -> None:
        state = {
            "run_id": "run-test",
            "task_ids": ["t00", "t01", "t100"],
            "tasks": {
                "t00": {"status": "pending"},
                "t01": {"status": "completed"},
                "t100": {"status": "pending"},
            },
        }
        runnable, skipped = _tasks_to_run_from_state(state, "0,1,100")
        self.assertEqual(runnable, ["t00", "t100"])
        self.assertEqual(skipped, ["t01"])

    def test_state_selection_handles_zero_to_three_digit_ranges(self) -> None:
        task_ids = [f"t{num:02d}" for num in range(100)] + ["t100"]
        state = {
            "run_id": "run-test",
            "task_ids": task_ids,
            "tasks": {task_id: {"status": "pending"} for task_id in task_ids},
        }
        runnable, skipped = _tasks_to_run_from_state(state, "t00-t100")
        self.assertEqual(runnable[0], "t00")
        self.assertEqual(runnable[-1], "t100")
        self.assertEqual(len(runnable), 101)
        self.assertEqual(skipped, [])


if __name__ == "__main__":
    unittest.main()
