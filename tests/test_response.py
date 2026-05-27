import unittest

from plan_agent import response as response_mod


class ResponseDecisionTests(unittest.TestCase):
    def test_preflight_outcome_hint_overrides_response_model_choice(self) -> None:
        original_llm_structured = response_mod.llm_structured

        def fake_llm_structured(prompt, response_model, model=None):
            return response_mod.ResponseDecision(
                message="Please clarify the requested action.",
                outcome="OUTCOME_OK",
                refs=[],
                should_submit_to_bitgn=True,
                reasoning="stub",
            )

        response_mod.llm_structured = fake_llm_structured
        try:
            decision = response_mod.decide_response(
                task="Process this inbox ent",
                agent_answer=(
                    "Request denied at preflight. Recommended outcome: "
                    "OUTCOME_NONE_CLARIFICATION. Message: Task is incomplete."
                ),
                step_results=[],
            )
        finally:
            response_mod.llm_structured = original_llm_structured

        self.assertEqual(decision.outcome, "OUTCOME_NONE_CLARIFICATION")


if __name__ == "__main__":
    unittest.main()
