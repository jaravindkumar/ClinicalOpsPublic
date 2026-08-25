# Gate 5 — deterministic scale/performance

Default ladder: 1K → 10K → 50K → 100K → 300K UK synthetic patients.

Run:
`python scripts/run_gate5_scale.py`

For each scale the gate:
- generates the frozen UK benchmark population
- reruns ground-truth cohort correctness
- executes the production cohort query three times
- builds trial operations from the selected cohort
- records CSV/database size and timings
- requires precision=1.0 and recall=1.0

MedGemma is intentionally not run across the full population. Gate 4 already measures model inference on bounded packets.

For a quick smoke test first:
`python scripts/run_gate5_scale.py --sizes 1000,10000`

If a long run is interrupted, existing generated data can be reused:
`python scripts/run_gate5_scale.py --reuse`
