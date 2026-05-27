import unittest

from plan_agent import response as response_mod


class ResponseDecisionTests(unittest.TestCase):
    def test_catalog_ref_is_inferred_from_evidence(self) -> None:
        original_llm_structured = response_mod.llm_structured

        def fake_llm_structured(prompt, response_model, model=None):
            return response_mod.ResponseDecision(
                message="Yes, the item is available.",
                outcome="OUTCOME_OK",
                refs=[],
                should_submit_to_bitgn=True,
                reasoning="stub",
            )

        response_mod.llm_structured = fake_llm_structured
        try:
            decision = response_mod.decide_response(
                task="do you have the requested item?",
                agent_answer="Matched product at /proc/catalog/ABC-12345678.json",
                step_results=[],
            )
        finally:
            response_mod.llm_structured = original_llm_structured

        self.assertEqual(decision.outcome, "OUTCOME_OK")
        self.assertEqual(decision.message, "<YES> Yes, the item is available.")
        self.assertEqual(decision.refs, ["/proc/catalog/ABC-12345678.json"])


if __name__ == "__main__":
    unittest.main()
