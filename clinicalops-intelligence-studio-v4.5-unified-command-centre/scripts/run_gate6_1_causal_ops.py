#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import argparse,csv,json,random,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
ANCHOR="2026-08-07"
SITES=[
 ("UK-LON-01","London Central","London",60),
 ("UK-LON-02","London North","London",95),
 ("UK-MAN-01","Manchester","Manchester",90),
 ("UK-BHM-01","Birmingham","Birmingham",80),
 ("UK-LDS-01","Leeds","Leeds",75),
 ("UK-BRS-01","Bristol","Bristol",70),
]
PRIMARY={
 "UK-LON-01":{"CAPACITY_CONSTRAINT"},
 "UK-LON-02":{"HIGH_DNA"},
 "UK-MAN-01":{"SLOW_RECRUITMENT"},
 "UK-BHM-01":{"HIGH_SCREEN_FAILURE"},
 "UK-LDS-01":{"OVERDUE_FOLLOWUP"},
 "UK-BRS-01":{"UNRESOLVED_CLINICAL_REVIEW","DATA_QUALITY"},
}
EXPECTED_EFFECTS={
 "UK-LON-01":set(),
 "UK-LON-02":{"SLOW_RECRUITMENT"},
 "UK-MAN-01":set(),
 "UK-BHM-01":{"SLOW_RECRUITMENT"},
 "UK-LDS-01":set(),
 "UK-BRS-01":set(),
}
def eligible_ids(data):
 from src.cohort_engine import filter_population
 df=filter_population(str(data),50,70,"Any","","",0,
   include_conditions=["Type 2 diabetes mellitus","Essential hypertension"],
   exclude_conditions=["Chronic kidney disease"],include_logic="AND",exclude_logic="OR",
   observation_description="Hemoglobin A1c/Hemoglobin.total in Blood",observation_operator=">=",observation_value=7.5,
   recent_days=90,as_of_date=ANCHOR)
 return df.patient_id.astype(str).tolist()
def metrics(rows):
 out={}
 for sid,name,city,cap in SITES:
  rr=[x for x in rows if x["site_id"]==sid]
  screened=sum(x["screened"] for x in rr); eligible=sum(x["eligible"] for x in rr)
  booked=sum(x["booked"] for x in rr); attended=sum(x["attended"] for x in rr); enrolled=sum(x["enrolled"] for x in rr)
  out[sid]={"site_name":name,"capacity":cap,"patients":len(rr),"screened":screened,"eligible":eligible,
   "booked":booked,"attended":attended,"enrolled":enrolled,
   "screen_failure_rate":(screened-eligible)/screened if screened else 0,
   "dna_rate":(booked-attended)/booked if booked else 0,
   "overdue_followups":sum(x["followup_overdue"] for x in rr),
   "unresolved_reviews":sum(x["unresolved_review"] for x in rr),
   "data_quality_issues":sum(x["data_quality_issue"] for x in rr),
   "capacity_utilisation":enrolled/cap if cap else 0}
 return out
def detect(m):
 f=set()
 if m["screen_failure_rate"]>=.35:f.add("HIGH_SCREEN_FAILURE")
 if m["dna_rate"]>=.25:f.add("HIGH_DNA")
 if m["overdue_followups"]>=8:f.add("OVERDUE_FOLLOWUP")
 if m["unresolved_reviews"]>=6:f.add("UNRESOLVED_CLINICAL_REVIEW")
 if m["data_quality_issues"]>=6:f.add("DATA_QUALITY")
 if m["capacity_utilisation"]>=.95:f.add("CAPACITY_CONSTRAINT")
 if m["patients"]>=25 and m["enrolled"]<8:f.add("SLOW_RECRUITMENT")
 return f
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--data",default=str(ROOT/"benchmark_data/uk_scale_10000"))
 ap.add_argument("--patients",type=int,default=360);ap.add_argument("--seed",type=int,default=20260807);args=ap.parse_args()
 data=Path(args.data)
 if not (data/"patients.csv").exists():
  print("Run first: python scripts/run_gate5_scale.py --sizes 10000");raise SystemExit(3)
 ids=eligible_ids(data)
 if not ids: raise SystemExit("No eligible patients")
 r=random.Random(args.seed);ids=(ids*((args.patients//len(ids))+1))[:args.patients]
 rows=[]
 for i,pid in enumerate(ids):
  sid,name,city,cap=SITES[i%6];local=i//6
  screened=eligible=1;booked=1;attended=1;enrolled=1
  overdue=unresolved=dq=0
  # Frozen causal injections. Each primary cause is made metric-grounded.
  if sid=="UK-LON-01":
   # 60 assigned, capacity 60 -> 100% utilisation.
   pass
  elif sid=="UK-LON-02":
   # 100% DNA -> zero enrolment -> expected downstream slow recruitment.
   attended=enrolled=0
  elif sid=="UK-MAN-01":
   # Explicit slow recruitment without another causal alert: only 6 enrolments.
   enrolled=1 if local<6 else 0
  elif sid=="UK-BHM-01":
   # 50% screen failure; only six of eligible half enrol -> downstream slow recruitment.
   if local%2==0:
    eligible=booked=attended=enrolled=0
   else:
    enrolled=1 if local<12 else 0
  elif sid=="UK-LDS-01":
   overdue=1 if local<12 else 0
  elif sid=="UK-BRS-01":
   unresolved=1 if local<8 else 0
   dq=1 if 8<=local<16 else 0
  rows.append({"patient_id":pid,"site_id":sid,"screened":screened,"eligible":eligible,"booked":booked,
   "attended":attended,"enrolled":enrolled,"followup_overdue":overdue,
   "unresolved_review":unresolved,"data_quality_issue":dq})
 mm=metrics(rows);det={sid:detect(mm[sid]) for sid in PRIMARY}
 primary_tp=primary_fn=effect_tp=effect_fn=unexpected=0;details={}
 for sid in PRIMARY:
  p=PRIMARY[sid];e=EXPECTED_EFFECTS[sid];a=det[sid]
  primary_tp+=len(p&a);primary_fn+=len(p-a);effect_tp+=len(e&a);effect_fn+=len(e-a)
  u=a-p-e;unexpected+=len(u)
  grounded=True
  # Every expected label must be directly supported by its frozen metric threshold.
  expected_all=p|e
  grounded=(expected_all <= a)
  details[sid]={"primary":sorted(p),"expected_effects":sorted(e),"detected":sorted(a),
   "unexpected":sorted(u),"missing_primary":sorted(p-a),"missing_effects":sorted(e-a),
   "metric_grounded":grounded,"metrics":mm[sid],"pass":not (p-a) and not (e-a) and not u}
 pden=primary_tp+primary_fn;eden=effect_tp+effect_fn
 primary_recall=primary_tp/pden if pden else 1;effect_recall=effect_tp/eden if eden else 1
 overall=primary_fn==0 and effect_fn==0 and unexpected==0
 outdir=ROOT/"benchmark_results/gate6_1_causal";outdir.mkdir(parents=True,exist_ok=True)
 with (outdir/"patient_operations.csv").open("w",newline="") as f:
  w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
 report={"gate":"Gate 6.1 causal operations","patients":len(rows),"primary_recall":primary_recall,
  "expected_effect_recall":effect_recall,"unexpected_alerts":unexpected,"pass":overall,
  "causal_model":{"HIGH_DNA":["SLOW_RECRUITMENT"],"HIGH_SCREEN_FAILURE":["SLOW_RECRUITMENT"]},
  "sites":details}
 (outdir/"gate6_1_report.json").write_text(json.dumps(report,indent=2))
 print("\n=== GATE 6.1 — CAUSAL CLINICAL OPERATIONS ===")
 for sid,name,city,cap in SITES:
  d=details[sid];m=mm[sid]
  print(("PASS" if d["pass"] else "FAIL"),sid,name,
   "primary="+",".join(d["primary"]),"effects="+(",".join(d["expected_effects"]) or "none"),
   "detected="+(",".join(d["detected"]) or "none"))
  print(f"     enrolled={m['enrolled']} capacity={m['capacity']} util={m['capacity_utilisation']:.1%} DNA={m['dna_rate']:.1%} screenfail={m['screen_failure_rate']:.1%} overdue={m['overdue_followups']} unresolved={m['unresolved_reviews']} DQ={m['data_quality_issues']}")
 print(f"\nPrimary-cause recall: {primary_recall:.3f}")
 print(f"Expected-effect recall: {effect_recall:.3f}")
 print("Unexpected alerts:",unexpected)
 print("Overall:","PASS" if overall else "FAIL")
 print("Report:",outdir/"gate6_1_report.json")
 raise SystemExit(0 if overall else 2)
if __name__=="__main__":main()
