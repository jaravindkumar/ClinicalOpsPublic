# v4.1 live workflow UX fix

Observed during manual Gate 8 walkthrough:
- reset appeared not to clear persisted Gate 8 state;
- patient selection was independent across tabs;
- invalid appointment/review actions remained clickable;
- reset had no visible acknowledgement.

v4.1 patches those issues and adds `scripts/run_v41_reset_regression.py`.
