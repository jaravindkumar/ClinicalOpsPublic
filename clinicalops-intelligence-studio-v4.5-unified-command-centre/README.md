# ClinicalOps Intelligence Studio v1.1

Evidence-grounded Synthea population intelligence, reusable cohort design, local MedGemma batch review, clinician validation, and explainable study/site operations oversight.

## v1.1 highlights
- Population Data Analysis page for demographics, conditions, encounter utilisation and source-data scale.
- Cohort Builder with grouped diagnosis checkboxes, multi-condition AND/OR logic and optional numeric observation/lab thresholds.
- Ask Clinical Ops copilot available from every page sidebar. It answers grounded study questions and can create an editable test-cohort draft from plain language.
- Study Command Centre rebuilt around attention queue, enrollment, country/site risk, data quality, protocol quality and safety operations.
- Saved cohorts can be selected as the candidate source when rebuilding the simulated study.
- Site Risk Drill-down now benchmarks each risk domain against study medians and prioritises subject-level operational workload.
- MedGemma batch outputs flow directly into clinician review and evaluation; there is no mock extractor fallback.

## Run
```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Default Synthea CSV path:
`/Volumes/Aravind_HardDisc/Clinical Ops/synthea/output/csv`

For local MedGemma/Ollama, ensure Ollama is running and the configured model is installed.

Research/portfolio prototype using synthetic data. Not a clinical device and not for patient-care decisions.

## v1.1.2 stability fixes
- Disables Streamlit magic rendering so internal `DeltaGenerator`/runner text cannot leak into the sidebar.
- Uses Ollama structured JSON output plus one MedGemma-only repair pass for malformed model JSON.
- Failed model executions cannot be clinically approved; they remain pipeline failures requiring re-run.
- Evaluation review coverage is calculated only over successfully completed MedGemma outputs.


## v2.0 clean layout
All Streamlit UI calls are explicitly consumed to prevent magic-rendered DeltaGenerator/API documentation from appearing in the sidebar or page body. The shared copilot remains available without exposing internal objects.

## v2.0.4 batch execution notes
- MedGemma runs in a background worker and survives navigation between Streamlit pages.
- The batch activity panel refreshes every 2 seconds and shows the current stage/patient.
- Only one local MedGemma batch may run at a time; duplicate queued runs are blocked.
- Jobs left marked Running after an app restart are automatically marked Interrupted.
- Cancellation is cooperative: it takes effect after the current Ollama request returns.


## UK automated benchmark

Run the complete 1K correctness workflow:

```bash
python scripts/automate_uk_workflow.py --patients 1000
```

Run the scale ladder:

```bash
python scripts/run_scale_benchmark.py --sizes 1000 10000 50000 100000 300000
```

Add a bounded local MedGemma sample after deterministic tests pass:

```bash
python scripts/automate_uk_workflow.py --patients 1000 --medgemma-sample 5
```
