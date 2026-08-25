#!/usr/bin/env python3
"""Run deterministic correctness and scale checks against a generated UK benchmark."""
import argparse, json, time
from pathlib import Path
import duckdb

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--data",default="benchmark_data/uk_300k"); ap.add_argument("--out",default="benchmark_results/uk_benchmark.json"); args=ap.parse_args()
    root=Path(args.data); out=Path(args.out); out.parent.mkdir(parents=True,exist_ok=True); con=duckdb.connect()
    p=str(root/"patients.csv").replace("'","''"); c=str(root/"conditions.csv").replace("'","''"); o=str(root/"observations.csv").replace("'","''"); g=str(root/"benchmark_ground_truth.csv").replace("'","''")
    age="date_diff('year', try_cast(BIRTHDATE as date), DATE '2026-08-07') - CASE WHEN (month(DATE '2026-08-07'),day(DATE '2026-08-07')) < (month(try_cast(BIRTHDATE as date)),day(try_cast(BIRTHDATE as date))) THEN 1 ELSE 0 END"
    sql=f'''SELECT cast(Id as varchar) patient_id FROM read_csv_auto('{p}',header=true,all_varchar=true) p WHERE {age} BETWEEN 50 AND 70 AND EXISTS (SELECT 1 FROM read_csv_auto('{c}',header=true,all_varchar=true) x WHERE x.PATIENT=p.Id AND lower(x.DESCRIPTION)='type 2 diabetes mellitus') AND EXISTS (SELECT 1 FROM read_csv_auto('{c}',header=true,all_varchar=true) x WHERE x.PATIENT=p.Id AND lower(x.DESCRIPTION)='essential hypertension') AND NOT EXISTS (SELECT 1 FROM read_csv_auto('{c}',header=true,all_varchar=true) x WHERE x.PATIENT=p.Id AND lower(x.DESCRIPTION)='chronic kidney disease')'''
    t=time.perf_counter(); actual=con.execute(sql).df(); cohort_s=time.perf_counter()-t
    truth=con.execute(f"SELECT patient_id FROM read_csv_auto('{g}',header=true,all_varchar=true) WHERE expected_base_cohort='1'").df()
    A=set(actual.patient_id); T=set(truth.patient_id); tp=len(A&T); fp=len(A-T); fn=len(T-A); precision=tp/len(A) if A else 1; recall=tp/len(T) if T else 1
    counts={}
    for fnm in ["patients.csv","conditions.csv","encounters.csv","observations.csv","medications.csv"]:
        q=str(root/fnm).replace("'","''"); t=time.perf_counter(); n=con.execute(f"SELECT count(*) FROM read_csv_auto('{q}',header=true,all_varchar=true)").fetchone()[0]; counts[fnm]={"rows":n,"scan_seconds":round(time.perf_counter()-t,3)}
    injected=con.execute(f"SELECT scenario,count(*) n FROM read_csv_auto('{g}',header=true,all_varchar=true) WHERE injected='1' GROUP BY 1 ORDER BY 1").df().to_dict('records')
    result={"data":str(root),"counts":counts,"cohort_test":{"definition":"age 50-70 AND T2DM AND hypertension EXCLUDE CKD","expected":len(T),"actual":len(A),"tp":tp,"fp":fp,"fn":fn,"precision":precision,"recall":recall,"pass":fp==0 and fn==0,"seconds":round(cohort_s,3)},"edge_scenarios":injected}
    out.write_text(json.dumps(result,indent=2),encoding="utf-8"); print(json.dumps(result,indent=2)); con.close()
if __name__=="__main__": main()
