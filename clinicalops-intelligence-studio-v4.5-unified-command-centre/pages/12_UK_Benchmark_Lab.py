import json
from pathlib import Path
import pandas as pd
import streamlit as st
from src.branding import inject_enterprise_css, hero

st.set_page_config(page_title="Benchmark Lab", layout="wide")
inject_enterprise_css()
hero("UK Benchmark Lab","Inspect automated correctness, scale and AI reliability runs without manually repeating the workflow.","Synthetic UK validation")

root=Path("benchmark_results")
reports=sorted(root.glob("uk_*/automation_report.json"), key=lambda p:p.stat().st_mtime, reverse=True) if root.exists() else []
if not reports:
    st.info("No benchmark run found. Run: python scripts/automate_uk_workflow.py --patients 1000")
    st.stop()
chosen=st.selectbox("Benchmark run",reports,format_func=lambda p:p.parent.name)
d=json.loads(Path(chosen).read_text())
st.success("Overall PASS") if d.get("overall_pass") else st.error("Overall FAIL")

st.markdown("## Automated scorecard")
rows=[]
for k,v in d.get("stages",{}).items():
    status = "SKIPPED" if v.get("status")=="skipped" else ("PASS" if v.get("pass",v.get("status")=="complete") else "FAIL")
    rows.append({"Stage":k,"Status":status,
                 "Seconds":v.get("seconds"),"Expected":v.get("expected"),"Actual":v.get("actual"),
                 "Precision":v.get("precision"),"Recall":v.get("recall"),"Detail":v.get("error") or v.get("reason")})
st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)

ce=d.get("stages",{}).get("clinicalops_cohort_engine",{})
c1,c2,c3,c4=st.columns(4)
c1.metric("Expected cohort",ce.get("expected","—")); c2.metric("Actual cohort",ce.get("actual","—"))
c3.metric("False positives",ce.get("fp","—")); c4.metric("False negatives",ce.get("fn","—"))


st.markdown("## Gate 2 — controlled minimal pairs")
g2p=Path(chosen).parent/"gate2_controlled.json"
if g2p.exists():
    g2=json.loads(g2p.read_text())
    st.success("Controlled Gate 2 PASS") if g2.get("pass") else st.error("Controlled Gate 2 FAIL")
    c1,c2,c3=st.columns(3)
    c1.metric("Fixture integrity","PASS" if g2.get("fixture_integrity_pass") else "FAIL")
    c2.metric("HbA1c threshold","PASS" if g2.get("hba1c_threshold",{}).get("pass") else "FAIL")
    c3.metric("90-day recency","PASS" if g2.get("recency_90d",{}).get("pass") else "FAIL")
    st.dataframe(pd.DataFrame(g2.get("cases",[])),use_container_width=True,hide_index=True)

st.markdown("## Ask Clinical Ops parser")
cp=d.get("stages",{}).get("copilot_parser",{})
if cp.get("cases"): st.dataframe(pd.DataFrame(cp["cases"]),use_container_width=True,hide_index=True)

st.markdown("## MedGemma reliability")
mg=d.get("stages",{}).get("medgemma",{})
st.json(mg,expanded=False)

with st.expander("Full machine-readable report"):
    st.json(d)
