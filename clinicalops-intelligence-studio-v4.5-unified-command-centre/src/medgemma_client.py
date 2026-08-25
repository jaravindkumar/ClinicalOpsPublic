import json
import re
from typing import Optional
import requests

from src.schemas import ExtractionOutput, ClinicalResult

DEFAULT_OLLAMA_MODEL = "hf.co/YADAV0206/medgemma-4b-it-Q4_K_M-GGUF:Q4_K_M"
OLLAMA_URL = "http://localhost:11434/api/generate"


def strip_json_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start:end + 1]
    return text.strip()


def _normalise_extraction_dict(data: dict) -> dict:
    """Normalise model output before Pydantic validation."""
    received_results = []
    for item in data.get("received_results", []) or []:
        if isinstance(item, dict):
            received_results.append(item)
        elif isinstance(item, str):
            received_results.append({"test": "", "finding": item, "status": "unknown"})
    data["received_results"] = received_results

    defaults = {
        "clinical_context": "",
        "symptoms": [],
        "clinical_question": "",
        "ordered_tests": [],
        "received_results": [],
        "missing_results": [],
        "red_flags": [],
        "open_loop": False,
        "priority": "routine review",
        "missing_information": [],
        "model_notes": "Extracted using local Ollama MedGemma."
    }
    for key, value in defaults.items():
        data.setdefault(key, value)
    return data


def parse_extraction_json(raw_response: str) -> ExtractionOutput:
    cleaned = strip_json_fences(raw_response)
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError("MedGemma output was JSON but not a JSON object")
    return ExtractionOutput(**_normalise_extraction_dict(data))


def _json_schema():
    """Return a compact JSON schema when supported by the installed Pydantic."""
    try:
        return ExtractionOutput.model_json_schema()
    except Exception:
        return "json"


def _ollama_generate(prompt: str, model: str, timeout: int):
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        # Ollama structured output mode substantially reduces broken commas,
        # quotes and truncated arrays from local models.
        "format": _json_schema(),
        "keep_alive": "15m",
        "options": {
            "temperature": 0,
            "top_p": 0.9,
            "num_ctx": 6144,
            "num_predict": 1024,
        },
    }
    response = requests.post(OLLAMA_URL, json=payload, timeout=timeout)
    response.raise_for_status()
    return response.json().get("response", "")


def build_extraction_prompt(input_text: str) -> str:
    """Build the bounded MedGemma prompt used for patient-batch extraction.

    The model is asked for a fixed JSON object only. Clinical conclusions must be
    grounded in the supplied synthetic record; uncertainty is represented through
    missing_information rather than invented facts.
    """
    return f"""
You are MedGemma operating inside a clinical-operations research prototype.
Analyse only the synthetic patient record supplied below. Do not provide treatment
advice, do not invent facts, and do not infer diagnoses that are not supported by
the record. Return exactly one JSON object and no markdown or commentary.

Required JSON keys and types:
{{
  "clinical_context": "string",
  "symptoms": ["string"],
  "clinical_question": "string",
  "ordered_tests": ["string"],
  "received_results": [
    {{"test": "string", "finding": "string", "status": "normal|abnormal|unknown"}}
  ],
  "missing_results": ["string"],
  "red_flags": ["string"],
  "open_loop": false,
  "priority": "routine review|follow-up required|clinician review required|urgent clinician review|same-day escalation|emergency escalation",
  "missing_information": ["string"],
  "model_notes": "brief evidence-grounded explanation"
}}

Rules:
- Use empty strings or empty arrays when the record does not support a field.
- Set open_loop=true only when a documented test, result, referral, follow-up, or
  clinically important unresolved item appears outstanding.
- Keep red_flags concise and evidence-based.
- Mention uncertainty in missing_information.
- Never include patient-identifying information in model_notes.

Synthetic patient record:
---
{input_text}
---
""".strip()


def _repair_prompt(raw: str) -> str:
    return f"""
You are a JSON repair utility. Repair the malformed JSON below so it exactly matches
this clinical extraction object shape. Preserve the original clinical meaning; do not
add diagnoses, advice, or unsupported facts. Return JSON only.

Required keys:
clinical_context (string), symptoms (array of strings), clinical_question (string),
ordered_tests (array of strings), received_results (array of objects with test, finding,
status), missing_results (array of strings), red_flags (array of strings), open_loop
(boolean), priority (string), missing_information (array of strings), model_notes (string).

Malformed model output:
{raw}
""".strip()


def ollama_extract(input_text: str, model: str = DEFAULT_OLLAMA_MODEL, timeout: int = 90) -> ExtractionOutput:
    raw = _ollama_generate(build_extraction_prompt(input_text), model, timeout)
    try:
        return parse_extraction_json(raw)
    except Exception as first_error:
        # One bounded repair pass. This remains MedGemma-only: there is no mock fallback.
        try:
            repaired = _ollama_generate(_repair_prompt(raw), model, timeout)
            out = parse_extraction_json(repaired)
            if not out.model_notes:
                out.model_notes = "Structured output repaired by a second local MedGemma pass."
            else:
                out.model_notes = f"{out.model_notes} Structured JSON required one repair pass."
            return out
        except Exception as repair_error:
            raise RuntimeError(
                "MedGemma structured-output validation failed after one repair pass. "
                f"Initial parse: {first_error}; repair parse: {repair_error}"
            )

def _contains(text: str, terms):
    text_l = text.lower()
    return any(t.lower() in text_l for t in terms)


def mock_extract(input_text: str) -> ExtractionOutput:
    text = input_text.lower()

    symptoms = []
    for term in [
        "dizziness", "dizzy", "fatigue", "heavy bleeding", "fever", "stitch pain",
        "pain", "abnormal smell", "unusual smell", "intrusive thoughts", "cannot cope",
        "painful breastfeeding", "persistent cough", "weight loss", "faint", "large clots",
        "thirst", "wound pain"
    ]:
        if term in text:
            symptoms.append(term)

    ordered_tests = []
    test_aliases = {
        "FBC": ["fbc", "full blood count"],
        "ferritin": ["ferritin"],
        "HbA1c": ["hba1c"],
        "X-ray": ["x-ray", "xray", "chest x-ray"],
        "lithium level": ["lithium level"]
    }
    for canonical, aliases in test_aliases.items():
        if any(a in text for a in aliases) and any(w in text for w in ["ordered", "monitoring", "bloods"]):
            ordered_tests.append(canonical)

    received_results = []
    if "hb 8.9" in text or "haemoglobin 8.9" in text or "hemoglobin 8.9" in text:
        received_results.append(ClinicalResult(test="FBC", finding="Hb 8.9 g/dL", status="abnormal"))
    if "hba1c 78" in text:
        received_results.append(ClinicalResult(test="HbA1c", finding="78 mmol/mol", status="abnormal"))
    if "normal range" in text and "fbc" in text:
        received_results.append(ClinicalResult(test="FBC", finding="normal range", status="normal"))
    if "1.4 mmol/l" in text:
        received_results.append(ClinicalResult(test="lithium level", finding="1.4 mmol/L", status="abnormal"))
    if "suspicious right upper lobe opacity" in text:
        received_results.append(ClinicalResult(test="Chest X-ray", finding="suspicious right upper lobe opacity; urgent CT recommended", status="abnormal"))

    missing_results = []
    if "ferritin result is missing" in text:
        missing_results.append("ferritin")
    if "no imaging report" in text or ("x-ray was ordered" in text and "no imaging report" in text):
        missing_results.append("X-ray")

    red_flags = []
    if _contains(text, ["worsening dizziness", "feeling faint", "faint"]):
        red_flags.append("worsening dizziness or faintness")
    if _contains(text, ["hb 8.9", "low haemoglobin", "low hemoglobin"]):
        red_flags.append("low haemoglobin")
    if _contains(text, ["fever"]) and _contains(text, ["unusual smell", "abnormal smell", "stitches", "stitch", "wound pain"]):
        red_flags.append("possible infection")
    if _contains(text, ["baby might be better without her", "intrusive thoughts", "cannot cope"]):
        red_flags.append("mental health / safeguarding concern")
    if _contains(text, ["soaking pads every hour", "large clots", "heavy bleeding"]):
        red_flags.append("heavy bleeding")
    if _contains(text, ["suspicious right upper lobe opacity", "urgent ct"]):
        red_flags.append("abnormal imaging requiring follow-up")
    if _contains(text, ["lithium level returned high", "1.4 mmol/l"]):
        red_flags.append("high lithium level")

    clinical_question = ""
    if _contains(text, ["anaemia", "anemia", "hb 8.9", "heavy bleeding"]):
        clinical_question = "possible anaemia or bleeding complication"
    elif _contains(text, ["fever", "stitches", "unusual smell", "wound pain"]):
        clinical_question = "possible postnatal infection"
    elif _contains(text, ["adhd"]):
        clinical_question = "ADHD assessment referral"
    elif _contains(text, ["knee pain"]):
        clinical_question = "musculoskeletal injury follow-up"
    elif _contains(text, ["hba1c", "thirst", "weight loss"]):
        clinical_question = "possible diabetes"
    elif _contains(text, ["lithium"]):
        clinical_question = "lithium safety monitoring"
    elif _contains(text, ["cough", "weight loss", "opacity"]):
        clinical_question = "possible serious lung pathology"

    missing_information = []
    if _contains(text, ["fever"]) and "temperature" not in text:
        missing_information.append("temperature value")
    if _contains(text, ["bleeding"]) and "amount" not in text and "soaking pads" not in text:
        missing_information.append("bleeding amount")
    if _contains(text, ["stitches", "wound"]) and "wound appearance" not in text:
        missing_information.append("wound appearance")
    if _contains(text, ["cannot cope", "intrusive thoughts"]):
        missing_information.append("immediate safety assessment")
        missing_information.append("support at home")

    abnormal = any(r.status == "abnormal" for r in received_results)
    open_loop = bool(missing_results or red_flags or ("no follow-up" in text) or ("no referral status" in text) or ("no ct order" in text))

    priority = "routine review"
    if _contains(text, ["soaking pads every hour", "large clots", "feeling faint"]):
        priority = "emergency escalation"
    elif _contains(text, ["baby might be better without her", "intrusive thoughts", "cannot cope"]):
        priority = "urgent mental health escalation"
    elif abnormal or _contains(text, ["worsening", "fever"]):
        priority = "urgent clinician review"
    elif _contains(text, ["referral was planned", "no referral status"]):
        priority = "pathway admin follow-up"

    context = ""
    wk_match = re.search(r"(\d+)\s+weeks?\s+postpartum", text)
    day_match = re.search(r"(\d+)\s+days?\s+postpartum", text)
    if wk_match:
        context = f"{wk_match.group(1)} weeks postpartum"
    elif day_match:
        context = f"{day_match.group(1)} days postpartum"

    return ExtractionOutput(
        clinical_context=context,
        symptoms=list(dict.fromkeys(symptoms)),
        clinical_question=clinical_question,
        ordered_tests=list(dict.fromkeys(ordered_tests)),
        received_results=received_results,
        missing_results=list(dict.fromkeys(missing_results)),
        red_flags=list(dict.fromkeys(red_flags)),
        open_loop=open_loop,
        priority=priority,
        missing_information=list(dict.fromkeys(missing_information)),
        model_notes="Mock extraction."
    )


def extract(input_text: str, mode: str = "Ollama MedGemma", model: Optional[str] = None) -> ExtractionOutput:
    return ollama_extract(input_text, model=model or DEFAULT_OLLAMA_MODEL)
