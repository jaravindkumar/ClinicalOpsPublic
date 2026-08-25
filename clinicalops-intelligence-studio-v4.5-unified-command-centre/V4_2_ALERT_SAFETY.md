# v4.2 — Alert denominator safeguards

Manual product validation exposed a sparse-data failure that the deterministic benchmark gates did not.

Observed failure:
- Study week 1
- Manchester: 1 observed screening visit
- 1 DNA
- Raw DNA rate = 100%
- v4.1 raised HIGH_DNA and SLOW_RECRUITMENT

v4.2 changes:
- Rate-based HIGH_DNA requires at least 5 observed visits.
- Standalone SLOW_RECRUITMENT requires at least 4 elapsed study weeks.
- The frozen London North week-5 longitudinal signal is preserved for reproducible Gate 7/8 demonstration.
- Alert reasons now expose numerator, denominator, rate, and signal source.

Regression:
`python scripts/run_gate8b_sparse_alert_safety.py`

Then rerun:
`python scripts/run_gate8_golden_journey.py`
