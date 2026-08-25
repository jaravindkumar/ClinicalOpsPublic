# Extractor Comparison

v0.4 adds a comparison workflow for testing extraction quality.

## Extractors

1. Mock extractor
2. Ollama MedGemma

## Metrics

- JSON validity
- extractor failure count
- symptom recall
- red-flag recall
- missing-result recall
- open-loop detection accuracy
- priority exact match

## Why this matters

The product is not judged by whether the model can generate fluent text. It is judged by whether extracted structured information can safely support workflow review.

## Intended workflow

1. Run mock extractor on all synthetic cases.
2. Run Ollama MedGemma on 3-5 cases.
3. Inspect failures.
4. Improve prompt, schema, fallback, or LoopGuard rules.
5. Repeat.
