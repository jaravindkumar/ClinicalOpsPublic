# Gate 6 — UK multi-site Clinical Operations simulation

Gate 6 moves from component validation to an operational study simulation.

Workflow represented:
population → protocol-eligible source cohort → screening → booking → attendance/DNA →
enrolment → follow-up → operational attention signals.

Six synthetic UK sites receive frozen, known operational problems:
- London Central — capacity constraint
- London North — high DNA/no-show
- Manchester — slow recruitment
- Birmingham — high screen failure
- Leeds — overdue follow-up
- Bristol — unresolved clinical review + data-quality issues

The benchmark calculates site metrics and independently applies attention rules.
Acceptance is strict: exact injected risk-set recovery, FP=0 and FN=0.

First ensure the 10K Gate 5 population exists in this folder:
`python scripts/run_gate5_scale.py --sizes 10000`

Then:
`python scripts/run_gate6_trial_ops.py`

Outputs:
- `benchmark_results/gate6_trial_ops/patient_operations.csv`
- `benchmark_results/gate6_trial_ops/gate6_report.json`

This is a controlled operational benchmark, not a claim of real NHS-site validation.
