# Safety Design

## Design principle

MedGemma extracts and structures. It does not make final clinical decisions.

## Safety controls

1. Explicit schema validation
2. Deterministic rules engine
3. Human review screen
4. Audit log
5. Synthetic test dataset
6. Red-flag recall evaluation
7. Clear non-clinical-use warning

## Why this matters

Healthcare AI portfolios should avoid unsafe claims. This product demonstrates safe workflow design by separating model extraction from pathway decision logic and requiring clinician review.
