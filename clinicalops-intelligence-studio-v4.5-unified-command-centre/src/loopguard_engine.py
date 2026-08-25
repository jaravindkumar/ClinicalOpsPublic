from typing import List
from src.schemas import ExtractionOutput, RuleTrigger

def run_loopguard_rules(extraction: ExtractionOutput, original_text: str = "") -> List[RuleTrigger]:
    text = original_text.lower()
    triggers = []
    def add(rule_id, name, flag, priority, evidence):
        triggers.append(RuleTrigger(rule_id=rule_id, name=name, flag=flag, priority=priority, evidence=evidence))

    if extraction.ordered_tests and extraction.missing_results:
        add("R001", "Ordered test missing result", "open diagnostic loop", "follow-up required", f"Missing results: {', '.join(extraction.missing_results)}")

    abnormal = [r for r in extraction.received_results if r.status == "abnormal"]
    if abnormal and any(x in text for x in ["no follow-up", "no medication review", "no ct order", "no referral"]):
        add("R002", "Abnormal result without documented follow-up", "unresolved abnormal result", "clinician review required", "; ".join([f"{r.test}: {r.finding}" for r in abnormal]))

    if abnormal and any(x in " ".join(extraction.red_flags).lower() for x in ["worsening", "faint", "dizziness"]):
        add("R003", "Worsening symptoms with abnormal result", "clinical deterioration risk", "urgent clinician review", "Abnormal result plus worsening symptoms/faintness signal")

    if "possible infection" in extraction.red_flags or ("fever" in text and ("stitch" in text or "unusual smell" in text)):
        add("R004", "Postnatal infection pattern", "possible postnatal infection", "same-day clinical review", "Fever plus wound/stitch pain or abnormal smell")

    if any(x in text for x in ["baby might be better without", "intrusive thoughts", "cannot cope"]):
        add("R005", "Postnatal mental health crisis pattern", "safeguarding / mental health red flag", "urgent mental health escalation", "Language suggests severe distress or intrusive thoughts")

    if any(x in text for x in ["soaking pads every hour", "large clots", "feeling faint"]):
        add("R006", "Heavy bleeding and faintness", "possible severe bleeding", "emergency escalation", "Heavy bleeding with clots or faintness")

    if "referral was planned" in text and ("no referral status" in text or "appointment date" in text):
        add("R007", "Planned referral missing status", "incomplete referral loop", "pathway admin follow-up", "Referral planned but status or appointment date missing")

    return triggers

def recommended_priority(extraction: ExtractionOutput, triggers: List[RuleTrigger]) -> str:
    order = ["emergency escalation", "urgent mental health escalation", "urgent clinician review", "same-day clinical review", "clinician review required", "follow-up required", "pathway admin follow-up", "routine review"]
    priorities = [t.priority for t in triggers] + [extraction.priority]
    for p in order:
        if p in priorities:
            return p
    return priorities[0] if priorities else "routine review"
