#!/usr/bin/env python3
from pathlib import Path
import argparse, json, time, sys
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.cohort_engine import filter_population

ANCHOR=pd.Timestamp("2026-08-07")
def main():
 ap=argparse.ArgumentParser(); ap.add_argument("--data",required=True); ap.add_argument("--out",required=True); a=ap.parse_args()
 d=Path(a.data); t=time.perf_counter()
 gt=pd.read_csv(d/"controlled_ground_truth.csv",dtype=str).fillna("")
 pat=pd.read_csv(d/"patients.csv",dtype=str).fillna("")
 con=pd.read_csv(d/"conditions.csv",dtype=str).fillna("")
 enc=pd.read_csv(d/"encounters.csv",dtype=str).fillna("")
 obs=pd.read_csv(d/"observations.csv",dtype=str).fillna("")
 rows=[]
 # Fixture integrity checks first.
 for _,g in gt.iterrows():
  pid=str(g["patient_id"]); case=str(g["case_id"]); issues=[]
  p=pat[pat.Id==pid].iloc[0]; c=con[con.PATIENT==pid]; e=enc[enc.PATIENT==pid]; o=obs[obs.PATIENT==pid]
  age=ANCHOR.year-pd.Timestamp(p.BIRTHDATE).year-((ANCHOR.month,ANCHOR.day)<(pd.Timestamp(p.BIRTHDATE).month,pd.Timestamp(p.BIRTHDATE).day))
  expected_age={"CTRL-AGE-49":49,"CTRL-AGE-50":50,"CTRL-AGE-70":70,"CTRL-AGE-71":71}.get(case)
  if expected_age is not None and age!=expected_age: issues.append(f"age {age} != {expected_age}")
  if case.startswith("CTRL-HBA1C"):
   wanted=float(case.split("-")[-1]); vals=pd.to_numeric(o[o.DESCRIPTION.str.contains("A1c",case=False)]["VALUE"],errors="coerce")
   if len(vals)!=1 or abs(float(vals.iloc[0])-wanted)>.001: issues.append(f"HbA1c {vals.tolist()} != {wanted}")
  if case.startswith("CTRL-TIME"):
   wanted=int(case.split("-")[-1]); days=(ANCHOR-pd.to_datetime(e.START).max().normalize()).days
   if days!=wanted: issues.append(f"recency {days} != {wanted}")
  if case=="CTRL-CKD" and "Chronic kidney disease" not in set(c.DESCRIPTION): issues.append("CKD missing")
  if case=="CTRL-NO-CKD" and "Chronic kidney disease" in set(c.DESCRIPTION): issues.append("unexpected CKD")
  if case=="CTRL-DIAB-ONLY" and "Essential hypertension" in set(c.DESCRIPTION): issues.append("unexpected HTN")
  if case=="CTRL-DUPLICATE" and (c.DESCRIPTION=="Essential hypertension").sum()!=2: issues.append("duplicate HTN not exactly 2")
  if case=="CTRL-SPARSE" and len(o)!=1: issues.append(f"sparse observations={len(o)}")
  if case=="CTRL-DENSE" and len(o)!=250: issues.append(f"dense observations={len(o)}")
  if case=="CTRL-MISSING-SEX" and str(p.GENDER).strip()!="": issues.append("sex not missing")
  if case=="CTRL-CONFLICT":
   vals=set(pd.to_numeric(o[o.DESCRIPTION.str.contains("A1c",case=False)]["VALUE"],errors="coerce").dropna().round(2))
   if not ({7.5,10.2}<=vals): issues.append(f"conflict values={vals}")
  rows.append({"case_id":case,"fixture_pass":not issues,"fixture_issues":issues})
 # ClinicalOps base cohort exact ID comparison on controlled fixtures.
 actual=filter_population(str(d),50,70,"Any","","",0,include_conditions=["Type 2 diabetes mellitus","Essential hypertension"],exclude_conditions=["Chronic kidney disease"],include_logic="AND",exclude_logic="OR")
 A=set(actual.patient_id.astype(str)); T=set(gt.loc[gt.expected_base=="1","patient_id"])
 base={"expected":len(T),"actual":len(A),"fp":len(A-T),"fn":len(T-A),"pass":A==T}
 # Numeric threshold using actual ClinicalOps engine.
 hba=filter_population(str(d),50,70,"Any","","",0,include_conditions=["Type 2 diabetes mellitus","Essential hypertension"],exclude_conditions=["Chronic kidney disease"],include_logic="AND",exclude_logic="OR",observation_description="Hemoglobin A1c/Hemoglobin.total in Blood",observation_operator=">=",observation_value=7.5)
 H=set(hba.patient_id.astype(str)); HT=set(gt.loc[gt.expected_hba1c=="1","patient_id"])
 htest={"expected":len(HT),"actual":len(H),"fp":len(H-HT),"fn":len(HT-H),"pass":H==HT}
 # Recency via cohort engine's days parameter.
 rec=filter_population(str(d),50,70,"Any","","",0,include_conditions=["Type 2 diabetes mellitus","Essential hypertension"],exclude_conditions=["Chronic kidney disease"],include_logic="AND",exclude_logic="OR",recent_days=90,as_of_date="2026-08-07")
 R=set(rec.patient_id.astype(str)); RT=set(gt.loc[gt.expected_recency90=="1","patient_id"])
 rtest={"expected":len(RT),"actual":len(R),"fp":len(R-RT),"fn":len(RT-R),"pass":R==RT}
 fixture_ok=all(x["fixture_pass"] for x in rows)
 out={"gate":"Gate 2 controlled minimal pairs","fixture_integrity_pass":fixture_ok,"base_cohort":base,"hba1c_threshold":htest,"recency_90d":rtest,"cases":rows}
 out["pass"]=fixture_ok and base["pass"] and htest["pass"] and rtest["pass"]; out["seconds"]=round(time.perf_counter()-t,3)
 Path(a.out).parent.mkdir(parents=True,exist_ok=True); Path(a.out).write_text(json.dumps(out,indent=2))
 print("\n=== GATE 2 — CONTROLLED MINIMAL PAIRS ===")
 print("PASS" if fixture_ok else "FAIL"," fixture integrity")
 for n,x in [("base cohort",base),("HbA1c >= 7.5",htest),("encounter <= 90d",rtest)]:
  print(f"{'PASS' if x['pass'] else 'FAIL':4}  {n:<22} expected={x['expected']} actual={x['actual']} fp={x['fp']} fn={x['fn']}")
 print("Overall:", "PASS" if out["pass"] else "FAIL")
 raise SystemExit(0 if out["pass"] else 2)
if __name__=="__main__": main()
