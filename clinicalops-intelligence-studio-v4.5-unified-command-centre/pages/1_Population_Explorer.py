import streamlit as st
from src.branding import inject_enterprise_css
from src.trial_ops import DEFAULT_SYNTHEA_DIR, synthea_status
from src.cohort_engine import filter_population, condition_options

_ = st.set_page_config(page_title='Population Explorer',layout='wide'); _ = inject_enterprise_css()
_ = st.title('Population Explorer')
_ = st.caption('Search an individual synthetic patient or explore the Synthea population before creating a cohort.')
with st.sidebar:
    _ = st.markdown('### Synthea')
    root=st.text_input('CSV directory',DEFAULT_SYNTHEA_DIR)
    if synthea_status(root)['ready']:
        _ = st.success('Connected')
    else:
        _ = st.error('Not connected')
if not synthea_status(root)['ready']: st.stop()
mode=st.segmented_control('Workspace',['Find patient','Explore population'],default='Explore population')
if mode=='Find patient':
    pid=st.text_input('Patient ID',placeholder='Paste full Synthea patient UUID')
    if pid:
        df=filter_population(root,0,120,'Any','', '',0)
        hit=df[df.patient_id.str.contains(pid,case=False,na=False)]
        _ = st.dataframe(hit,use_container_width=True,hide_index=True)
        _ = st.caption('Open the patient from Patient Review after selecting a cohort, or copy the Patient ID for investigation.')
else:
    c1,c2,c3=st.columns(3)
    age=c1.slider('Age',0,100,(18,80)); sex=c2.selectbox('Sex',['Any','Female','Male']); recent=c3.selectbox('Encounter activity',['Any time','≤ 1 year','≤ 3 years','≤ 5 years','≤ 10 years'],index=4)
    opts=condition_options(root)
    condition=st.selectbox('Condition contains',opts,index=0)
    years={'Any time':0,'≤ 1 year':1,'≤ 3 years':3,'≤ 5 years':5,'≤ 10 years':10}[recent]
    df=filter_population(root,*age,sex,condition,'',years)
    _ = st.metric('Matching patients',f'{len(df):,}')
    _ = st.dataframe(df.head(500),use_container_width=True,hide_index=True)
    if len(df)>500: st.caption(f'Showing first 500 of {len(df):,} matches.')
