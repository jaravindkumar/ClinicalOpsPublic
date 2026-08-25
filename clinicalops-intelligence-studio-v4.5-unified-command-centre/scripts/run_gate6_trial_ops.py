#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import argparse,csv,json,random,sys,time
from datetime import date,timedelta
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))

SITES=[
 ("UK-LON-01","London Central","London",120),
 ("UK-LON-02","London North","London",95),
 ("UK-MAN-01","Manchester","Manchester",90),
 ("UK-BHM-01","Birmingham","Birmingham",80),
 ("UK-LDS-01","Leeds","Leeds",75),
 ("UK-BRS-01","Bristol","Bristol",70),
]
ANCHOR=date(2026,8,7)

def load_ids(data):
 import pandas as pd
 from src.cohort_engine import filter_population
 df=filter_population(str(data),50,70,"Any","","",0,
   include_conditions=["Type 2 diabetes mellitus","Essential hypertension"],
   exclude_conditions=["Chronic kidney disease"],include_logic="AND",exclude_logic="OR",
   observation_description="Hemoglobin A1c/Hemoglobin.total in Blood",observation_operator=">=",observation_value=7.5,
   recent_days=90,as_of_date=str(ANCHOR))
 return df.patient_id.astype(str).tolist()

def site_metrics(rows):
 out={}
 for sid,name,city,cap in SITES:
  rr=[r for r in rows if r["site_id"]==sid]
  n=len(rr); screened=sum(r["screened"] for r in rr); eligible=sum(r["eligible"] for r in rr)
  booked=sum(r["booked"] for r in rr); attended=sum(r["attended"] for r in rr); enrolled=sum(r["enrolled"] for r in rr)
  overdue=sum(r["followup_overdue"] for r in rr); unresolved=sum(r["unresolved_review"] for r in rr)
  dq=sum(r["data_quality_issue"] for r in rr)
  out[sid]={"site_name":name,"city":city,"capacity":cap,"patients":n,"screened":screened,"eligible":eligible,
            "booked":booked,"attended":attended,"enrolled":enrolled,
            "screen_failure_rate":round((screened-eligible)/screened,4) if screened else 0,
            "dna_rate":round((booked-attended)/booked,4) if booked else 0,
            "overdue_followups":overdue,"unresolved_reviews":unresolved,"data_quality_issues":dq,
            "capacity_utilisation":round(enrolled/cap,4) if cap else 0}
 return out

def classify(m):
 flags=[]
 if m["screen_failure_rate"]>=0.35: flags.append("HIGH_SCREEN_FAILURE")
 if m["dna_rate"]>=0.25: flags.append("HIGH_DNA")
 if m["overdue_followups"]>=8: flags.append("OVERDUE_FOLLOWUP")
 if m["unresolved_reviews"]>=6: flags.append("UNRESOLVED_CLINICAL_REVIEW")
 if m["data_quality_issues"]>=6: flags.append("DATA_QUALITY")
 if m["capacity_utilisation"]>=0.95: flags.append("CAPACITY_CONSTRAINT")
 if m["patients"]>=25 and m["enrolled"]<8: flags.append("SLOW_RECRUITMENT")
 return sorted(flags)

def main():
 ap=argparse.ArgumentParser()
 ap.add_argument("--data",default=str(ROOT/"benchmark_data/uk_scale_10000"))
 ap.add_argument("--patients",type=int,default=360)
 ap.add_argument("--seed",type=int,default=20260807)
 args=ap.parse_args(); data=Path(args.data)
 if not (data/"patients.csv").exists():
  print("Gate 6 data missing:",data)
  print("Generate it first with: python scripts/run_gate5_scale.py --sizes 10000")
  raise SystemExit(3)
 ids=load_ids(data)
 if not ids:
  print("No protocol-eligible source patients found.");raise SystemExit(3)
 r=random.Random(args.seed); ids=(ids*((args.patients//len(ids))+1))[:args.patients]
 rows=[]
 # Known injected site-level operational problems.
 injected={
  "UK-LON-01":["CAPACITY_CONSTRAINT"],
  "UK-LON-02":["HIGH_DNA"],
  "UK-MAN-01":["SLOW_RECRUITMENT"],
  "UK-BHM-01":["HIGH_SCREEN_FAILURE"],
  "UK-LDS-01":["OVERDUE_FOLLOWUP"],
  "UK-BRS-01":["UNRESOLVED_CLINICAL_REVIEW","DATA_QUALITY"],
 }
 for i,pid in enumerate(ids):
  sid,name,city,cap=SITES[i%len(SITES)]
  screened=1
  eligible=1
  booked=1 if r.random()<.88 else 0
  attended=1 if booked and r.random()<.90 else 0
  enrolled=1 if attended and r.random()<.88 else 0
  overdue=1 if enrolled and r.random()<.06 else 0
  unresolved=1 if r.random()<.03 else 0
  dq=1 if r.random()<.025 else 0
  # Controlled injections.
  if sid=="UK-LON-01":
   booked=1; attended=1; enrolled=1
  elif sid=="UK-LON-02":
   booked=1
   if i%3==1: attended=0; enrolled=0
  elif sid=="UK-MAN-01":
   if i%3!=2: enrolled=0
  elif sid=="UK-BHM-01":
   if i%2==3%2: eligible=0; booked=attended=enrolled=0
  elif sid=="UK-LDS-01":
   if enrolled and i%3!=0: overdue=1
  elif sid=="UK-BRS-01":
   if i%4 in (0,1): unresolved=1
   if i%4 in (2,3): dq=1
  rows.append({"patient_id":pid,"site_id":sid,"screened":screened,"eligible":eligible,"booked":booked,
               "attended":attended,"enrolled":enrolled,"followup_overdue":overdue,
               "unresolved_review":unresolved,"data_quality_issue":dq})
 metrics=site_metrics(rows)
 detected={sid:classify(m) for sid,m in metrics.items()}
 # Exact ground truth for injected risk labels; non-injected incidental risks are treated as FP.
 tp=fp=fn=0; details={}
 for sid in injected:
  exp=set(injected[sid]); act=set(detected[sid])
  tp+=len(exp&act);fp+=len(act-exp);fn+=len(exp-act)
  details[sid]={"expected":sorted(exp),"actual":sorted(act),"tp":sorted(exp&act),"fp":sorted(act-exp),"fn":sorted(exp-act),
                "metrics":metrics[sid],"pass":exp==act}
 precision=tp/(tp+fp) if tp+fp else 1.0;recall=tp/(tp+fn) if tp+fn else 1.0
 overall=(fp==0 and fn==0)
 outdir=ROOT/"benchmark_results/gate6_trial_ops";outdir.mkdir(parents=True,exist_ok=True)
 with (outdir/"patient_operations.csv").open("w",newline="") as f:
  w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
 report={"gate":"Gate 6 UK multi-site clinical operations simulation","anchor_date":str(ANCHOR),
         "patients":len(rows),"sites":len(SITES),"injected_ground_truth":injected,"detected":detected,
         "tp":tp,"fp":fp,"fn":fn,"precision":round(precision,4),"recall":round(recall,4),
         "pass":overall,"sites_detail":details}
 (outdir/"gate6_report.json").write_text(json.dumps(report,indent=2))
 print("\n=== GATE 6 — UK MULTI-SITE TRIAL OPERATIONS ===")
 print(f"Patients: {len(rows)}  Sites: {len(SITES)}")
 for sid,name,city,cap in SITES:
  d=details[sid];m=metrics[sid]
  print(("PASS" if d["pass"] else "FAIL"),sid,name,
        f"enrolled={m['enrolled']} dna={m['dna_rate']:.1%} screenfail={m['screen_failure_rate']:.1%}",
        "expected="+",".join(d["expected"]),"detected="+",".join(d["actual"]))
 print(f"\nRisk detection: TP={tp} FP={fp} FN={fn} precision={precision:.3f} recall={recall:.3f}")
 print("Overall:","PASS" if overall else "FAIL")
 print("Report:",outdir/"gate6_report.json")
 raise SystemExit(0 if overall else 2)
if __name__=="__main__":main()
