# Evaluation Plan

## Dataset

Synthetic labelled cases covering:

- postnatal red flags
- missing test results
- abnormal lab follow-up
- referral loops
- medication monitoring
- mental health escalation
- normal/no-action cases

## Metrics

- Symptom extraction recall
- Missing result recall
- Red-flag recall
- Open-loop detection accuracy
- Priority exact match
- JSON validity
- Hallucination count

## Most important metric

Red-flag recall.

Missing a high-risk case is worse than over-escalating a low-risk case in a workflow-safety prototype.
