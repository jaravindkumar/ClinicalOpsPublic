#!/usr/bin/env python3
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.live_study import init_live_study,snapshot,book,mark_visit,review,enroll,advance,intervene
from datetime import date
def main():
 init_live_study(force=True)
 w,p,s,a,e=snapshot(); checks=[]
 def ck(n,x):checks.append((n,bool(x)));print(("PASS" if x else "FAIL"),n)
 ck("study initializes",w==1 and len(p)==60)
 pid="DEMO-0002"
 book(pid,date(2026,8,10));mark_visit(pid,"DNA")
 _,p,_,_,_=snapshot();ck("appointment DNA persisted",p.loc[p.patient_id==pid,"appointment_status"].iloc[0]=="DNA")
 book(pid,date(2026,8,12));mark_visit(pid,"Attended");review(pid,"Eligible");enroll(pid)
 _,p,_,_,_=snapshot();r=p[p.patient_id==pid].iloc[0]
 ck("clinician decision persisted",r.clinician_decision=="Eligible")
 ck("patient enrolled",r.status=="Enrolled" and r.followup_due is not None)
 advance(4);w,p,s,a,e=snapshot()
 ck("week 5 reached",w==5);ck("HIGH_DNA emerges",(a.label=="HIGH_DNA").any())
 ck("downstream slow recruitment emerges",(a.label=="SLOW_RECRUITMENT").any())
 intervene("UK-LON-02","Patient reminder workflow + site huddle");advance(1)
 w,p,s,a,e=snapshot();ck("intervention recorded",bool(s.loc[s.site_id=="UK-LON-02","intervention"].iloc[0]))
 ck("controlled risk recovers",not ((a.site_id=="UK-LON-02") & (a.label=="HIGH_DNA")).any())
 ok=all(x for _,x in checks)
 print("\n=== GATE 8 — GOLDEN JOURNEY ===")
 print(f"Passed: {sum(x for _,x in checks)}/{len(checks)}")
 print("Overall:","PASS" if ok else "FAIL")
 raise SystemExit(0 if ok else 2)
if __name__=="__main__":main()
