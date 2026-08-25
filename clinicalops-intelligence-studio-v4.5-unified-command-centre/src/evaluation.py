from typing import List, Dict, Any, Tuple
import pandas as pd

from src.medgemma_client import mock_extract, ollama_extract, DEFAULT_OLLAMA_MODEL
from src.loopguard_engine import run_loopguard_rules, recommended_priority


def _normalise(items):
    return set([str(x).lower().strip() for x in items if str(x).strip()])


def _set_recall(predicted, gold):
    predicted = _normalise(predicted)
    gold = _normalise(gold)
    if not gold:
        return 1.0
    return len(predicted.intersection(gold)) / len(gold)


def _result_names(results):
    names = []
    for item in results:
        if isinstance(item, dict):
            names.append(item.get("test", "") or item.get("finding", ""))
        else:
            names.append(getattr(item, "test", "") or getattr(item, "finding", ""))
    return [x for x in names if x]


def evaluate_one_case(case: Dict[str, Any], extraction) -> Dict[str, Any]:
    gold = case["gold"]
    triggers = run_loopguard_rules(extraction, case["input_text"])
    priority = recommended_priority(extraction, triggers)

    red_flags = extraction.red_flags
    symptoms = extraction.symptoms
    missing_results = extraction.missing_results

    return {
        "case_id": case["case_id"],
        "pathway": case["pathway"],
        "severity": case["severity"],
        "gold_open_loop": bool(gold["open_loop"]),
        "pred_open_loop": bool(extraction.open_loop or triggers),
        "open_loop_correct": bool(gold["open_loop"]) == bool(extraction.open_loop or triggers),
        "symptom_recall": round(_set_recall(symptoms, gold["symptoms"]), 2),
        "missing_result_recall": round(_set_recall(missing_results, gold["missing_results"]), 2),
        "red_flag_recall": round(_set_recall(red_flags, gold["red_flags"]), 2),
        "ordered_test_recall": round(_set_recall(extraction.ordered_tests, gold["ordered_tests"]), 2),
        "received_result_recall": round(_set_recall(_result_names(extraction.received_results), _result_names(gold["received_results"])), 2),
        "gold_priority": gold["priority"],
        "pred_priority": priority,
        "priority_exact_match": gold["priority"].lower() == priority.lower(),
        "trigger_count": len(triggers),
        "json_valid": True,
        "model_notes": extraction.model_notes,
    }


def evaluate_cases(cases: List[Dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for case in cases:
        extraction = mock_extract(case["input_text"])
        rows.append(evaluate_one_case(case, extraction))
    return pd.DataFrame(rows)


def compare_extractors(
    cases: List[Dict[str, Any]],
    run_ollama: bool = False,
    ollama_model: str = DEFAULT_OLLAMA_MODEL,
    max_cases: int | None = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Compare mock extraction with local Ollama MedGemma extraction.

    Returns:
    - case-level dataframe
    - summary dataframe
    """
    selected_cases = cases[:max_cases] if max_cases else cases
    rows = []

    for case in selected_cases:
        # Mock baseline
        try:
            mock_output = mock_extract(case["input_text"])
            row = evaluate_one_case(case, mock_output)
            row["extractor"] = "Mock extractor"
            row["extractor_failed"] = False
            rows.append(row)
        except Exception as e:
            rows.append({
                "case_id": case["case_id"],
                "pathway": case["pathway"],
                "severity": case["severity"],
                "extractor": "Mock extractor",
                "extractor_failed": True,
                "model_notes": str(e),
                "json_valid": False,
            })

        # Ollama MedGemma
        if run_ollama:
            try:
                med_output = ollama_extract(case["input_text"], model=ollama_model)
                row = evaluate_one_case(case, med_output)
                row["extractor"] = "Ollama MedGemma"
                # If the client fell back, this will appear in model_notes.
                row["extractor_failed"] = "falling back" in (med_output.model_notes or "").lower()
                rows.append(row)
            except Exception as e:
                rows.append({
                    "case_id": case["case_id"],
                    "pathway": case["pathway"],
                    "severity": case["severity"],
                    "extractor": "Ollama MedGemma",
                    "extractor_failed": True,
                    "model_notes": str(e),
                    "json_valid": False,
                })

    df = pd.DataFrame(rows)

    summary_rows = []
    for extractor, group in df.groupby("extractor"):
        summary_rows.append({
            "extractor": extractor,
            "cases": len(group),
            "extractor_failures": int(group.get("extractor_failed", pd.Series([False] * len(group))).fillna(False).sum()),
            "json_valid_rate": round(group.get("json_valid", pd.Series([False] * len(group))).fillna(False).mean(), 2),
            "open_loop_accuracy": round(group.get("open_loop_correct", pd.Series([0] * len(group))).fillna(False).mean(), 2),
            "avg_symptom_recall": round(group.get("symptom_recall", pd.Series([0] * len(group))).fillna(0).mean(), 2),
            "avg_red_flag_recall": round(group.get("red_flag_recall", pd.Series([0] * len(group))).fillna(0).mean(), 2),
            "avg_missing_result_recall": round(group.get("missing_result_recall", pd.Series([0] * len(group))).fillna(0).mean(), 2),
            "priority_exact_match_rate": round(group.get("priority_exact_match", pd.Series([0] * len(group))).fillna(False).mean(), 2),
        })

    return df, pd.DataFrame(summary_rows)
