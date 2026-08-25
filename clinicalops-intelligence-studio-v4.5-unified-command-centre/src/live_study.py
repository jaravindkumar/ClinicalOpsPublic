from __future__ import annotations
import pandas as pd
from pathlib import Path
from datetime import date,timedelta
import duckdb, hashlib

DEFAULT_LIVE_DB="data/live_study_v40.duckdb"
SITES=[
 ("UK-LON-01","London Central",60),("UK-LON-02","London North",95),
 ("UK-MAN-01","Manchester",90),("UK-BHM-01","Birmingham",80),
 ("UK-LDS-01","Leeds",75),("UK-BRS-01","Bristol",70),
]
def con(db=DEFAULT_LIVE_DB):
 Path(db).parent.mkdir(parents=True,exist_ok=True); return duckdb.connect(db)
def init_live_study(db=DEFAULT_LIVE_DB,force=False):
 c=con(db)
 exists=c.execute("select count(*) from information_schema.tables where table_name='live_meta'").fetchone()[0]
 if exists and not force:
  c.close()
  return
 for t in ["live_meta","live_sites","live_patients","live_events","live_alerts"]:
  c.execute(f"drop table if exists {t}")
 c.execute("create table live_meta(key varchar primary key,value varchar)")
 c.executemany("insert into live_meta values (?,?)",[("study_id","COS-DEMO-001"),("study_name","UK Metabolic Outcomes Study"),("week","1"),("anchor_date","2026-08-07")])
 c.execute("create table live_sites(site_id varchar primary key,site_name varchar,capacity integer,intervention varchar)")
 c.executemany("insert into live_sites values (?,?,?,?)",[(a,b,d,"") for a,b,d in SITES])
 c.execute("""create table live_patients(
 patient_id varchar primary key, initials varchar, age integer, condition varchar,
 site_id varchar, status varchar, appointment_date date, appointment_status varchar,
 medgemma_status varchar, clinician_decision varchar, followup_due date, notes varchar)""")
 rows=[]
 for i in range(1,61):
  pid=f"DEMO-{i:04d}";site=SITES[(i-1)%6][0]
  rows.append((pid,f"P{i:03d}",50+(i%21),"T2DM + hypertension",site,"Candidate",None,"Not booked","Not reviewed","Pending",None,""))
 c.executemany("insert into live_patients values (?,?,?,?,?,?,?,?,?,?,?,?)",rows)
 c.execute("create table live_events(event_id bigint,week integer,event_type varchar,patient_id varchar,site_id varchar,detail varchar)")
 c.execute("create table live_alerts(week integer,site_id varchar,label varchar,reason varchar,active boolean)")
 c.close()
 refresh_alerts(db)
def week(db=DEFAULT_LIVE_DB):
 c=con(db);w=int(c.execute("select value from live_meta where key='week'").fetchone()[0]);c.close();return w
def log(c,w,etype,pid,site,detail):
 n=c.execute("select coalesce(max(event_id),0)+1 from live_events").fetchone()[0]
 c.execute("insert into live_events values (?,?,?,?,?,?)",[n,w,etype,pid,site,detail])
def book(pid,appt,db=DEFAULT_LIVE_DB):
 c=con(db);w=week(db);site=c.execute("select site_id from live_patients where patient_id=?",[pid]).fetchone()[0]
 c.execute("update live_patients set appointment_date=?,appointment_status='Booked',status='Screening booked' where patient_id=?",[appt,pid])
 log(c,w,"APPOINTMENT_BOOKED",pid,site,str(appt));c.close();refresh_alerts(db)
def mark_visit(pid,status,db=DEFAULT_LIVE_DB):
 c=con(db);w=week(db);site=c.execute("select site_id from live_patients where patient_id=?",[pid]).fetchone()[0]
 new="Screening attended" if status=="Attended" else "Needs reschedule"
 c.execute("update live_patients set appointment_status=?,status=? where patient_id=?",[status,new,pid])
 log(c,w,"VISIT_"+status.upper(),pid,site,status);c.close();refresh_alerts(db)
def review(pid,decision="Eligible",db=DEFAULT_LIVE_DB):
 c=con(db);w=week(db);site=c.execute("select site_id from live_patients where patient_id=?",[pid]).fetchone()[0]
 c.execute("update live_patients set medgemma_status='Evidence extracted',clinician_decision=? where patient_id=?",[decision,pid])
 log(c,w,"CLINICIAN_REVIEW",pid,site,decision);c.close()
def enroll(pid,db=DEFAULT_LIVE_DB):
 c=con(db);w=week(db);site=c.execute("select site_id from live_patients where patient_id=?",[pid]).fetchone()[0]
 due=date(2026,8,7)+timedelta(weeks=w+4)
 c.execute("update live_patients set status='Enrolled',followup_due=? where patient_id=?",[due,pid])
 log(c,w,"ENROLLED",pid,site,f"Follow-up due {due}");c.close();refresh_alerts(db)
def intervene(site,action,db=DEFAULT_LIVE_DB):
 c=con(db);w=week(db);c.execute("update live_sites set intervention=? where site_id=?",[action,site])
 log(c,w,"SITE_INTERVENTION","",site,action);c.close();refresh_alerts(db)
def advance(n=1,db=DEFAULT_LIVE_DB):
 c=con(db);w=week(db)+int(n);c.execute("update live_meta set value=? where key='week'",[str(w)])
 # Frozen demo episode: London North deteriorates from week 5; intervention clears it next week.
 c.close();refresh_alerts(db);return w
def _recruitment_state(c,sid,w,cap,intervention):
 weekly_targets={"UK-LON-01":3.0,"UK-LON-02":2.5,"UK-MAN-01":2.0,"UK-BHM-01":2.0,"UK-LDS-01":2.0,"UK-BRS-01":2.0}
 background_rates={"UK-LON-01":3.0,"UK-LON-02":2.5,"UK-MAN-01":1.9,"UK-BHM-01":2.0,"UK-LDS-01":2.1,"UK-BRS-01":2.0}
 target=weekly_targets[sid]
 manual=c.execute("select count(*) from live_patients where site_id=? and status='Enrolled'",[sid]).fetchone()[0]
 expected=min(cap,round(target*w))

 # Current weekly velocity is the operational early-warning signal.
 if sid=="UK-LON-02" and w>=5 and not intervention:
  current_velocity=.5
  background_actual=round(background_rates[sid]*4 + current_velocity*(w-4))
 else:
  current_velocity=background_rates[sid]
  background_actual=round(background_rates[sid]*w)

 actual=min(cap,background_actual+manual)
 attainment=actual/expected if expected else 1.0
 velocity_ratio=current_velocity/target if target else 1.0
 velocity_drop=1.0-velocity_ratio

 return {
  "weekly_target":target,
  "expected_enrolled":expected,
  "actual_enrolled":actual,
  "attainment":attainment,
  "recent_velocity":current_velocity,
  "velocity_ratio":velocity_ratio,
  "velocity_drop":velocity_drop,
 }

def recruitment_trajectory(db=DEFAULT_LIVE_DB):
 c=con(db)
 w=int(c.execute("select value from live_meta where key='week'").fetchone()[0])
 rows=[]
 for sid,name,cap in SITES:
  intervention=c.execute("select intervention from live_sites where site_id=?",[sid]).fetchone()[0]
  r=_recruitment_state(c,sid,w,cap,intervention)
  rows.append({"site_id":sid,"site_name":name,"week":w,**r})
 c.close()
 return pd.DataFrame(rows)

def refresh_alerts(db=DEFAULT_LIVE_DB):
 c=con(db)
 w=int(c.execute("select value from live_meta where key='week'").fetchone()[0])
 c.execute("delete from live_alerts where week=?",[w])

 MIN_DNA_DENOMINATOR=5
 MIN_RECRUITMENT_WEEK=4
 MIN_CUMULATIVE_ATTAINMENT=.70
 MIN_VELOCITY_RATIO=.60

 for sid,name,cap in SITES:
  intervention=c.execute("select intervention from live_sites where site_id=?",[sid]).fetchone()[0]

  observed_visits=c.execute(
   """select count(*) from live_patients
      where site_id=? and appointment_status in ('Attended','DNA')""",[sid]
  ).fetchone()[0]
  dna=c.execute("select count(*) from live_patients where site_id=? and appointment_status='DNA'",[sid]).fetchone()[0]
  dna_rate=dna/observed_visits if observed_visits else 0.0

  rate_based_high_dna=observed_visits>=MIN_DNA_DENOMINATOR and dna_rate>=.25
  controlled_high_dna=sid=="UK-LON-02" and w>=5 and not intervention
  high_dna=rate_based_high_dna or controlled_high_dna

  if high_dna:
   source="controlled longitudinal signal" if controlled_high_dna and not rate_based_high_dna else "observed visit rate"
   c.execute("insert into live_alerts values (?,?,?,?,true)",
    [w,sid,"HIGH_DNA",f"DNA {dna}/{observed_visits} observed visits ({dna_rate:.0%}); source={source}"])

  r=_recruitment_state(c,sid,w,cap,intervention)
  cumulative_bad=(w>=MIN_RECRUITMENT_WEEK and r["expected_enrolled"]>=5 and r["attainment"]<MIN_CUMULATIVE_ATTAINMENT)
  velocity_bad=(w>=MIN_RECRUITMENT_WEEK and r["velocity_ratio"]<MIN_VELOCITY_RATIO)
  slow_recruitment=cumulative_bad or velocity_bad

  if slow_recruitment:
   if velocity_bad and not cumulative_bad:
    reason=(f"Recruitment velocity {r['recent_velocity']:.1f}/week vs "
            f"{r['weekly_target']:.1f}/week plan ({r['velocity_ratio']:.0%}); "
            f"cumulative attainment still {r['attainment']:.0%}")
   elif cumulative_bad and not velocity_bad:
    reason=(f"{r['actual_enrolled']} actual vs {r['expected_enrolled']} expected "
            f"({r['attainment']:.0%} cumulative attainment)")
   else:
    reason=(f"Recruitment velocity {r['velocity_ratio']:.0%} of plan and "
            f"cumulative attainment {r['attainment']:.0%}")
   c.execute("insert into live_alerts values (?,?,?,?,true)",[w,sid,"SLOW_RECRUITMENT",reason])

 c.close()
def snapshot(db=DEFAULT_LIVE_DB):
 c=con(db);w=int(c.execute("select value from live_meta where key='week'").fetchone()[0])
 pats=c.execute("select * from live_patients order by patient_id").df()
 sites=c.execute("""select s.site_id,s.site_name,s.capacity,
 count(p.patient_id) candidates,
 sum(case when p.status='Enrolled' then 1 else 0 end) enrolled,
 sum(case when p.appointment_status='DNA' then 1 else 0 end) dna,
 s.intervention from live_sites s left join live_patients p using(site_id)
 group by all order by s.site_id""").df()
 alerts=c.execute("select * from live_alerts where week=? and active order by site_id,label",[w]).df()
 events=c.execute("select * from live_events order by event_id desc limit 50").df();c.close()
 return w,pats,sites,alerts,events
