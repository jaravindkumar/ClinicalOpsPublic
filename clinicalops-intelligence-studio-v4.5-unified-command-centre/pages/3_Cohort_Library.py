import streamlit as st
from src.branding import inject_enterprise_css
from src.cohort_engine import list_cohorts, cohort_members
_ = st.set_page_config(page_title='Cohort Library',layout='wide'); _ = inject_enterprise_css(); _ = st.title('Cohort Library')
df=list_cohorts()
if df.empty: st.info('No saved cohorts yet. Create one in Build Cohort.'); st.stop()
_ = st.dataframe(df[['cohort_id','name','patient_count','created_at']],use_container_width=True,hide_index=True)
cid=st.selectbox('Open cohort',df.cohort_id.tolist(),format_func=lambda x:f"{df.loc[df.cohort_id==x,'name'].iloc[0]} · {x}")
m=cohort_members(cid); st.metric('Patients',f'{len(m):,}'); st.dataframe(m,use_container_width=True,hide_index=True)
