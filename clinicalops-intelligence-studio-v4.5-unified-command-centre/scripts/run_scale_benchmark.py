#!/usr/bin/env python3
import argparse, subprocess, sys, json, time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--sizes",nargs="+",type=int,default=[1000,10000,50000,100000,300000])
    ap.add_argument("--medgemma-sample",type=int,default=0)
    args=ap.parse_args()
    summary=[]
    for n in args.sizes:
        print(f"\n{'='*70}\nRUNNING UK BENCHMARK: {n:,} PATIENTS\n{'='*70}")
        cmd=[sys.executable,"scripts/automate_uk_workflow.py","--patients",str(n),"--medgemma-sample",str(args.medgemma_sample)]
        t=time.perf_counter(); p=subprocess.run(cmd,cwd=ROOT); sec=round(time.perf_counter()-t,2)
        report=ROOT/"benchmark_results"/f"uk_{n}"/"automation_report.json"
        row={"patients":n,"returncode":p.returncode,"seconds":sec,"report":str(report)}
        if report.exists():
            d=json.loads(report.read_text()); row["overall_pass"]=d.get("overall_pass")
            ce=d.get("stages",{}).get("clinicalops_cohort_engine",{})
            row.update({"cohort_seconds":ce.get("seconds"),"precision":ce.get("precision"),"recall":ce.get("recall")})
        summary.append(row)
        if p.returncode: break
    out=ROOT/"benchmark_results"/"scale_summary.json"; out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(summary,indent=2))
    print(f"\nScale summary: {out}")
if __name__=="__main__": main()
