import streamlit as st
from src.branding import inject_enterprise_css, hero
from src.gemma_ops_client import DEFAULT_GEMMA_MODEL, deterministic_fallback, grounded_ops_answer, ollama_health
from src.trial_ops import build_grounded_context, ensure_trial
from src.copilot import parse_cohort_request

_ = st.set_page_config(page_title='Ask Clinical Ops',layout='wide')
_ = inject_enterprise_css()
_ = hero('Ask Clinical Ops','Investigate grounded study metrics or turn a plain-language population idea into an editable test-cohort draft.','Copilot workspace')

with st.sidebar:
    model=st.text_input('Ollama model',DEFAULT_GEMMA_MODEL,key='ops_model_v11')
    up=ollama_health(); st.success('Ollama reachable') if up else st.warning('Ollama not reachable')

mode=st.segmented_control('What do you want to do?',['Investigate study','Draft a test cohort'],default='Investigate study')
if mode=='Investigate study':
    suggestions=['Which sites need attention today and why?','What changed in study risk over time?','Which sites have the oldest open queries?','Where are protocol deviations concentrated?','What should I review before the weekly governance meeting?']
    q=st.selectbox('Start with a question',['Custom question']+suggestions)
    if q=='Custom question': q=st.text_area('Question',height=100,placeholder='Ask about study, site, quality, safety or operational workload...')
    else: st.text_area('Question',value=q,height=100,disabled=True)
    if st.button('Ask Clinical Ops',type='primary') and q.strip():
        if not ensure_trial(): st.error('Build the study first from Study Command Centre.')
        else:
            ctx=build_grounded_context(q)
            with st.spinner('Reviewing grounded evidence...'):
                try: answer=grounded_ops_answer(q,ctx,model=model) if up else deterministic_fallback(q,ctx)
                except Exception as e: answer=deterministic_fallback(q,ctx)+f"\n\nModel error: {e}"
            _ = st.markdown('## Answer'); st.markdown(answer)
            with st.expander('Evidence supplied to the model'): st.json(ctx)
else:
    q=st.text_area('Describe the population',height=120,placeholder='e.g. Adults age 55 to 75 with diabetes and hypertension, excluding chronic kidney disease, with an encounter in the past year')
    if q.strip():
        draft=parse_cohort_request(q)
        _ = st.markdown('### Draft interpretation')
        c1,c2,c3=st.columns(3)
        c1.metric('Age','Any' if draft['any_age'] else f"{draft['age'][0]}–{draft['age'][1]}")
        c2.metric('Sex',draft['sex']); c3.metric('Recent encounter',draft['recent'])
        _ = st.markdown('**Include**')
        if draft['include_keywords']:
            for item in draft['include_keywords']: st.markdown(f"✓ {item.title()}")
            if len(draft['include_keywords']) > 1: st.caption('All included concepts are required (AND). Cohort Builder resolves these against observed Synthea diagnosis labels.')
        else: st.caption('No supported diagnosis inclusion detected. Try a clinical diagnosis such as diabetes, hypertension, asthma, CKD, heart failure, MI, CAD, AF, cancer, anemia, osteoporosis, arthritis or dementia.')
        if draft['exclude_keywords']:
            _ = st.markdown('**Exclude**')
            for item in draft['exclude_keywords']: st.markdown(f"✓ {item.title()}")
        with st.expander('Structured draft'): st.json(draft)
        _ = st.caption('Parsed criteria: demographics + encounter recency + recognised clinical concepts. Diagnosis concepts are resolved against actual Synthea labels in Cohort Builder. Nothing is saved until you review it.')
        if st.button('Send draft to Cohort Builder',type='primary'):
            st.session_state['copilot_cohort_draft_v11']=draft; st.session_state.pop('copilot_draft_applied_v11',None)
            _ = st.success('Draft saved to this session. Open Cohort Builder to review it.')
            _ = st.page_link('pages/2_Cohort_Builder.py',label='Open Cohort Builder →')

_ = st.info('The copilot is also available in the sidebar on every page. Study answers use precomputed operational metrics; cohort drafts remain editable and are never silently saved.')
