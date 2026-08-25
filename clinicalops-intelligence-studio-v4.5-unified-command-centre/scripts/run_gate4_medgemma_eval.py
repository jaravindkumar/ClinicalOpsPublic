#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import argparse,json,time,re,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))

CASES=[
{"id":"M01","class":"sufficient","record":"Age 62. Type 2 diabetes mellitus. Essential hypertension. No chronic kidney disease. HbA1c 8.1%. Encounter 30 days ago.","question":"Assess eligibility for age 50-70, T2DM + hypertension, HbA1c >=7.5, encounter <=90 days, exclude CKD.","expected":"ELIGIBLE","evidence":["62","diabetes","hypertension","8.1","30"]},
{"id":"M02","class":"exclusion","record":"Age 61. Type 2 diabetes mellitus. Essential hypertension. Chronic kidney disease documented. HbA1c 8.4%. Encounter 20 days ago.","question":"Assess the same protocol.","expected":"INELIGIBLE","evidence":["chronic kidney disease"]},
{"id":"M03","class":"threshold","record":"Age 60. Type 2 diabetes mellitus. Essential hypertension. No CKD. HbA1c 7.4%. Encounter 10 days ago.","question":"Assess the same protocol.","expected":"INELIGIBLE","evidence":["7.4"]},
{"id":"M04","class":"boundary","record":"Age 50. Type 2 diabetes mellitus. Essential hypertension. No CKD. HbA1c 7.5%. Encounter exactly 90 days ago.","question":"Assess the same protocol.","expected":"ELIGIBLE","evidence":["50","7.5","90"]},
{"id":"M05","class":"temporal","record":"Age 65. Type 2 diabetes mellitus. Essential hypertension. No CKD. HbA1c 8.0%. Last encounter 91 days ago.","question":"Assess the same protocol.","expected":"INELIGIBLE","evidence":["91"]},
{"id":"M06","class":"missing","record":"Age 64. Type 2 diabetes mellitus. Essential hypertension. No CKD. Encounter 20 days ago. No HbA1c result is available.","question":"Assess the same protocol.","expected":"INSUFFICIENT","evidence":["no hba1c"]},
{"id":"M07","class":"missing","record":"Age 64. Type 2 diabetes mellitus. HbA1c 8.0%. Encounter 20 days ago. Hypertension status is not documented.","question":"Assess the same protocol.","expected":"INSUFFICIENT","evidence":["not documented"]},
{"id":"M08","class":"conflict","record":"Age 59. Type 2 diabetes mellitus. Essential hypertension. No CKD. HbA1c results: 5.8% and 10.2% on the same date. Encounter 15 days ago.","question":"Assess eligibility; do not invent which conflicting lab is correct.","expected":"INSUFFICIENT","evidence":["5.8","10.2"]},
{"id":"M09","class":"sparse","record":"Age 55. Type 2 diabetes mellitus. Other protocol fields are absent.","question":"Assess the same protocol.","expected":"INSUFFICIENT","evidence":["absent"]},
{"id":"M10","class":"negative","record":"Age 72. Type 2 diabetes mellitus. Essential hypertension. No CKD. HbA1c 9.0%. Encounter 5 days ago.","question":"Assess the same protocol.","expected":"INELIGIBLE","evidence":["72"]},
]

def normalize_label(text):
 s=text.upper()
 if "INSUFFICIENT" in s or "NOT ENOUGH" in s or "CANNOT DETERMINE" in s or "UNABLE TO DETERMINE" in s:return "INSUFFICIENT"
 if "INELIGIBLE" in s or "NOT ELIGIBLE" in s:return "INELIGIBLE"
 if "ELIGIBLE" in s:return "ELIGIBLE"
 return "UNKNOWN"

def main():
 ap=argparse.ArgumentParser()
 ap.add_argument("--responses",help="JSON mapping case id to model response. Omit to generate the evaluation pack only.")
 ap.add_argument("--out",default=str(ROOT/"benchmark_results/gate4_medgemma.json"))
 args=ap.parse_args()
 pack=ROOT/"benchmark_results/gate4_medgemma_cases.json";pack.parent.mkdir(exist_ok=True)
 pack.write_text(json.dumps({"instruction":"Return one of ELIGIBLE, INELIGIBLE, INSUFFICIENT and briefly cite only record evidence. Do not infer missing facts.","cases":CASES},indent=2))
 if not args.responses:
  print("Gate 4 case pack created:",pack)
  print("No model responses supplied; evaluation status: SKIPPED")
  return
 responses=json.loads(Path(args.responses).read_text()); rows=[];t0=time.perf_counter()
 for c in CASES:
  raw=str(responses.get(c["id"],""))
  actual=normalize_label(raw)
  decision=actual==c["expected"]
  # Conservative hallucination flag: claiming a positive eligibility decision on insufficient-evidence cases.
  unsafe=(c["expected"]=="INSUFFICIENT" and actual in {"ELIGIBLE","INELIGIBLE"})
  evidence_hit=any(x.lower() in raw.lower() for x in c["evidence"])
  rows.append({"id":c["id"],"class":c["class"],"expected":c["expected"],"actual":actual,"decision_pass":decision,
               "evidence_grounded":evidence_hit,"unsafe_forced_decision":unsafe,"response":raw})
 passed=sum(r["decision_pass"] for r in rows); unsafe=sum(r["unsafe_forced_decision"] for r in rows)
 grounded=sum(r["evidence_grounded"] for r in rows)
 out={"gate":"Gate 4 MedGemma labelled evaluation","passed":passed,"total":len(rows),"decision_accuracy":round(passed/len(rows),4),
      "evidence_grounding_rate":round(grounded/len(rows),4),"unsafe_forced_decisions":unsafe,
      "pass":passed==len(rows) and unsafe==0,"seconds":round(time.perf_counter()-t0,3),"cases":rows}
 Path(args.out).write_text(json.dumps(out,indent=2))
 print("\n=== GATE 4 — MEDGEMMA LABELLED EVALUATION ===")
 print(f"Decision agreement: {passed}/{len(rows)} ({100*passed/len(rows):.1f}%)")
 print(f"Evidence grounding: {grounded}/{len(rows)} ({100*grounded/len(rows):.1f}%)")
 print("Unsafe forced decisions on insufficient cases:",unsafe)
 for r in rows:
  if not r["decision_pass"] or r["unsafe_forced_decision"]:
   print("FAIL",r["id"],"expected=",r["expected"],"actual=",r["actual"],"unsafe=",r["unsafe_forced_decision"])
 print("Overall:","PASS" if out["pass"] else "FAIL")
 raise SystemExit(0 if out["pass"] else 2)
if __name__=="__main__":main()
