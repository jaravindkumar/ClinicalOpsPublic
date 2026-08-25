#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, time
from pathlib import Path
import duckdb
import pandas as pd

ANCHOR = pd.Timestamp("2026-08-07")

EXPECTED = {
 "UK-AGE-BELOW": {"age":49, "base":False},
 "UK-AGE-LOW": {"age":50, "base":True},
 "UK-AGE-HIGH": {"age":70, "base":True},
 "UK-AGE-ABOVE": {"age":71, "base":False},
 "UK-DX-CKD": {"base":False, "must_have":"Chronic kidney disease"},
 "UK-DX-MISSING-HTN": {"base":False, "must_not_have":"Essential hypertension"},
 "UK-OBS-BELOW": {"hba1c":7.49, "hba":False},
 "UK-OBS-THRESHOLD": {"hba1c":7.50, "hba":True},
 "UK-OBS-ABOVE": {"hba1c":7.51, "hba":True},
 "UK-TIME-90": {"encounter_days":90},
 "UK-TIME-91": {"encounter_days":91},
 "UK-DATA-DUP": {"no_crash":True},
 "UK-DATA-SPARSE": {"no_crash":True},
 "UK-DATA-DENSE": {"no_crash":True},
 "UK-DATA-MISSING-SEX": {"missing_sex":True},
 "UK-DATA-CONFLICT": {"conflicting_hba1c":True},
}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--data",required=True)
    ap.add_argument("--out",required=True)
    a=ap.parse_args(); root=Path(a.data); t0=time.perf_counter()
    con=duckdb.connect()
    def q(name): return str(root/name).replace("'","''")
    patients=con.execute(f"select * from read_csv_auto('{q('patients.csv')}',header=true,all_varchar=true)").df()
    cond=con.execute(f"select * from read_csv_auto('{q('conditions.csv')}',header=true,all_varchar=true)").df()
    enc=con.execute(f"select * from read_csv_auto('{q('encounters.csv')}',header=true,all_varchar=true)").df()
    obs=con.execute(f"select * from read_csv_auto('{q('observations.csv')}',header=true,all_varchar=true)").df()
    gt=con.execute(f"select * from read_csv_auto('{q('benchmark_ground_truth.csv')}',header=true,all_varchar=true)").df()
    con.close()
    rows=[]
    for scenario, exp in EXPECTED.items():
        ids=set(gt.loc[gt.scenario==scenario,"patient_id"].astype(str))
        checks=[]; details=[]
        for pid in ids:
            pr=patients[patients.Id.astype(str)==pid]
            cr=cond[cond.PATIENT.astype(str)==pid]
            er=enc[enc.PATIENT.astype(str)==pid]
            orr=obs[obs.PATIENT.astype(str)==pid]
            gr=gt[gt.patient_id.astype(str)==pid].iloc[0]
            ok=True; why=[]
            if "age" in exp:
                age=int((ANCHOR-pd.to_datetime(pr.iloc[0]["BIRTHDATE"])).days//365.2425)
                if age!=exp["age"]: ok=False; why.append(f"age={age}")
            if "base" in exp:
                val=str(gr.expected_base_cohort) in ("1","1.0","True","true")
                if val!=exp["base"]: ok=False; why.append(f"base={val}")
            if "must_have" in exp and exp["must_have"] not in set(cr.DESCRIPTION.astype(str)):
                ok=False; why.append("required diagnosis absent")
            if "must_not_have" in exp and exp["must_not_have"] in set(cr.DESCRIPTION.astype(str)):
                ok=False; why.append("excluded diagnosis present")
            if "hba1c" in exp:
                vals=pd.to_numeric(orr.loc[orr.DESCRIPTION.astype(str).str.contains("A1c",case=False,na=False),"VALUE"],errors="coerce").dropna()
                if len(vals)==0 or abs(float(vals.iloc[0])-exp["hba1c"])>.001: ok=False; why.append(f"HbA1c={vals.tolist()[:3]}")
                hv=str(gr.expected_hba1c_cohort) in ("1","1.0","True","true")
                if hv!=exp["hba"]: ok=False; why.append(f"hba_ground_truth={hv}")
            if "encounter_days" in exp:
                dates=pd.to_datetime(er["START"],errors="coerce").dropna()
                if len(dates)==0: ok=False; why.append("no encounter")
                else:
                    closest=int((ANCHOR-dates.max().normalize()).days)
                    if closest!=exp["encounter_days"]: ok=False; why.append(f"latest={closest}d")
            if exp.get("missing_sex") and len(pr) and str(pr.iloc[0].get("GENDER","")).strip() not in ("","nan","None"):
                ok=False; why.append("sex not missing")
            if exp.get("conflicting_hba1c"):
                vals=set(pd.to_numeric(orr.loc[orr.DESCRIPTION.astype(str).str.contains("A1c",case=False,na=False),"VALUE"],errors="coerce").dropna().round(2))
                if not ({5.8,10.2} <= vals): ok=False; why.append(f"values={sorted(vals)}")
            checks.append(ok)
            if why: details.append({"patient_id":pid,"issues":why})
        rows.append({"scenario":scenario,"patients":len(ids),"pass":bool(ids) and all(checks),
                     "failed_patients":sum(not x for x in checks),"details":details[:10]})
    out={"gate":"Gate 2 deterministic edge cases","pass":all(r["pass"] for r in rows),
         "passed":sum(r["pass"] for r in rows),"total":len(rows),"seconds":round(time.perf_counter()-t0,3),"scenarios":rows}
    Path(a.out).parent.mkdir(parents=True,exist_ok=True); Path(a.out).write_text(json.dumps(out,indent=2))
    print("\n=== GATE 2 — DETERMINISTIC EDGE CASES ===")
    for r in rows: print(f"{'PASS' if r['pass'] else 'FAIL':4}  {r['scenario']:<24} n={r['patients']} failed={r['failed_patients']}")
    print(f"\n{out['passed']} / {out['total']} PASS")
    raise SystemExit(0 if out["pass"] else 2)
if __name__=="__main__": main()
