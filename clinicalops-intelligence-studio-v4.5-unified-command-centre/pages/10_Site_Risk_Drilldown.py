import pandas as pd
import streamlit as st
import plotly.express as px
from src.branding import inject_enterprise_css, hero
from src.trial_ops import ensure_trial,get_site_detail,get_site_scores

_ = st.set_page_config(page_title='Site Risk Drill-down',layout='wide')
_ = inject_enterprise_css()
_ = hero('Site Risk Drill-down','Move from a site score to the precise operational signals and subjects creating workload.','Explainable site monitoring')
if not ensure_trial(): st.warning('Build the study first.'); st.stop()
sites=get_site_scores(); labels=[f"{r.site_id} · {r.site_name} · {r.risk_band} {r.risk_score:.0f}" for _,r in sites.iterrows()]
choice=st.selectbox('Site',labels,key='site_drill_v11'); site_id=choice.split(' · ')[0]
site,trend,subjects=get_site_detail(site_id)
median=sites.median(numeric_only=True)

_ = st.markdown(f"## {site['site_id']} · {site['site_name']} · {site['country']}")
if site['risk_band']=='High': st.error(f"High operational risk · {site['risk_score']:.0f}/100")
elif site['risk_band']=='Medium': st.warning(f"Medium operational risk · {site['risk_score']:.0f}/100")
else: st.success(f"Low operational risk · {site['risk_score']:.0f}/100")

c1,c2,c3,c4,c5=st.columns(5)
c1.metric('Enrollment',f"{int(site['enrolled'])}/{int(site['target_enrollment'])}",f"{100*site['enrolled']/max(1,site['target_enrollment']):.0f}%")
c2.metric('Missed visits',int(site['missed_visits']),f"{site['missed_visit_rate']:.1f}%")
c3.metric('Open queries',int(site['open_queries']),f"{site['avg_open_query_age']:.1f}d avg")
c4.metric('Deviations',int(site['deviations']),f"{int(site['important_deviations'])} important")
c5.metric('Open AEs',int(site['open_aes']),f"{site['avg_ae_report_delay']:.1f}d report delay")

_ = st.markdown('## Why this site has this score')
drivers=pd.DataFrame({'Driver':['Enrollment','Visit compliance','Data quality','Protocol compliance','Safety operations'],
                      'Risk signal':[site['enrollment_risk'],site['visit_risk'],site['query_risk'],site['deviation_risk'],site['safety_risk']]})
drivers['Study median']=[median.get('enrollment_risk',0),median.get('visit_risk',0),median.get('query_risk',0),median.get('deviation_risk',0),median.get('safety_risk',0)]
drivers['Delta vs median']=drivers['Risk signal']-drivers['Study median']
l,r=st.columns([1.25,1])
with l:
    fig=px.bar(drivers.sort_values('Risk signal'),x='Risk signal',y='Driver',orientation='h',hover_data=['Study median','Delta vs median'])
    fig.update_xaxes(range=[0,100]); fig.update_layout(height=350,margin=dict(l=10,r=10,t=20,b=10)); st.plotly_chart(fig,use_container_width=True)
with r:
    _ = st.dataframe(drivers.sort_values('Risk signal',ascending=False),use_container_width=True,hide_index=True)
    top=drivers.sort_values('Risk signal',ascending=False).iloc[0]
    _ = st.info(f"Primary driver: {top['Driver']} ({top['Risk signal']:.0f}/100), {top['Delta vs median']:+.0f} versus the study median.")

_ = st.markdown('## Risk trajectory')
fig=px.line(trend,x='week_date',y='risk_score',markers=True,labels={'week_date':'Week','risk_score':'Risk score'})
fig.update_yaxes(range=[0,100]); fig.update_layout(height=320,margin=dict(l=10,r=10,t=20,b=10)); st.plotly_chart(fig,use_container_width=True)

_ = st.markdown('## Subject-level operational workload')
show=subjects.copy(); show['attention_score']=show['missed_visits']*3+show['late_visits']+show['open_queries']*2+show['deviations']*3
show=show.sort_values('attention_score',ascending=False)
f1,f2=st.columns(2)
only_attention=f1.checkbox('Only subjects with an operational issue',value=True)
min_score=f2.number_input('Minimum attention score',0,50,1)
if only_attention: show=show[show.attention_score>=max(1,min_score)]
_ = st.dataframe(show,use_container_width=True,hide_index=True)

_ = st.markdown('## Suggested operational next steps')
steps=[]
if site['query_risk']>=45: steps.append('Review aged/open data queries with the site data-management contact.')
if site['visit_risk']>=45: steps.append('Review missed and overdue visit backlog and identify recurring visit-window causes.')
if site['deviation_risk']>=45: steps.append('Review important protocol deviations and whether corrective/preventive action is needed.')
if site['safety_risk']>=45: steps.append('Verify adverse-event reporting timelines and unresolved safety follow-up.')
if site['enrollment_risk']>=45: steps.append('Review recruitment velocity versus site target and current screening pipeline.')
if not steps: steps=['Continue routine monitoring; no risk domain currently crosses the medium-risk signal threshold.']
for i,x in enumerate(steps,1): st.markdown(f"**{i}.** {x}")
_ = st.caption('These are operational review prompts derived from deterministic metrics, not clinical treatment recommendations.')
