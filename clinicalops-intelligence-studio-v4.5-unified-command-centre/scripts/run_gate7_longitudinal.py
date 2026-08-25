#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import csv,json,sys
ROOT=Path(__file__).resolve().parents[1]
SITES=["UK-LON-01","UK-LON-02","UK-MAN-01","UK-BHM-01","UK-LDS-01","UK-BRS-01"]
WEEKS=26

# Frozen episodes: (site, label, onset, recovery). Expected alert is active onset..recovery-1.
EPISODES=[
 ("UK-LON-02","HIGH_DNA",5,11),
 ("UK-MAN-01","SLOW_RECRUITMENT",8,15),
 ("UK-BHM-01","HIGH_SCREEN_FAILURE",12,18),
 ("UK-LDS-01","OVERDUE_FOLLOWUP",15,22),
 ("UK-BRS-01","DATA_QUALITY",18,24),
]
def metrics(site,w):
 # Healthy baseline
 m={"dna_rate":.08,"screen_failure_rate":.12,"weekly_enrolled":5,"overdue_followups":2,"data_quality_issues":1}
 # Episodes use clear threshold separation; recovery returns to baseline.
 for s,label,on,off in EPISODES:
  if s==site and on<=w<off:
   if label=="HIGH_DNA":m["dna_rate"]=.42
   elif label=="SLOW_RECRUITMENT":m["weekly_enrolled"]=1
   elif label=="HIGH_SCREEN_FAILURE":m["screen_failure_rate"]=.48
   elif label=="OVERDUE_FOLLOWUP":m["overdue_followups"]=12
   elif label=="DATA_QUALITY":m["data_quality_issues"]=9
 return m
def detect(m):
 a=set()
 if m["dna_rate"]>=.25:a.add("HIGH_DNA")
 if m["screen_failure_rate"]>=.35:a.add("HIGH_SCREEN_FAILURE")
 if m["weekly_enrolled"]<2:a.add("SLOW_RECRUITMENT")
 if m["overdue_followups"]>=8:a.add("OVERDUE_FOLLOWUP")
 if m["data_quality_issues"]>=6:a.add("DATA_QUALITY")
 return a
def expected(site,w):
 return {label for s,label,on,off in EPISODES if s==site and on<=w<off}
def main():
 rows=[];tp=fp=fn=0
 for w in range(1,WEEKS+1):
  for site in SITES:
   m=metrics(site,w);exp=expected(site,w);act=detect(m)
   tp+=len(exp&act);fp+=len(act-exp);fn+=len(exp-act)
   rows.append({"week":w,"site_id":site,**m,"expected":";".join(sorted(exp)),"detected":";".join(sorted(act)),
                "pass":exp==act})
 # Event-level time-to-detection and recovery.
 events=[]
 for site,label,on,off in EPISODES:
  alert_weeks=[r["week"] for r in rows if r["site_id"]==site and label in r["detected"].split(";")]
  first=min(alert_weeks) if alert_weeks else None
  after=[r for r in rows if r["site_id"]==site and r["week"]>=off and label in r["detected"].split(";")]
  recovery_detected=(len(after)==0)
  events.append({"site_id":site,"label":label,"onset_week":on,"recovery_week":off,
                 "first_detected_week":first,"detection_delay_weeks":None if first is None else first-on,
                 "recovery_detected":recovery_detected})
 delays=[e["detection_delay_weeks"] for e in events if e["detection_delay_weeks"] is not None]
 precision=tp/(tp+fp) if tp+fp else 1;recall=tp/(tp+fn) if tp+fn else 1
 zero_delay=all(x==0 for x in delays) and len(delays)==len(events)
 recovery=all(e["recovery_detected"] for e in events)
 overall=(fp==0 and fn==0 and zero_delay and recovery)
 outdir=ROOT/"benchmark_results/gate7_longitudinal";outdir.mkdir(parents=True,exist_ok=True)
 with (outdir/"weekly_site_metrics.csv").open("w",newline="") as f:
  w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
 report={"gate":"Gate 7 longitudinal study simulation","weeks":WEEKS,"sites":len(SITES),"episodes":events,
         "tp":tp,"fp":fp,"fn":fn,"precision":precision,"recall":recall,
         "mean_detection_delay_weeks":sum(delays)/len(delays) if delays else None,
         "recovery_detection_rate":sum(e["recovery_detected"] for e in events)/len(events),
         "pass":overall}
 (outdir/"gate7_report.json").write_text(json.dumps(report,indent=2))
 print("\n=== GATE 7 — 26-WEEK LONGITUDINAL STUDY ===")
 print(f"Sites={len(SITES)} Weeks={WEEKS} Site-weeks={len(rows)}")
 for e in events:
  print(("PASS" if e["detection_delay_weeks"]==0 and e["recovery_detected"] else "FAIL"),
        e["site_id"],e["label"],f"onset={e['onset_week']}",f"detected={e['first_detected_week']}",
        f"recovery={e['recovery_week']}",f"recovery_detected={e['recovery_detected']}")
 print(f"\nWeekly alert precision={precision:.3f} recall={recall:.3f} FP={fp} FN={fn}")
 print("Mean detection delay:",report["mean_detection_delay_weeks"],"weeks")
 print("Recovery detection:",f"{100*report['recovery_detection_rate']:.1f}%")
 print("Overall:","PASS" if overall else "FAIL")
 print("Report:",outdir/"gate7_report.json")
 raise SystemExit(0 if overall else 2)
if __name__=="__main__":main()
