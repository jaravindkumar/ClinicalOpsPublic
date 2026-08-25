import streamlit as st
from datetime import date,timedelta
from src.branding import inject_enterprise_css,hero
from src.live_study import init_live_study,snapshot,book,mark_visit,review,enroll,advance,intervene,recruitment_trajectory,DEFAULT_LIVE_DB

st.set_page_config(page_title="Live Study Simulator",layout="wide")
inject_enterprise_css()
hero("Live Study Simulator","Operate a synthetic UK study end-to-end: screening, appointments, review, enrolment, follow-up and site-risk intervention.","v4.4 · Recruitment velocity + trajectory")
with st.sidebar:
 st.markdown("### Simulation control")
 if st.button("Reset demo",use_container_width=True):
  init_live_study(force=True)
  st.session_state["live_patient"] = "DEMO-0001"
  st.session_state["reset_notice"] = True
  st.rerun()
 if st.button("Advance 1 study week",type="primary",use_container_width=True):
  advance(1);st.rerun()
 st.caption("Synthetic portfolio simulation. No real patient data.")
init_live_study()
if st.session_state.pop("reset_notice", False):
 st.toast("Demo reset to Study Week 1")
w,pats,sites,alerts,events=snapshot()
if "live_patient" not in st.session_state or st.session_state["live_patient"] not in pats.patient_id.tolist():
 st.session_state["live_patient"]="DEMO-0001"
def patient_picker(label,key):
 current=st.session_state["live_patient"]
 idx=pats.patient_id.tolist().index(current)
 chosen=st.selectbox(label,pats.patient_id.tolist(),index=idx,key=key)
 if chosen != st.session_state["live_patient"]:
  st.session_state["live_patient"]=chosen
 return chosen
trajectory=recruitment_trajectory()
portfolio_actual=int(trajectory["actual_enrolled"].sum()) if not trajectory.empty else 0
portfolio_expected=int(trajectory["expected_enrolled"].sum()) if not trajectory.empty else 0
c1,c2,c3,c4=st.columns(4)
c1.metric("Study week",w);c2.metric("Candidates",len(pats));c3.metric("Simulated enrolled",portfolio_actual,delta=f"{portfolio_actual-portfolio_expected:+d} vs plan");c4.metric("Active alerts",len(alerts))
tabs=st.tabs(["Patient workflow","Appointments","Clinician review","Command Centre","Audit trail"])
with tabs[0]:
 st.markdown("### 1 · Screen and select a candidate")
 pid=patient_picker("Patient","live_pid")
 row=pats[pats.patient_id==pid].iloc[0]
 st.dataframe(row.to_frame("value"),use_container_width=True)
 st.caption("The live simulator uses synthetic candidates so the workflow can be demonstrated without PHI.")
with tabs[1]:
 st.markdown("### 2 · Book and operate the screening visit")
 pid2=patient_picker("Patient","appt_pid")
 appt=st.date_input("Appointment date",date.today()+timedelta(days=2))
 current=pats[pats.patient_id==pid2].iloc[0]
 can_book=current.appointment_status in ("Not booked","DNA")
 can_complete=current.appointment_status=="Booked"
 a,b,c=st.columns(3)
 if a.button("Book appointment",use_container_width=True,disabled=not can_book):
  book(pid2,appt);st.rerun()
 if b.button("Mark attended",use_container_width=True,disabled=not can_complete):
  mark_visit(pid2,"Attended");st.rerun()
 if c.button("Mark DNA",use_container_width=True,disabled=not can_complete):
  mark_visit(pid2,"DNA");st.rerun()
 st.dataframe(pats[["patient_id","site_id","status","appointment_date","appointment_status"]],use_container_width=True,hide_index=True)
with tabs[2]:
 st.markdown("### 3 · Evidence review → clinician decision → enrolment")
 pid3=patient_picker("Patient","review_pid")
 current=pats[pats.patient_id==pid3].iloc[0]
 can_review=current.appointment_status=="Attended"
 can_enrol=(current.clinician_decision=="Eligible" and current.status!="Enrolled")
 a,b,c=st.columns(3)
 if a.button("Run bounded evidence review",use_container_width=True,disabled=not can_review):
  review(pid3,"Pending");st.rerun()
 if b.button("Clinician: Eligible",use_container_width=True,disabled=current.medgemma_status!="Evidence extracted"):
  review(pid3,"Eligible");st.rerun()
 if c.button("Enrol patient",type="primary",use_container_width=True,disabled=not can_enrol):
  enroll(pid3);st.rerun()
 st.info("In the validated production path, MedGemma extracts evidence; the clinician retains the eligibility decision. This demo action does not replace clinician review.")
 st.dataframe(pats[["patient_id","site_id","medgemma_status","clinician_decision","status","followup_due"]],use_container_width=True,hide_index=True)
with tabs[3]:
 st.markdown("### 4 · Unified Study Command Centre")

 # Presentation layer only: v4.4 detection thresholds and alert logic remain unchanged.
 command=trajectory.merge(sites[["site_id","intervention"]],on="site_id",how="left")
 active_by_site={}
 if not alerts.empty:
  active_by_site=alerts.groupby("site_id")["label"].apply(lambda x:", ".join(x.tolist())).to_dict()
 intervention_week={}
 if not events.empty:
  ie=events[events.event_type=="SITE_INTERVENTION"]
  if not ie.empty:
   intervention_week=ie.groupby("site_id")["week"].max().to_dict()

 def _status(row):
  sid=row["site_id"]
  if sid in active_by_site:
   return "At risk"
  if row.get("intervention",""):
   iw=intervention_week.get(sid)
   return "Intervention applied" if iw==w else "Recovering"
  return "Healthy"

 command["attainment"]=(command["attainment"]*100).round(0).astype(int).astype(str)+"%"
 command["recent_velocity"]=command["recent_velocity"].map(lambda x:f"{x:.1f}/wk")
 command["plan_velocity"]=command["weekly_target"].map(lambda x:f"{x:.1f}/wk")
 command["risk_status"]=command.apply(_status,axis=1)
 command["active_risk"]=command["site_id"].map(active_by_site).fillna("—")
 display=command[["site_id","site_name","actual_enrolled","expected_enrolled","attainment","recent_velocity","plan_velocity","risk_status","active_risk"]].rename(columns={
  "site_id":"Site ID","site_name":"Site","actual_enrolled":"Actual","expected_enrolled":"Expected",
  "attainment":"Attainment","recent_velocity":"Recent velocity","plan_velocity":"Plan","risk_status":"Status","active_risk":"Active risk"})
 st.dataframe(display,use_container_width=True,hide_index=True)

 if alerts.empty:st.success("No active operational alerts this week.")
 else:
  st.warning(f"{len(alerts)} active operational alert(s)")
  st.dataframe(alerts[["site_id","label","reason"]],use_container_width=True,hide_index=True)

 st.markdown("#### Site intelligence")
 selected=st.selectbox("Inspect site",command.site_id.tolist(),index=command.site_id.tolist().index("UK-LON-02") if "UK-LON-02" in command.site_id.tolist() else 0)
 sr=trajectory[trajectory.site_id==selected].iloc[0]
 site_alerts=alerts[alerts.site_id==selected] if not alerts.empty else alerts
 a,b,c,d=st.columns(4)
 a.metric("Actual / expected",f"{int(sr.actual_enrolled)} / {int(sr.expected_enrolled)}")
 b.metric("Cumulative attainment",f"{sr.attainment:.0%}")
 c.metric("Recent velocity",f"{sr.recent_velocity:.1f}/wk")
 d.metric("Planned velocity",f"{sr.weekly_target:.1f}/wk")

 if not site_alerts.empty:
  st.error("Why this site is at risk: " + " | ".join(site_alerts.reason.tolist()))
 elif command.loc[command.site_id==selected,"intervention"].iloc[0]:
  iw=intervention_week.get(selected,w)
  if iw==w:
   st.info(f"Intervention applied in Week {iw}. Outcome not yet demonstrated; advance the study to assess recovery.")
  else:
   st.success(f"No active alert. Intervention was applied in Week {iw}; current operational signals are within thresholds.")
 else:
  st.success("Current recruitment and operational signals are within validated thresholds.")

 # Compact cumulative recruitment trajectory for the selected site.
 hist=[]
 for wk in range(1,w+1):
  target=float(sr.weekly_target)
  expected=min(int(sites.loc[sites.site_id==selected,"capacity"].iloc[0]),round(target*wk))
  iw=intervention_week.get(selected)
  if selected=="UK-LON-02" and wk>=5 and (iw is None or wk<=iw):
   actual=round(2.5*4+0.5*(wk-4))
  else:
   rate={"UK-LON-01":3.0,"UK-LON-02":2.5,"UK-MAN-01":1.9,"UK-BHM-01":2.0,"UK-LDS-01":2.1,"UK-BRS-01":2.0}[selected]
   actual=round(rate*wk)
  hist.append({"Week":wk,"Expected":expected,"Actual":actual})
 import pandas as pd
 chart=pd.DataFrame(hist).set_index("Week")
 st.line_chart(chart,use_container_width=True)

 st.markdown("#### Operational intervention")
 site=st.selectbox("Intervention site",sites.site_id.tolist(),key="intervention_site")
 action=st.selectbox("Operational action",["Patient reminder workflow + site huddle","Add screening slots","CRA data-quality review","Recruitment recovery plan"])
 if st.button("Apply intervention",use_container_width=True):
  intervene(site,action);st.rerun()
 st.caption("v4.5 surfaces the validated v4.4 recruitment model. Alert thresholds and detection logic are unchanged.")
with tabs[4]:
 st.markdown("### Explainable audit trail")
 st.dataframe(events,use_container_width=True,hide_index=True)
