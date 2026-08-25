#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, subprocess, sys, time, csv
from pathlib import Path
import pandas as pd
import duckdb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.cohort_engine import filter_population
from src.copilot import parse_cohort_request
from src.trial_ops import build_trial, get_study_summary, get_site_scores

ANCHOR = "2026-08-07"

COPILOT_CASES = [
    ("Adults age 50-70 with diabetes and hypertension excluding CKD", (50,70), {"diabetes","hypertension"}, {"chronic kidney disease"}),
    ("Patients aged between 50 and 70 with T2DM and high blood pressure without chronic kidney disease", (50,70), {"diabetes","hypertension"}, {"chronic kidney disease"}),
    ("Find diabetic hypertensive patients 50 to 70, exclude renal disease", (50,70), {"diabetes","hypertension"}, {"chronic kidney disease"}),
    ("Age 50-70, type 2 diabetes AND hypertension, excluding CKD", (50,70), {"diabetes","hypertension"}, {"chronic kidney disease"}),
]

def run(cmd):
    t=time.perf_counter()
    p=subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    return p, round(time.perf_counter()-t,3)

def deterministic_app_test(data_dir: Path):
    t=time.perf_counter()
    df=filter_population(
        str(data_dir), 50, 70, "Any", "", "", 0,
        include_conditions=["Type 2 diabetes mellitus","Essential hypertension"],
        exclude_conditions=["Chronic kidney disease"],
        include_logic="AND", exclude_logic="OR"
    )
    sec=round(time.perf_counter()-t,3)
    con=duckdb.connect()
    g=str(data_dir/"benchmark_ground_truth.csv").replace("'","''")
    truth=con.execute(f"SELECT patient_id FROM read_csv_auto('{g}',header=true,all_varchar=true) WHERE expected_base_cohort='1'").df()
    con.close()
    A=set(df.patient_id.astype(str)); T=set(truth.patient_id.astype(str))
    tp=len(A&T); fp=len(A-T); fn=len(T-A)
    return {
        "expected":len(T),"actual":len(A),"tp":tp,"fp":fp,"fn":fn,
        "precision": tp/len(A) if A else (1.0 if not T else 0.0),
        "recall": tp/len(T) if T else (1.0 if not A else 0.0),
        "seconds":sec,"pass":fp==0 and fn==0
    }

def copilot_test():
    rows=[]
    for prompt, age, inc, exc in COPILOT_CASES:
        d=parse_cohort_request(prompt)
        got_age=tuple(d.get("age",(0,120)))
        got_inc=set(d.get("include_keywords",[]))
        got_exc=set(d.get("exclude_keywords",[]))
        ok=(got_age==age and inc.issubset(got_inc) and exc.issubset(got_exc) and d.get("include_logic")=="AND")
        rows.append({"prompt":prompt,"pass":ok,"age":list(got_age),"include":sorted(got_inc),"exclude":sorted(got_exc)})
    return {"pass":all(x["pass"] for x in rows),"passed":sum(x["pass"] for x in rows),"total":len(rows),"cases":rows}

def medgemma_test(data_dir: Path, n: int, model: str):
    if n <= 0:
        return {"status":"skipped","reason":"sample size 0"}
    import requests
    try:
        requests.get("http://localhost:11434/api/tags", timeout=3).raise_for_status()
    except Exception as e:
        return {"status":"skipped","reason":f"Ollama unavailable: {e}"}
    from src.synthea_patient import build_patient_clinical_text
    from src.medgemma_client import extract
    sample=filter_population(str(data_dir),50,70,"Any","","",0,limit=n)
    rows=[]; t0=time.perf_counter()
    for pid in sample.patient_id.astype(str):
        t=time.perf_counter()
        try:
            clinical,_=build_patient_clinical_text(pid,str(data_dir))
            out=extract(clinical,model=model)
            rows.append({"patient_id":pid,"status":"pass","seconds":round(time.perf_counter()-t,2),
                         "priority":out.priority,"open_loop":bool(out.open_loop)})
        except Exception as e:
            rows.append({"patient_id":pid,"status":"fail","seconds":round(time.perf_counter()-t,2),"error":str(e)})
    return {"status":"complete","n":len(rows),"passed":sum(r["status"]=="pass" for r in rows),
            "failed":sum(r["status"]=="fail" for r in rows),"seconds":round(time.perf_counter()-t0,2),"cases":rows}

def trial_test(data_dir: Path, target: int, out_dir: Path):
    db=out_dir/"trial_ops_benchmark.duckdb"
    t=time.perf_counter()
    try:
        build_trial(str(data_dir), db_path=str(db), target_enrollment=target, force=True)
        summary=get_study_summary(db_path=str(db))
        sites=get_site_scores(db_path=str(db))
        countries=set(sites["country"].dropna().astype(str)) if len(sites) and "country" in sites.columns else set()
        return {"pass": countries <= {"United Kingdom"}, "seconds":round(time.perf_counter()-t,3),
                "study_summary":summary,"sites":len(sites),"countries":sorted(countries)}
    except Exception as e:
        return {"pass":False,"seconds":round(time.perf_counter()-t,3),"error":str(e)}

def main():
    ap=argparse.ArgumentParser(description="Automate the UK ClinicalOps benchmark workflow.")
    ap.add_argument("--patients",type=int,default=1000)
    ap.add_argument("--data-dir",default="")
    ap.add_argument("--results-dir",default="")
    ap.add_argument("--edge-rate",type=float,default=.05)
    ap.add_argument("--medgemma-sample",type=int,default=0)
    ap.add_argument("--model",default="hf.co/YADAV0206/medgemma-4b-it-Q4_K_M-GGUF:Q4_K_M")
    ap.add_argument("--trial-target",type=int,default=100)
    args=ap.parse_args()

    data_dir=Path(args.data_dir or (ROOT/"benchmark_data"/f"uk_{args.patients//1000}k" if args.patients>=1000 else ROOT/"benchmark_data"/f"uk_{args.patients}"))
    results_dir=Path(args.results_dir or ROOT/"benchmark_results"/f"uk_{args.patients}")
    results_dir.mkdir(parents=True,exist_ok=True)

    report={"patients":args.patients,"data_dir":str(data_dir),"started_at":time.strftime("%Y-%m-%d %H:%M:%S"),"stages":{}}

    if not (data_dir/"patients.csv").exists():
        p,sec=run([sys.executable,"scripts/generate_uk_benchmark.py","--patients",str(args.patients),"--out",str(data_dir),"--edge-rate",str(args.edge_rate)])
        report["stages"]["generate"]={"pass":p.returncode==0,"seconds":sec,"stdout":p.stdout[-4000:],"stderr":p.stderr[-4000:]}
        if p.returncode:
            (results_dir/"automation_report.json").write_text(json.dumps(report,indent=2,default=str)); print(json.dumps(report,indent=2)); raise SystemExit(p.returncode)
    else:
        report["stages"]["generate"]={"pass":True,"seconds":0,"status":"reused existing dataset"}

    p,sec=run([sys.executable,"scripts/run_uk_benchmark.py","--data",str(data_dir),"--out",str(results_dir/"ground_truth_benchmark.json")])
    report["stages"]["ground_truth_runner"]={"pass":p.returncode==0,"seconds":sec,"stdout":p.stdout[-4000:],"stderr":p.stderr[-4000:]}

    report["stages"]["clinicalops_cohort_engine"]=deterministic_app_test(data_dir)

    controlled_dir = results_dir/"controlled_fixtures"
    pg, sg = run([sys.executable,"scripts/generate_controlled_fixtures.py","--out",str(controlled_dir)])
    gate2_out = results_dir/"gate2_controlled.json"
    p2, sec2 = run([sys.executable,"scripts/run_gate2_controlled.py","--data",str(controlled_dir),"--out",str(gate2_out)])
    gate2_data = json.loads(gate2_out.read_text()) if gate2_out.exists() else {}
    report["stages"]["gate2_controlled"] = {
        "pass": pg.returncode == 0 and p2.returncode == 0 and bool(gate2_data.get("pass")),
        "seconds": round(sg+sec2,3),
        "fixture_integrity_pass": gate2_data.get("fixture_integrity_pass"),
        "base_cohort": gate2_data.get("base_cohort"),
        "hba1c_threshold": gate2_data.get("hba1c_threshold"),
        "recency_90d": gate2_data.get("recency_90d"),
        "stdout": (pg.stdout+p2.stdout)[-8000:], "stderr": (pg.stderr+p2.stderr)[-4000:]
    }

    report["stages"]["copilot_parser"]=copilot_test()
    p3, sec3 = run([sys.executable,"scripts/run_gate3_language.py"])
    g3p = ROOT/"benchmark_results"/"gate3_language.json"
    g3 = json.loads(g3p.read_text()) if g3p.exists() else {}
    report["stages"]["gate3_language"] = {
        "pass": p3.returncode == 0 and bool(g3.get("pass")),
        "seconds": sec3, "passed": g3.get("passed"), "total": g3.get("total"),
        "accuracy": g3.get("accuracy"), "stdout": p3.stdout[-8000:], "stderr": p3.stderr[-4000:]
    }
    p3b, sec3b = run([sys.executable,"scripts/run_gate3b_safety.py"])
    g3bp = ROOT/"benchmark_results"/"gate3b_safety.json"
    g3b = json.loads(g3bp.read_text()) if g3bp.exists() else {}
    report["stages"]["gate3b_safety"] = {
        "pass": p3b.returncode == 0 and bool(g3b.get("pass")),
        "seconds": sec3b, "passed": g3b.get("passed"), "total": g3b.get("total"),
        "accuracy": g3b.get("accuracy"), "stdout": p3b.stdout[-8000:], "stderr": p3b.stderr[-4000:]
    }
    p3c, sec3c = run([sys.executable,"scripts/run_gate3c_e2e.py"])
    g3cp = ROOT/"benchmark_results"/"gate3c_e2e.json"
    g3c = json.loads(g3cp.read_text()) if g3cp.exists() else {}
    report["stages"]["gate3c_e2e"] = {
        "pass": p3c.returncode == 0 and bool(g3c.get("pass")),
        "seconds": sec3c, "passed": g3c.get("passed"), "total": g3c.get("total"),
        "exact_match_rate": g3c.get("exact_match_rate"), "equivalence_consistency": g3c.get("equivalence_consistency"),
        "stdout": p3c.stdout[-8000:], "stderr": p3c.stderr[-4000:]
    }
    report["stages"]["trial_operations"]=trial_test(data_dir,min(args.trial_target,args.patients),results_dir)
    report["stages"]["medgemma"]=medgemma_test(data_dir,args.medgemma_sample,args.model)

    critical=["ground_truth_runner","clinicalops_cohort_engine","gate2_controlled","copilot_parser","gate3_language","gate3b_safety","gate3c_e2e","trial_operations"]
    report["overall_pass"]=all(bool(report["stages"].get(k,{}).get("pass")) for k in critical)
    report["completed_at"]=time.strftime("%Y-%m-%d %H:%M:%S")
    (results_dir/"automation_report.json").write_text(json.dumps(report,indent=2,default=str),encoding="utf-8")

    flat=[]
    for stage,v in report["stages"].items():
        status = "SKIPPED" if v.get("status") == "skipped" else ("PASS" if v.get("pass", v.get("status")=="complete") else "FAIL")
        flat.append({"stage":stage,"status":status,"pass": status=="PASS","seconds":v.get("seconds",""),
                     "detail":v.get("error") or v.get("reason") or f"{v.get('actual','')} / {v.get('expected','')}"})
    pd.DataFrame(flat).to_csv(results_dir/"scorecard.csv",index=False)

    print("\n=== CLINICALOPS UK AUTOMATED BENCHMARK ===")
    for r in flat:
        print(f"{r.get('status', 'PASS' if r['pass'] else 'FAIL'):<7} {r['stage']:<28} {r['seconds']}")
    print(f"\nOverall: {'PASS' if report['overall_pass'] else 'FAIL'}")
    print(f"Report: {results_dir/'automation_report.json'}")
    print(f"Scorecard: {results_dir/'scorecard.csv'}")

if __name__=="__main__":
    main()
