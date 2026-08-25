#!/usr/bin/env python3
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.live_study import init_live_study,snapshot,book,mark_visit,review,enroll,advance
from datetime import date
init_live_study(force=True)
book("DEMO-0002",date(2026,8,12));mark_visit("DEMO-0002","Attended");review("DEMO-0002","Eligible");enroll("DEMO-0002");advance(5)
w,p,s,a,e=snapshot()
assert w==6 and (p.status=="Enrolled").sum()==1
init_live_study(force=True)
w,p,s,a,e=snapshot()
r=p[p.patient_id=="DEMO-0002"].iloc[0]
checks=[
 ("week reset",w==1),("enrolment reset",(p.status=="Enrolled").sum()==0),
 ("patient candidate",r.status=="Candidate"),("appointment reset",r.appointment_status=="Not booked"),
 ("review reset",r.medgemma_status=="Not reviewed" and r.clinician_decision=="Pending"),
 ("events cleared",len(e)==0)]
print("\n=== v4.1 RESET REGRESSION ===")
for n,x in checks: print("PASS" if x else "FAIL",n)
print("Overall:","PASS" if all(x for _,x in checks) else "FAIL")
raise SystemExit(0 if all(x for _,x in checks) else 2)
