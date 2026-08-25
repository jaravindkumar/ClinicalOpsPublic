# v4.3 — Recruitment trajectory model

Manual longitudinal validation of v4.2 exposed a second-order product-validity failure: all six sites were labelled SLOW_RECRUITMENT because the simulator had only one manually enrolled patient.

v4.3 replaces raw absolute recruitment thresholds with:
- explicit site-specific weekly recruitment targets;
- deterministic synthetic background recruitment;
- expected vs actual enrolment;
- attainment percentage;
- SLOW_RECRUITMENT only when attainment is <70% after sufficient study exposure.

London North retains the controlled week-5 DNA deterioration. The deterioration suppresses its recruitment trajectory; intervention restores it.

Run:
`python scripts/run_gate8c_recruitment_trajectory.py`
`python scripts/run_gate8b_sparse_alert_safety.py`
`python scripts/run_gate8_golden_journey.py`
