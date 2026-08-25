# v0.8 Trial Operations Intelligence

## Product decision

The Clinical Ops layer is separated into two systems:

1. **Deterministic operations intelligence** — study/site/subject/visit state, KRI metrics and risk scoring.
2. **Gemma explanation layer** — receives compact precomputed evidence and explains what needs attention.

Gemma does not calculate risk scores and does not read millions of raw EHR rows.

## Data flow

```text
Synthea CSV (immutable source)
        ↓
DuckDB query layer
        ↓
bounded screened/enrolled cohort
        ↓
multicentre trial simulator
        ↓
subjects / visits / queries / deviations / AEs
        ↓
site KRI metrics
        ↓
explainable weighted risk score
        ↓
Study Command Centre + Site Drill-down
        ↓
Grounded local Gemma copilot
```

## Risk score

The current score is intentionally transparent:

- enrollment: 20%
- visit compliance: 25%
- data quality / query burden: 20%
- protocol compliance: 20%
- safety operations: 15%

This is a portfolio simulation, not a validated clinical-trial risk model.

## Scaling to ~300K source patients

The simulator does not materialise every Synthea event into the application database. DuckDB scans source tables for eligibility/complexity features and materialises only the trial cohort and operational events. At larger scale:

- convert high-volume CSVs to Parquet;
- partition by patient/date where useful;
- precompute patient feature tables;
- keep Gemma context at the study/site aggregate level;
- move multi-user operational state to PostgreSQL if needed.
