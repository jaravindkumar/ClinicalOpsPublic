from __future__ import annotations

import json
from typing import Dict, Optional
import requests

DEFAULT_GEMMA_MODEL = "gemma3:4b"
OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"


def ollama_health(timeout: int = 2) -> bool:
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=timeout)
        return r.ok
    except Exception:
        return False


def grounded_ops_answer(question: str, context: Dict[str, object], model: str = DEFAULT_GEMMA_MODEL, timeout: int = 90) -> str:
    system = """You are the ClinicalOps Intelligence Studio copilot.
You explain clinical-trial OPERATIONS metrics, not clinical care.
Rules:
- Use only facts in the supplied JSON context.
- Never invent a site, subject, event, metric, diagnosis, or causal claim.
- Separate observed facts from interpretations.
- Keep recommendations operational: review, contact site, inspect queries, verify data, escalate to study leadership.
- Do not provide medical advice or patient-level treatment recommendations.
- If the context is insufficient, say what data is missing.
- Prefer concise executive language.
"""
    payload = {
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": f"Question: {question}\n\nGrounded context:\n{json.dumps(context, default=str)}"},
        ],
        "options": {"temperature": 0.1, "top_p": 0.9, "num_ctx": 8192},
    }
    r = requests.post(OLLAMA_CHAT_URL, json=payload, timeout=timeout)
    r.raise_for_status()
    return r.json().get("message", {}).get("content", "No response returned.")


def deterministic_fallback(question: str, context: Dict[str, object]) -> str:
    summary = context.get("study_summary", {})
    sites = context.get("highest_risk_sites", [])
    if not sites:
        return "The trial database is available, but no site-risk records were returned."
    top = sites[0]
    return (
        f"The highest-risk site is {top.get('site_id')} ({top.get('site_name')}) with a risk score of "
        f"{top.get('risk_score')}. It has {int(top.get('overdue_visits', 0))} overdue visits, "
        f"{int(top.get('open_queries', 0))} open queries and {int(top.get('deviations', 0))} protocol deviations. "
        f"Across the study, {summary.get('high_risk_sites', 0)} sites are currently high risk. "
        "Gemma is not reachable, so this response is a deterministic summary of the stored metrics."
    )
