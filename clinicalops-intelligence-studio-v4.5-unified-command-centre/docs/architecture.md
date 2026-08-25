# Architecture

```text
Clinical text / intake / lab report
        ↓
MedGemma extraction layer
        ↓
Pydantic structured JSON schema
        ↓
LoopGuard rules engine
        ↓
Priority recommendation
        ↓
Clinician review screen
        ↓
SQLite audit log
        ↓
Evaluation dashboard
```

## Components

- `src/medgemma_client.py`: mock extraction now; replace with MedGemma later
- `src/schemas.py`: Pydantic output schemas
- `src/loopguard_engine.py`: explicit workflow-safety rules
- `src/audit_log.py`: SQLite persistence
- `src/evaluation.py`: synthetic case evaluation
- `pages/`: Streamlit UI
