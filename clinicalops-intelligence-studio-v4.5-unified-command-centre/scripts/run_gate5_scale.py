#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import argparse,csv,json,os,resource,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

def run(cmd):
 t=time.perf_counter()
 p=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True)
 return p,round(time.perf_counter()-t,3)

def file_stats(d):
 out={}
 total=0
 for p in d.glob("*.csv"):
  b=p.stat().st_size; total+=b
  out[p.name]={"bytes":b,"mb":round(b/1024/1024,2)}
 out["_total"]={"bytes":total,"mb":round(total/1024/1024,2)}
 return out

def main():
 ap=argparse.ArgumentParser()
 ap.add_argument("--sizes",default="1000,10000,50000,100000,300000")
 ap.add_argument("--edge-rate",type=float,default=.10)
 ap.add_argument("--reuse",action="store_true")
 args=ap.parse_args()
 sizes=[int(x) for x in args.sizes.split(",") if x.strip()]
 outdir=ROOT/"benchmark_results"/"gate5_scale";outdir.mkdir(parents=True,exist_ok=True)
 rows=[]

 for n in sizes:
  print(f"\n=== SCALE {n:,} PATIENTS ===",flush=True)
  data=ROOT/"benchmark_data"/f"uk_scale_{n}"
  if not (args.reuse and (data/"benchmark_ground_truth.csv").exists()):
   p,gen=run([sys.executable,"scripts/generate_uk_benchmark.py","--patients",str(n),"--out",str(data),"--edge-rate",str(args.edge_rate)])
   if p.returncode:
    rows.append({"patients":n,"pass":False,"stage":"generate","seconds":gen,"stderr":p.stderr[-4000:]});print("FAIL generate");continue
  else: gen=0.0
  print("generation:",gen,"s",flush=True)

  # Ground truth + deterministic cohort correctness.
  gt=outdir/f"ground_truth_{n}.json"
  p,bench=run([sys.executable,"scripts/run_uk_benchmark.py","--data",str(data),"--out",str(gt)])
  gd=json.loads(gt.read_text()) if gt.exists() else {}
  cohort=gd.get("cohort_test",{})
  print("cohort:",bench,"s precision=",cohort.get("precision"),"recall=",cohort.get("recall"),flush=True)

  # Production cohort engine latency, repeated to expose query scaling.
  qtimes=[]; qerr=None; actual=None
  try:
   from src.cohort_engine import filter_population
   for _ in range(3):
    t=time.perf_counter()
    df=filter_population(str(data),50,70,"Any","","",0,
      include_conditions=["Type 2 diabetes mellitus","Essential hypertension"],
      exclude_conditions=["Chronic kidney disease"],include_logic="AND",exclude_logic="OR")
    qtimes.append(time.perf_counter()-t);actual=len(df)
  except Exception as e:qerr=f"{type(e).__name__}: {e}"
  qmed=sorted(qtimes)[len(qtimes)//2] if qtimes else None
  print("cohort query median:",round(qmed,3) if qmed is not None else None,"s",flush=True)

  # Trial operations: build on the selected cohort, not entire population.
  trialdb=outdir/f"trial_{n}.duckdb"
  trial_sec=None;trial_err=None
  try:
   from src.trial_ops import build_trial
   ids=df.patient_id.astype(str).tolist() if qerr is None else []
   t=time.perf_counter()
   build_trial(synthea_dir=str(data),db_path=str(trialdb),force=True,candidate_patient_ids=ids,cohort_name=f"gate5_{n}")
   trial_sec=time.perf_counter()-t
  except Exception as e:trial_err=f"{type(e).__name__}: {e}"
  print("trial ops:",round(trial_sec,3) if trial_sec is not None else None,"s",flush=True)

  expected=cohort.get("expected"); precision=cohort.get("precision");recall=cohort.get("recall")
  correctness=(precision==1.0 and recall==1.0 and (expected is None or actual==expected))
  ok=(p.returncode==0 and correctness and qerr is None and trial_err is None)
  stats=file_stats(data)
  rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
  # macOS ru_maxrss is bytes; Linux is KiB. Record raw to avoid pretending cross-platform equivalence.
  row={"patients":n,"pass":ok,"generation_seconds":gen,"benchmark_seconds":bench,
       "cohort_query_seconds_median":round(qmed,4) if qmed is not None else None,
       "cohort_query_runs":[round(x,4) for x in qtimes],"expected_cohort":expected,"actual_cohort":actual,
       "precision":precision,"recall":recall,"trial_ops_seconds":round(trial_sec,4) if trial_sec is not None else None,
       "csv_total_mb":stats["_total"]["mb"],"files":stats,"trial_db_mb":round(trialdb.stat().st_size/1024/1024,2) if trialdb.exists() else None,
       "process_maxrss_raw":rss,"query_error":qerr,"trial_error":trial_err}
  rows.append(row)
  print("RESULT:","PASS" if ok else "FAIL","CSV",row["csv_total_mb"],"MB",flush=True)

 passed=sum(bool(x.get("pass")) for x in rows)
 report={"gate":"Gate 5 deterministic scale/performance","sizes":sizes,"passed":passed,"total":len(sizes),
         "pass":passed==len(sizes),"rows":rows,
         "architecture_note":"MedGemma is intentionally excluded from population-scale execution. It operates on bounded selected batches; Gate 4 measured local model latency separately."}
 (outdir/"gate5_scale_report.json").write_text(json.dumps(report,indent=2))
 with (outdir/"gate5_scale_scorecard.csv").open("w",newline="") as f:
  fields=["patients","pass","generation_seconds","benchmark_seconds","cohort_query_seconds_median","expected_cohort","actual_cohort","precision","recall","trial_ops_seconds","csv_total_mb","trial_db_mb"]
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
  for r in rows:w.writerow({k:r.get(k) for k in fields})
 print("\n=== GATE 5 — SCALE SUMMARY ===")
 for r in rows:
  print(("PASS" if r.get("pass") else "FAIL"),f"{r['patients']:,}",f"gen={r.get('generation_seconds')}s",f"query={r.get('cohort_query_seconds_median')}s",f"trial={r.get('trial_ops_seconds')}s",f"csv={r.get('csv_total_mb')}MB")
 print(f"Overall: {'PASS' if report['pass'] else 'FAIL'} ({passed}/{len(sizes)})")
 print("Report:",outdir/"gate5_scale_report.json")
 raise SystemExit(0 if report["pass"] else 2)
if __name__=="__main__":main()
