#!/usr/bin/env python3
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.live_study import init_live_study,advance,snapshot,recruitment_trajectory,intervene

checks=[]
def ck(name,ok):
 checks.append((name,bool(ok)));print(("PASS" if ok else "FAIL"),name)

init_live_study(force=True)
advance(3)
w,p,s,a,e=snapshot();t=recruitment_trajectory()
ck("week 4 reached",w==4)
ck("normal sites not falsely slow at week 4",not (a.label=="SLOW_RECRUITMENT").any())
ck("explicit expected recruitment",(t.expected_enrolled>0).all())
ck("background recruitment present",(t.actual_enrolled>0).all())
ck("normal recruitment velocity near plan",(t.velocity_ratio>=.60).all())

advance(1)
w,p,s,a,e=snapshot();t=recruitment_trajectory()
lon=t[t.site_id=="UK-LON-02"].iloc[0]
ck("week 5 reached",w==5)
ck("London North HIGH_DNA emerges",((a.site_id=="UK-LON-02")&(a.label=="HIGH_DNA")).any())
ck("cumulative attainment still buffered",lon.attainment>=.70)
ck("London North velocity collapses",lon.velocity_ratio<.60)
ck("velocity detects slow recruitment",((a.site_id=="UK-LON-02")&(a.label=="SLOW_RECRUITMENT")).any())
ck("other sites not falsely slow",not ((a.site_id!="UK-LON-02")&(a.label=="SLOW_RECRUITMENT")).any())

intervene("UK-LON-02","Patient reminder workflow + site huddle");advance(1)
w,p,s,a,e=snapshot();t=recruitment_trajectory()
lon=t[t.site_id=="UK-LON-02"].iloc[0]
ck("week 6 reached",w==6)
ck("recruitment velocity restored",lon.velocity_ratio>=.60)
ck("HIGH_DNA recovers",not ((a.site_id=="UK-LON-02")&(a.label=="HIGH_DNA")).any())
ck("SLOW_RECRUITMENT recovers",not ((a.site_id=="UK-LON-02")&(a.label=="SLOW_RECRUITMENT")).any())
ck("no recruitment alert storm",not (a.label=="SLOW_RECRUITMENT").any())

ok=all(v for _,v in checks)
print("\n=== GATE 8C — RECRUITMENT VELOCITY + TRAJECTORY ===")
print(f"Passed: {sum(v for _,v in checks)}/{len(checks)}")
print("Overall:","PASS" if ok else "FAIL")
raise SystemExit(0 if ok else 2)
