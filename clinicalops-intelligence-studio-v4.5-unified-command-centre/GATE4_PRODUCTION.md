# Gate 4 — production-path MedGemma

This benchmark calls the same `src.medgemma_client.extract()` path used by batch jobs.
It requires local Ollama and the configured MedGemma model.

Run:
`python scripts/run_gate4a_production_medgemma.py`

Gate 4A establishes the real baseline:
- inference/schema success
- inference failures
- latency
- required evidence recall
- raw structured outputs for conflict, missing-result, sparse and negated-evidence review

Do not tune the cases after seeing the model output. Gate 4B will score extraction-field fidelity,
hallucination/negation handling and appropriate missing-information behaviour using this frozen baseline.
