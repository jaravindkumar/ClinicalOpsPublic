# Gate 6.1 — causal Clinical Operations benchmark

v3.4 exposed two benchmark-design issues:
1. some intended primary risks were not actually injected strongly enough to cross their own thresholds;
2. high DNA and high screen failure naturally propagated into slow recruitment, so exact one-label matching incorrectly counted plausible downstream effects as false positives.

v3.5 freezes a causal interpretation:
- HIGH_DNA → expected downstream SLOW_RECRUITMENT
- HIGH_SCREEN_FAILURE → expected downstream SLOW_RECRUITMENT

It also makes London Central genuinely capacity constrained and Manchester genuinely slow recruiting.

Run:
`python scripts/run_gate5_scale.py --sizes 10000`
`python scripts/run_gate6_1_causal_ops.py`

Acceptance:
- primary-cause recall = 1.0
- expected-effect recall = 1.0
- unexpected alerts = 0
- every expected alert is metric-grounded
