import streamlit as st
from src.branding import inject_enterprise_css, hero, enterprise_card, workflow_step

_ = st.set_page_config(page_title="Product Case Study", layout="wide")
_ = inject_enterprise_css()

_ = hero(
    "Product Case Study",
    "ClinicalOps Intelligence Studio is a portfolio-grade healthcare AI product case study focused on workflow safety, model boundaries and evaluation.",
    "Portfolio narrative"
)

_ = st.markdown("## Problem")
_ = st.markdown("""
Healthcare follow-up work is fragmented across notes, test orders, lab results, referrals and patient communications.
Risk can emerge when a test is ordered but no result returns, an abnormal result is not followed up, or a referral is planned but not completed.
""")

_ = st.markdown("## Product thesis")
_ = st.markdown("""
Medical foundation models should not directly own clinical decisions.  
They should extract, structure, flag and explain information inside a workflow where deterministic rules, auditability and human review control the final decision.
""")

_ = st.markdown("## Users")
c1, c2, c3 = st.columns(3)
with c1:
    _ = enterprise_card("Clinician reviewer", "Reviews open loops, missing results and unresolved follow-up risks before confirming final action.")
with c2:
    _ = enterprise_card("Pathway operations lead", "Monitors bottlenecks, incomplete actions and unresolved patient-pathway items.")
with c3:
    _ = enterprise_card("AI product / safety owner", "Measures model extraction quality, failure modes, overrides and auditability.")

_ = st.markdown("## Architecture")
_ = workflow_step(1, "Clinical text enters", "Patient intake, clinician notes, lab report snippets or referral status text.")
_ = workflow_step(2, "MedGemma-ready extraction", "The model extracts structured symptoms, tests, results, red flags and missing information.")
_ = workflow_step(3, "LoopGuard rules engine", "Explicit rules detect missing results, abnormal results without action, unresolved referrals and high-risk patterns.")
_ = workflow_step(4, "Clinician review", "The reviewer sees evidence, triggered rules and suggested priority, then approves, edits, dismisses or escalates.")
_ = workflow_step(5, "Audit and evaluation", "Decisions are logged and extraction quality is compared against synthetic gold labels.")

_ = st.markdown("## Safety design")
_ = st.markdown("""
- The model is constrained to extraction and structuring.
- Output is validated against a schema.
- Rules are explicit and inspectable.
- Human review is required.
- Decisions are audit logged.
- Synthetic cases are used before any real data.
- Evaluation focuses on red-flag recall and open-loop detection, not fluent text.
""")

_ = st.markdown("## What this demonstrates")
_ = st.markdown("""
This project demonstrates AI product judgement:

- healthcare workflow understanding
- safe use of medical foundation models
- human-in-the-loop product design
- structured outputs and schema validation
- deterministic rules for safety-critical workflow logic
- auditability
- measurable evaluation
- failure-mode analysis
""")

_ = st.markdown("## Interview pitch")
_ = st.markdown("""
> I built ClinicalOps Intelligence Studio to explore how medical foundation models can support healthcare workflow safety without replacing clinicians. The first module, Diagnostic LoopGuard, uses MedGemma-ready extraction to structure patient intake, clinical notes and lab results, then applies deterministic rules to detect missing results, unresolved follow-ups and open diagnostic loops. I added clinician review, audit logs and an extractor comparison dashboard to measure model failure modes instead of trusting generated text by default.
""")
