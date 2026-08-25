# Gate 4 — MedGemma evaluation

This gate does not count a model call as a pass. It evaluates labelled clinical interpretation cases.

1. Generate/view the case pack:
   `python scripts/run_gate4_medgemma_eval.py`
2. Run the cases through the project's real local MedGemma workflow and save a JSON object:
   `{"M01":"...", "M02":"...", ... "M10":"..."}`
3. Score:
   `python scripts/run_gate4_medgemma_eval.py --responses benchmark_results/medgemma_responses.json`

Acceptance for this initial gate: 10/10 decision agreement and zero forced decisions where evidence is insufficient.
The deterministic cohort engine remains authoritative for arithmetic/rule filtering; MedGemma is evaluated for interpretation, ambiguity and evidence-grounded review.
