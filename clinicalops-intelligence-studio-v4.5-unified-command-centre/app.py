import streamlit as st
from src.branding import inject_enterprise_css, hero, enterprise_card
_ = st.set_page_config(page_title='ClinicalOps Intelligence Studio',page_icon='🩺',layout='wide')
_ = inject_enterprise_css()
_ = hero('ClinicalOps Intelligence Studio','Synthea-backed population analytics, reusable protocol cohorts, local MedGemma review and explainable study/site operations intelligence.','v4.0 · Validated workflow + live study simulation')
c1,c2,c3=st.columns(3)
with c1: enterprise_card('1 · Understand the population','Use Data Analysis and Population Explorer to understand the synthetic source data before applying protocol criteria.')
with c2: enterprise_card('2 · Build & validate cohorts','Build reusable cohorts, run local MedGemma on bounded batches, and capture clinician decisions instead of reviewing every record manually.')
with c3: enterprise_card('3 · Operate the study','Use validated candidate populations to build a study, then monitor site risk, queries, deviations, visits and safety operations.')
_ = st.markdown('## Recommended workflow')
_ = st.markdown('**Data Analysis → Cohort Builder → Cohort Library → MedGemma Batch Review → Clinician Review → Evaluation Dashboard → Study Command Centre → Site Risk Drill-down**')
_ = st.info('Ask Clinical Ops is available in the sidebar on every page. It can investigate study metrics or prepare an editable test-cohort draft from a plain-language request.')
_ = st.caption('Research/portfolio prototype using synthetic data. Not a clinical device and not for patient-care decisions.')

_ = st.markdown('## Live portfolio demo')
_ = st.page_link('pages/13_Live_Study_Simulator.py',label='Open Live Study Simulator →')
