# Gate 7 — 26-week longitudinal study simulation

Six UK sites are observed across 26 simulated study weeks (156 site-weeks).

Frozen risk episodes:
- London North: high DNA, weeks 5–10
- Manchester: slow recruitment, weeks 8–14
- Birmingham: high screen failure, weeks 12–17
- Leeds: overdue follow-up, weeks 15–21
- Bristol: data quality, weeks 18–23

The detector is evaluated both per site-week and per episode.

Metrics:
- weekly alert precision / recall
- FP / FN
- time-to-detection
- recovery detection

Acceptance:
- precision=1.0
- recall=1.0
- zero-week detection delay for these deterministic threshold events
- 100% recovery detection

Run:
`python scripts/run_gate7_longitudinal.py`

This is a controlled synthetic operational benchmark. It does not represent prospective NHS validation.
