# Product Spec: ClinicalOps Intelligence Studio

## Problem

Healthcare teams lose time and safety margin when critical information is fragmented across notes, patient intake, lab results and referrals. Patients can fall through gaps because a test result is missing, an abnormal result is not actioned, or the original clinical question is not linked to the follow-up.

## Users

1. Clinician / nurse / midwife
2. Pathway operations manager
3. Product owner / clinical safety reviewer
4. Healthtech implementation team

## MVP module

Diagnostic LoopGuard.

## Jobs to be done

- Extract key facts from messy clinical text.
- Identify whether the clinical loop is closed or open.
- Flag missing tests, abnormal results and unresolved referrals.
- Show evidence and reasoning to a clinician.
- Store an audit trail.
- Evaluate performance on synthetic labelled cases.

## Non-goals

- Diagnosis
- Autonomous triage
- Clinical deployment
- Real patient data processing

## Success metrics

- Open-loop detection accuracy
- Red-flag recall
- Missing-result recall
- JSON validity
- Hallucination count
- Clinician override rate
