#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import sys,json,time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.copilot import parse_cohort_request
from src.cohort_engine import filter_population

DATA=ROOT/"benchmark_results"/"uk_1000"/"controlled_fixtures"
CASES=[
("E01","patients aged 50 to 70 with type 2 diabetes and hypertension",dict(age_min=50,age_max=70,inc=["Type 2 diabetes mellitus","Essential hypertension"])),
("E02","find adults 50-70 with diabetes and hypertension excluding CKD",dict(age_min=50,age_max=70,inc=["Type 2 diabetes mellitus","Essential hypertension"],exc=["Chronic kidney disease"])),
("E03","T2DM and hypertension, age 50-70, HbA1c >= 7.5",dict(age_min=50,age_max=70,inc=["Type 2 diabetes mellitus","Essential hypertension"],obs=(">=",7.5))),
("E04","patients aged 50 to 70 with diabetes and hypertension seen within the last 90 days",dict(age_min=50,age_max=70,inc=["Type 2 diabetes mellitus","Essential hypertension"],days=90)),
("E05","Find people aged 50 to 70 with type 2 diabetes and hypertension, HbA1c at least 7.5, seen in the last 90 days, excluding CKD",dict(age_min=50,age_max=70,inc=["Type 2 diabetes mellitus","Essential hypertension"],exc=["Chronic kidney disease"],obs=(">=",7.5),days=90)),
("E06","Exclude chronic kidney disease. I need hypertensive T2DM patients between 50 and 70, HbA1c 7.5 or higher, seen within the last 90 days.",dict(age_min=50,age_max=70,inc=["Type 2 diabetes mellitus","Essential hypertension"],exc=["Chronic kidney disease"],obs=(">=",7.5),days=90)),
]
def expected_ids(spec):
 kw=dict(age_min=spec.get("age_min",0),age_max=spec.get("age_max",120),sex="Any",condition="",exclude_condition="",recent_years=0,
         include_conditions=spec.get("inc",[]),exclude_conditions=spec.get("exc",[]),include_logic="AND",exclude_logic="OR")
 if spec.get("obs"):
  kw.update(observation_description="Hemoglobin A1c/Hemoglobin.total in Blood",observation_operator=spec["obs"][0],observation_value=spec["obs"][1])
 if spec.get("days"):kw.update(recent_days=spec["days"],as_of_date="2026-08-07")
 return set(filter_population(str(DATA),**kw).patient_id.astype(str))
def actual_ids(text):
 d=parse_cohort_request(text) or {}
 kw=dict(age_min=d.get("age_min",0),age_max=d.get("age_max",120),sex="Any",condition="",exclude_condition="",recent_years=0,
         include_conditions=d.get("include_keywords") or d.get("include_conditions") or [],
         exclude_conditions=d.get("exclude_keywords") or d.get("exclude_conditions") or [],include_logic="AND",exclude_logic="OR")
 if d.get("observation_value") is not None:
  kw.update(observation_description=d.get("observation_description","Hemoglobin A1c/Hemoglobin.total in Blood"),
            observation_operator=d.get("observation_operator",">="),observation_value=d["observation_value"])
 if d.get("recent_days") is not None:kw.update(recent_days=d["recent_days"],as_of_date="2026-08-07")
 return d,set(filter_population(str(DATA),**kw).patient_id.astype(str))
def main():
 if not DATA.exists():
  print("Controlled fixtures missing. Run automate_uk_workflow.py first.");raise SystemExit(2)
 rows=[];t0=time.perf_counter()
 for cid,text,spec in CASES:
  exp=expected_ids(spec)
  try:d,act=actual_ids(text);err=None
  except Exception as e:d={};act=set();err=str(e)
  tp=len(exp&act);fp=len(act-exp);fn=len(exp-act)
  precision=tp/len(act) if act else (1.0 if not exp else 0.0)
  recall=tp/len(exp) if exp else (1.0 if not act else 0.0)
  rows.append({"id":cid,"text":text,"expected_n":len(exp),"actual_n":len(act),"tp":tp,"fp":fp,"fn":fn,
               "precision":round(precision,4),"recall":round(recall,4),"exact_match":exp==act,"pass":exp==act,
               "parsed":d,"error":err,"false_positive_ids":sorted(act-exp),"false_negative_ids":sorted(exp-act)})
 passed=sum(r["pass"] for r in rows)
 # Equivalent full-complex prompts E05/E06 must resolve to identical IDs.
 e5=next(r for r in rows if r["id"]=="E05");e6=next(r for r in rows if r["id"]=="E06")
 equivalence=(e5["actual_n"]==e6["actual_n"] and e5["false_positive_ids"]==e6["false_positive_ids"] and e5["false_negative_ids"]==e6["false_negative_ids"])
 out={"gate":"Gate 3C natural language to exact patient set","passed":passed,"total":len(rows),"exact_match_rate":round(passed/len(rows),4),
      "equivalence_consistency":equivalence,"pass":passed==len(rows) and equivalence,"seconds":round(time.perf_counter()-t0,3),"cases":rows}
 op=ROOT/"benchmark_results/gate3c_e2e.json";op.write_text(json.dumps(out,indent=2,default=str))
 print("\n=== GATE 3C — NL → EXACT PATIENT SET ===")
 print(f"Exact matches: {passed}/{len(rows)} ({100*passed/len(rows):.1f}%)")
 for r in rows:
  print(("PASS" if r["pass"] else "FAIL"),r["id"],f"expected={r['expected_n']} actual={r['actual_n']} fp={r['fp']} fn={r['fn']} precision={r['precision']} recall={r['recall']}")
 print("Equivalent complex prompts:", "PASS" if equivalence else "FAIL")
 print("Overall:","PASS" if out["pass"] else "FAIL")
 raise SystemExit(0 if out["pass"] else 2)
if __name__=="__main__":main()
