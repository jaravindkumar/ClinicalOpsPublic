#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import sys, json, re, time
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from src.copilot import parse_cohort_request
try:
    from src.copilot import parse_recency_days
except ImportError:
    def parse_recency_days(text): return None

CASES=[
{"id":"S01","text":"patients aged 50 to 70 with type 2 diabetes and hypertension","age":[50,70],"inc":["diabetes","hypertension"]},
{"id":"S02","text":"people between 50 and 70 with T2DM and high blood pressure","age":[50,70],"inc":["diabetes","hypertension"]},
{"id":"S03","text":"find adults 50-70 with diabetes and hypertension excluding CKD","age":[50,70],"inc":["diabetes","hypertension"],"exc":["ckd"]},
{"id":"S04","text":"aged 50 to 70, type 2 diabetes, hypertension, but no chronic kidney disease","age":[50,70],"inc":["diabetes","hypertension"],"exc":["ckd"]},
{"id":"N01","text":"patients aged 50 to 70 with type 2 diabetes and hypertension with HbA1c at least 7.5","age":[50,70],"inc":["diabetes","hypertension"],"obs":[">=",7.5]},
{"id":"N02","text":"T2DM and hypertension, age 50-70, HbA1c >= 7.5","age":[50,70],"inc":["diabetes","hypertension"],"obs":[">=",7.5]},
{"id":"T01","text":"patients aged 50 to 70 with diabetes and hypertension seen within the last 90 days","age":[50,70],"inc":["diabetes","hypertension"],"days":90},
{"id":"T02","text":"50-70 year olds with T2DM and high blood pressure seen in the past 30 days","age":[50,70],"inc":["diabetes","hypertension"],"days":30},
{"id":"T03","text":"diabetes and hypertension patients aged 50 to 70 with an encounter in the last 180 days","age":[50,70],"inc":["diabetes","hypertension"],"days":180},
{"id":"C01","text":"Find people aged 50 to 70 with type 2 diabetes and hypertension, HbA1c at least 7.5, seen in the last 90 days, excluding CKD","age":[50,70],"inc":["diabetes","hypertension"],"exc":["ckd"],"obs":[">=",7.5],"days":90},
{"id":"C02","text":"Exclude chronic kidney disease. I need hypertensive T2DM patients between 50 and 70, HbA1c 7.5 or higher, seen within the last 90 days.","age":[50,70],"inc":["diabetes","hypertension"],"exc":["ckd"],"obs":[">=",7.5],"days":90},
{"id":"W01","text":"Could you build me a cohort of people between fifty and seventy with type 2 diabetes and hypertension?","inc":["diabetes","hypertension"]},
{"id":"A01","text":"patients with diabetes","inc":["diabetes"]},
{"id":"A02","text":"patients without CKD","exc":["ckd"]},
]
# Add paraphrase permutations without inventing new clinical meaning.
bases=[
("aged 50 to 70 with type 2 diabetes and hypertension", [50,70],["diabetes","hypertension"],[],None,None),
("between 50 and 70 with T2DM and hypertension excluding CKD",[50,70],["diabetes","hypertension"],["ckd"],None,None),
("age 50-70 diabetes hypertension HbA1c at least 7.5",[50,70],["diabetes","hypertension"],[],[">=",7.5],None),
("age 50-70 diabetes hypertension seen within the last 90 days",[50,70],["diabetes","hypertension"],[],None,90),
]
prefixes=["find patients ","build a cohort of ","show me ","identify ","I need "]
for bi,b in enumerate(bases):
 for pi,pfx in enumerate(prefixes):
  CASES.append({"id":f"P{bi}{pi}","text":pfx+b[0],"age":b[1],"inc":b[2],"exc":b[3],"obs":b[4],"days":b[5]})

def norm_terms(d):
 vals=d.get("include_keywords") or d.get("include_conditions") or []
 return " ".join(map(str,vals)).lower()
def norm_exc(d):
 vals=d.get("exclude_keywords") or d.get("exclude_conditions") or []
 return " ".join(map(str,vals)).lower()
def concept_ok(blob,concept):
 aliases={"diabetes":["diabetes","t2dm","type 2"],"hypertension":["hypertension","high blood pressure"],"ckd":["ckd","chronic kidney"]}
 return any(x in blob for x in aliases[concept])
def age_from(d):
 lo=d.get("age_min"); hi=d.get("age_max")
 return [lo,hi] if lo is not None and hi is not None else None
def obs_from(d):
 op=d.get("observation_operator"); val=d.get("observation_value")
 if val is None:
  op=d.get("hba1c_operator"); val=d.get("hba1c_value")
 return [op,float(val)] if val is not None else None

def main():
 t0=time.perf_counter(); results=[]
 for c in CASES:
  try: d=parse_cohort_request(c["text"]) or {}
  except Exception as e:
   results.append({"id":c["id"],"text":c["text"],"pass":False,"issues":[f"parser exception: {e}"]}); continue
  issues=[]; ib=norm_terms(d); eb=norm_exc(d)
  if c.get("age") and age_from(d)!=c["age"]: issues.append(f"age expected {c['age']} got {age_from(d)}")
  for x in c.get("inc",[]):
   if not concept_ok(ib,x): issues.append(f"missing inclusion {x}")
  for x in c.get("exc",[]):
   if not concept_ok(eb,x): issues.append(f"missing exclusion {x}")
  if c.get("obs"):
   got=obs_from(d)
   if not got or got[0]!=c["obs"][0] or abs(got[1]-c["obs"][1])>.001: issues.append(f"observation expected {c['obs']} got {got}")
  if c.get("days"):
   got=d.get("recent_days")
   if got is None: got=parse_recency_days(c["text"])
   if got!=c["days"]: issues.append(f"recency expected {c['days']} got {got}")
  results.append({"id":c["id"],"text":c["text"],"pass":not issues,"issues":issues,"parsed":d})
 passed=sum(x["pass"] for x in results); total=len(results)
 out={"gate":"Gate 3 language semantics","pass":passed==total,"passed":passed,"total":total,
      "accuracy":round(passed/total,4),"seconds":round(time.perf_counter()-t0,3),"cases":results}
 outp=ROOT/"benchmark_results/gate3_language.json"; outp.parent.mkdir(exist_ok=True)
 outp.write_text(json.dumps(out,indent=2,default=str))
 print("\n=== GATE 3 — ASK CLINICAL OPS LANGUAGE ===")
 print(f"Passed: {passed}/{total} ({100*passed/total:.1f}%)")
 for x in results:
  if not x["pass"]: print("FAIL",x["id"],"::","; ".join(x["issues"]))
 print("Overall:","PASS" if out["pass"] else "FAIL")
 raise SystemExit(0 if out["pass"] else 2)
if __name__=="__main__": main()
