import streamlit as st
import plotly.express as px
from src.branding import inject_enterprise_css, hero
from src.trial_ops import DEFAULT_SYNTHEA_DIR, synthea_status
from src.data_analysis import population_summary, age_distribution, top_conditions, encounter_mix, encounter_trend, data_volume, cohort_profile
from src.cohort_engine import list_cohorts, cohort_members

_ = st.set_page_config(page_title='Data Analysis',layout='wide')
_ = inject_enterprise_css()
_ = hero('Data Analysis','Explore the source population or inspect a saved cohort before model review and trial operations.','Synthea population intelligence')
with st.sidebar:
    root=st.text_input('Synthea CSV directory',DEFAULT_SYNTHEA_DIR,key='analysis_root_v11')
    ok=synthea_status(root)['ready']
    _ = st.success('Synthea connected') if ok else st.error('Synthea unavailable')
if not ok: st.stop()

view=st.segmented_control('Analysis view',['Population','Cohort Analysis'],default='Population')

if view=='Population':
    with st.spinner('Profiling population...'):
        summary=population_summary(root); ages=age_distribution(root); conditions=top_conditions(root,15); mix=encounter_mix(root); trend=encounter_trend(root,5); volumes=data_volume(root)
    c1,c2,c3,c4=st.columns(4)
    c1.metric('Patients',f"{summary['patients']:,}"); c2.metric('Median age',f"{summary['median_age']:.0f}")
    c3.metric('Female',f"{summary['female']:,}",f"{100*summary['female']/max(1,summary['patients']):.1f}%")
    c4.metric('Male',f"{summary['male']:,}",f"{100*summary['male']/max(1,summary['patients']):.1f}%")
    _ = st.markdown('## Population composition')
else:
    cohorts=list_cohorts()
    if cohorts.empty:
        st.info('No saved cohorts yet. Build and save a cohort first.'); st.stop()
    options={f"{r['name']} · {int(r['patient_count']):,} patients":r['cohort_id'] for _,r in cohorts.iterrows()}
    label=st.selectbox('Saved cohort',list(options.keys())); cid=options[label]
    members=cohort_members(cid)
    with st.spinner('Profiling saved cohort...'):
        prof=cohort_profile(root,members); pop=population_summary(root)
    summary=prof['summary']; ages=prof['ages']; conditions=prof['conditions']; mix=prof['mix']; trend=prof['trend']
    c1,c2,c3,c4=st.columns(4)
    c1.metric('Cohort patients',f"{summary['patients']:,}",f"{100*summary['patients']/max(1,pop['patients']):.1f}% of population")
    c2.metric('Median age',f"{summary['median_age']:.0f}")
    c3.metric('Female',f"{summary['female']:,}",f"{100*summary['female']/max(1,summary['patients']):.1f}%")
    c4.metric('Male',f"{summary['male']:,}",f"{100*summary['male']/max(1,summary['patients']):.1f}%")
    _ = st.markdown('## Cohort composition')

l,r=st.columns(2)
with l:
    fig=px.bar(ages,x='age_band',y='patients',labels={'age_band':'Age band','patients':'Patients'}); fig.update_layout(height=360,margin=dict(l=10,r=10,t=20,b=10)); st.plotly_chart(fig,use_container_width=True)
with r:
    _ = st.markdown('### Most prevalent recorded conditions'); _ = st.dataframe(conditions,use_container_width=True,hide_index=True,height=340)
_ = st.markdown('## Healthcare utilisation')
l,r=st.columns([1,1.5])
with l:
    fig=px.bar(mix.head(12),x='encounters',y='encounter_class',orientation='h',labels={'encounter_class':'Encounter type'}); fig.update_layout(height=390,margin=dict(l=10,r=10,t=20,b=10)); st.plotly_chart(fig,use_container_width=True)
with r:
    fig=px.line(trend,x='month_start',y='encounter_count',labels={'month_start':'Month','encounter_count':'Encounters'}); fig.update_layout(height=390,margin=dict(l=10,r=10,t=20,b=10)); st.plotly_chart(fig,use_container_width=True)

if view=='Population':
    _ = st.markdown('## Data scale'); _ = st.caption('Record volume across the eight connected synthetic healthcare datasets. Cohort filtering and MedGemma packets operate on bounded subsets rather than sending raw tables to the model.')
    fig=px.bar(volumes,x='records',y='dataset',orientation='h',log_x=True,labels={'records':'Records (log scale)','dataset':''}); fig.update_layout(height=430,margin=dict(l=10,r=10,t=20,b=10)); st.plotly_chart(fig,use_container_width=True); _ = st.dataframe(volumes,use_container_width=True,hide_index=True)
else:
    _ = st.markdown('## Cohort members'); _ = st.dataframe(members,use_container_width=True,hide_index=True,height=340)

_ = st.markdown('## Product interpretation')
_ = st.info('Use Population analysis to understand source-data composition and scale. Use Cohort Analysis to validate the composition and utilisation profile of a saved candidate cohort before MedGemma review. This is descriptive analysis, not clinical inference.')
