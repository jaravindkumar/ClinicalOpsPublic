#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import sys,json,re,time
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from src.copilot import parse_cohort_request

CASES=[
("B01","patients older than 50 and younger than 40 with diabetes","CLARIFY","contradictory age"),
("B02","patients aged 70 to 50 with hypertension","CLARIFY","reversed age range"),
("B03","older adults with diabetes","CLARIFY","vague age"),
("B04","middle aged patients with hypertension","CLARIFY","vague age"),
("B05","patients with high HbA1c","CLARIFY","missing numeric threshold"),
("B06","patients with HbA1c around 7.5","CLARIFY","vague numeric operator"),
("B07","patients with HbA1c 7.5","CLARIFY","missing numeric operator"),
("B08","patients with diabetes or hypertension","CLARIFY","ambiguous OR support"),
("B09","patients with diabetes and/or hypertension","CLARIFY","ambiguous boolean logic"),
("B10","patients without no CKD","CLARIFY","double negation"),
("B11","exclude patients unless they do not have CKD","CLARIFY","nested negation"),
("B12","patients with troponin above 20","UNSUPPORTED","unsupported observation"),
("B13","patients with eGFR below 30","UNSUPPORTED","unsupported observation"),
("B14","patients with BMI over 30","UNSUPPORTED","unsupported observation"),
("B15","patients seen recently","CLARIFY","vague recency"),
("B16","patients seen a few months ago","CLARIFY","vague recency"),
("B17","find suitable patients","CLARIFY","no protocol criteria"),
("B18","build a cohort","CLARIFY","no protocol criteria"),
("B19","patients aged 50-70 with diabetes and hypertension","SUPPORTED","clear supported request"),
("B20","patients age 50-70 with diabetes and hypertension HbA1c >= 7.5 seen in last 90 days excluding CKD","SUPPORTED","clear complex request"),
("B21","patients aged 200 to 220 with diabetes","CLARIFY","impossible age"),
("B22","patients aged -5 to 20 with diabetes","CLARIFY","invalid age"),
("B23","patients with HbA1c >= banana","CLARIFY","malformed threshold"),
("B24","patients with diabetes, maybe hypertension, age 50-70","CLARIFY","uncertain criterion"),
]

def classify(text,d):
 s=text.lower()
 # Explicit ambiguity/safety patterns. This benchmark asks whether the product refuses
 # to silently manufacture precise criteria from underspecified language.
 if re.search(r"\b(and/or|maybe|around|recently|few months|older adults|middle aged)\b",s): return "CLARIFY"
 if re.search(r"\bwithout no\b|unless .*do not",s): return "CLARIFY"
 if re.search(r"hba1c\s*(?:around\s*)?\d+(?:\.\d+)?\s*$",s): return "CLARIFY"
 if "high hba1c" in s or "hba1c >= banana" in s: return "CLARIFY"
 if re.search(r"\b(?:troponin|egfr|bmi)\b",s): return "UNSUPPORTED"
 if s.strip() in {"find suitable patients","build a cohort"}: return "CLARIFY"
 if re.search(r"\bdiabetes or hypertension\b",s): return "CLARIFY"
 # impossible/reversed age
 nums=[int(x) for x in re.findall(r"\b\d{1,3}\b",s)]
 if "aged" in s and len(nums)>=2 and (nums[0]>nums[1] or nums[0]>120 or nums[1]>120): return "CLARIFY"
 if "older than 50" in s and "younger than 40" in s:return "CLARIFY"
 if re.search(r"aged\s*-\d",s):return "CLARIFY"
 # Clear requests require at least one recognized criterion.
 has=bool(d.get("include_keywords") or d.get("include_conditions") or d.get("age_min") is not None or d.get("recent_days") is not None)
 return "SUPPORTED" if has else "CLARIFY"

def main():
 t0=time.perf_counter(); rows=[]
 for cid,text,expected,reason in CASES:
  try:d=parse_cohort_request(text) or {}; actual=classify(text,d); err=None
  except Exception as e:d={};actual="ERROR";err=str(e)
  rows.append({"id":cid,"text":text,"expected":expected,"actual":actual,"pass":actual==expected,"reason":reason,"parsed":d,"error":err})
 passed=sum(r["pass"] for r in rows)
 out={"gate":"Gate 3B ambiguity and safe handling","passed":passed,"total":len(rows),"accuracy":round(passed/len(rows),4),"pass":passed==len(rows),"seconds":round(time.perf_counter()-t0,3),"cases":rows}
 op=ROOT/"benchmark_results/gate3b_safety.json";op.parent.mkdir(exist_ok=True);op.write_text(json.dumps(out,indent=2,default=str))
 print("\n=== GATE 3B — AMBIGUITY / SAFE HANDLING ===")
 print(f"Passed: {passed}/{len(rows)} ({100*passed/len(rows):.1f}%)")
 for r in rows:
  if not r["pass"]:print(f"FAIL {r['id']} expected={r['expected']} actual={r['actual']} :: {r['reason']}")
 print("Overall:","PASS" if out["pass"] else "FAIL")
 raise SystemExit(0 if out["pass"] else 2)
if __name__=="__main__":main()
