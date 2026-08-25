#!/usr/bin/env python3
from pathlib import Path
import sys
from datetime import date
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from src.live_study import (
 init_live_study,snapshot,book,mark_visit,advance,intervene
)

checks=[]
def ck(name,ok):
 checks.append((name,bool(ok)))
 print(("PASS" if ok else "FAIL"),name)

init_live_study(force=True)

# Reproduce the manual product-validity failure:
# one Manchester screening visit, one DNA => raw rate 100%.
pid="DEMO-0003"
book(pid,date(2026,8,9))
mark_visit(pid,"DNA")
w,p,s,a,e=snapshot()

ck("week 1 retained", w==1)
ck("single DNA persisted",
   p.loc[p.patient_id==pid,"appointment_status"].iloc[0]=="DNA")
ck("1/1 DNA does NOT trigger HIGH_DNA",
   not ((a.site_id=="UK-MAN-01") & (a.label=="HIGH_DNA")).any())
ck("week 1 does NOT trigger SLOW_RECRUITMENT",
   not ((a.site_id=="UK-MAN-01") & (a.label=="SLOW_RECRUITMENT")).any())
ck("no sparse-data alerts at week 1", len(a)==0)

# Ensure the controlled longitudinal golden journey is still intact.
advance(4)
w,p,s,a,e=snapshot()
ck("week 5 reached",w==5)
ck("controlled London North HIGH_DNA still emerges",
   ((a.site_id=="UK-LON-02") & (a.label=="HIGH_DNA")).any())
ck("controlled downstream SLOW_RECRUITMENT still emerges",
   ((a.site_id=="UK-LON-02") & (a.label=="SLOW_RECRUITMENT")).any())

intervene("UK-LON-02","Patient reminder workflow + site huddle")
advance(1)
w,p,s,a,e=snapshot()
ck("controlled HIGH_DNA clears after intervention",
   not ((a.site_id=="UK-LON-02") & (a.label=="HIGH_DNA")).any())

ok=all(x for _,x in checks)
print("\n=== GATE 8B — SPARSE ALERT SAFETY ===")
print(f"Passed: {sum(x for _,x in checks)}/{len(checks)}")
print("Overall:","PASS" if ok else "FAIL")
raise SystemExit(0 if ok else 2)
