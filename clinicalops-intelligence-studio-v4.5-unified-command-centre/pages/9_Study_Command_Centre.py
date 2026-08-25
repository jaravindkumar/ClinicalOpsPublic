import os
import streamlit as st
import plotly.express as px
from src.branding import inject_enterprise_css, hero
from src.trial_ops import DEFAULT_SYNTHEA_DIR, build_trial, ensure_trial, get_attention_items, get_site_scores, get_study_summary, synthea_status, get_study_weekly_risk, get_country_summary
from src.cohort_engine import list_cohorts, cohort_members

_ = st.set_page_config(page_title='Study Command Centre',layout='wide')
_ = inject_enterprise_css()
_ = hero('Study Command Centre','One place to see whether the trial is on track, where risk is emerging, and what the operations team should investigate next.','Study oversight')

with st.sidebar:
    _ = st.markdown('### Trial build')
    synthea_dir=st.text_input('Synthea CSV directory',os.getenv('SYNTHEA_CSV_DIR',DEFAULT_SYNTHEA_DIR),key='study_root_v11')
    target=st.number_input('Target enrollment',100,5000,500,50,key='study_target_v11')
    cohorts=list_cohorts(); cohort_labels=['Default diabetes-enriched pool']
    if not cohorts.empty: cohort_labels += [f"{r.cohort_id} · {r.name} · {r.patient_count} patients" for r in cohorts.itertuples(index=False)]
    source=st.selectbox('Candidate source',cohort_labels,key='study_cohort_source_v11')
    ready=synthea_status(synthea_dir)['ready']; st.success('Synthea ready') if ready else st.error('Synthea unavailable')
    if st.button('Build / rebuild study',type='primary',use_container_width=True,disabled=not ready):
        ids=None; cname=None
        if source!='Default diabetes-enriched pool':
            cid=source.split(' · ')[0]; m=cohort_members(cid); ids=m.patient_id.astype(str).tolist(); cname=source.split(' · ')[1]
        with st.spinner('Creating study subjects and operational events...'):
            build_trial(synthea_dir,target_enrollment=int(target),force=True,candidate_patient_ids=ids,cohort_name=cname)
        _ = st.success('Study rebuilt'); st.rerun()

if not ensure_trial(synthea_dir): st.info('Build the study from the sidebar first.'); st.stop()
summary=get_study_summary(); sites=get_site_scores(); weekly=get_study_weekly_risk(); countries=get_country_summary()
enrollment_pct=100*summary['enrolled']/max(1,summary['target'])

_ = st.markdown(f"### {summary.get('study_id','')} · {summary.get('study_name','')}")
_ = st.caption(f"Candidate source: {summary.get('source_cohort','Default candidate pool')} · Built {summary.get('build_date','—')}")

c1,c2,c3,c4,c5,c6=st.columns(6)
c1.metric('Enrollment',f"{summary['enrolled']:,}/{summary['target']:,}",f"{enrollment_pct:.1f}%")
c2.metric('Study risk',f"{summary['avg_risk']:.0f}/100")
c3.metric('High-risk sites',summary['high_risk_sites'])
c4.metric('Overdue visits',summary['overdue_visits'])
c5.metric('Open queries',summary['open_queries'])
c6.metric('Open AEs',summary['open_aes'])

if summary['high_risk_sites']>0 or summary['overdue_visits']>0:
    _ = st.warning(f"Attention required: {summary['high_risk_sites']} high-risk site(s), {summary['overdue_visits']} overdue visits and {summary['open_queries']} open queries.")
else: st.success('No high-priority operational exception is currently detected.')

_ = st.markdown('## Priority work queue')
for item in get_attention_items(limit=5):
    tone='🔴' if item['risk_band']=='High' else '🟠' if item['risk_band']=='Medium' else '🟢'
    drivers=' · '.join(f"{n}: {v:.0f}" for n,v in item['drivers'])
    _ = st.markdown(f"**{tone} {item['site_id']} · {item['site_name']} — Risk {item['risk_score']:.0f}/100**  \n{drivers}  \n{item['overdue_visits']} overdue visits · {item['open_queries']} open queries · {item['deviations']} deviations")

overview,quality,safety,sites_tab=st.tabs(['Overview','Data & protocol quality','Safety operations','Sites'])
with overview:
    l,r=st.columns([1.4,1])
    with l:
        fig=px.line(weekly,x='week_date',y=['avg_risk','max_risk'],markers=True,labels={'value':'Risk score','week_date':'Week','variable':'Signal'})
        fig.update_yaxes(range=[0,100]); fig.update_layout(height=360,margin=dict(l=10,r=10,t=25,b=10)); st.plotly_chart(fig,use_container_width=True)
    with r:
        _ = st.markdown('### Country performance')
        _ = st.dataframe(countries,use_container_width=True,hide_index=True,height=330)
with quality:
    q=sites[['site_id','site_name','open_queries','avg_open_query_age','deviations','important_deviations','missed_visit_rate','overdue_visits','query_risk','deviation_risk']].sort_values(['query_risk','deviation_risk'],ascending=False)
    _ = st.dataframe(q,use_container_width=True,hide_index=True)
    fig=px.scatter(sites,x='avg_open_query_age',y='missed_visit_rate',size='open_queries',color='risk_band',hover_name='site_name',labels={'avg_open_query_age':'Average open-query age (days)','missed_visit_rate':'Missed visit rate (%)'})
    _ = st.plotly_chart(fig,use_container_width=True)
with safety:
    s=sites[['site_id','site_name','adverse_events','open_aes','avg_ae_report_delay','safety_risk','risk_band']].sort_values('safety_risk',ascending=False)
    _ = st.dataframe(s,use_container_width=True,hide_index=True)
    fig=px.bar(s.head(10),x='site_id',y='safety_risk',hover_data=['open_aes','avg_ae_report_delay'],labels={'safety_risk':'Safety operations risk'})
    fig.update_yaxes(range=[0,100]); st.plotly_chart(fig,use_container_width=True)
with sites_tab:
    display=sites[['site_id','site_name','country','risk_score','risk_band','enrolled','target_enrollment','screen_failure_rate','overdue_visits','open_queries','deviations','open_aes']]
    _ = st.dataframe(display,use_container_width=True,hide_index=True)
    _ = st.page_link('pages/10_Site_Risk_Drilldown.py',label='Open Site Risk Drill-down →')

_ = st.caption('Risk scores are deterministic operational signals. Gemma explains the stored evidence; it does not set the risk score or make medical decisions.')
