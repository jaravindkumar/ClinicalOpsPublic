# v4.4 — Recruitment velocity

v4.3 Gate 8C failed 11/12 for a useful reason: cumulative recruitment was still ~83% of plan at the first deterioration week. Four healthy weeks buffered the cumulative metric.

v4.4 therefore uses two complementary signals:
- cumulative attainment: lagging overall site performance;
- recent recruitment velocity: leading deterioration indicator.

The controlled London North episode falls from a 2.5/week plan to 0.5/week at week 5. SLOW_RECRUITMENT can therefore surface before cumulative attainment falls below 70%.

Run:
python scripts/run_gate8c_recruitment_trajectory.py
python scripts/run_gate8b_sparse_alert_safety.py
python scripts/run_gate8_golden_journey.py
