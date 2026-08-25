# Gate 4B — field fidelity and safety

Gate 4B scores the exact saved outputs from Gate 4A; it does not rerun MedGemma.

Run Gate 4A first in this folder:
`python scripts/run_gate4a_production_medgemma.py`

Then:
`python scripts/run_gate4b_field_fidelity.py`

The frozen assertions test:
- positive evidence capture
- negation preservation
- missing/pending result detection
- open-loop behaviour
- conflict preservation
- no invented symptoms/tests/results in sparse packets
- normal-result preservation
- follow-up/referral representation

Do not patch individual cases before reviewing the failure class.
