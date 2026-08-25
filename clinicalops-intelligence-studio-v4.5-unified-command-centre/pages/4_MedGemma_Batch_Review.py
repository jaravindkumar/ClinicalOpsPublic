import time
import streamlit as st
import pandas as pd
from src.branding import inject_enterprise_css
from src.cohort_engine import list_cohorts, cohort_members
from src.trial_ops import DEFAULT_SYNTHEA_DIR, synthea_status
from src.medgemma_client import DEFAULT_OLLAMA_MODEL
from src.batch_jobs import start_batch, recent_jobs, active_jobs, request_cancel

_ = st.set_page_config(page_title='MedGemma Batch Review', layout='wide')
_ = inject_enterprise_css()
_ = st.title('MedGemma Batch Review')
_ = st.caption('Choose a clinically meaningful subset of a saved cohort, then run local MedGemma. Processing continues when you navigate to another page.')

with st.sidebar:
    root = st.text_input('Synthea CSV directory', DEFAULT_SYNTHEA_DIR)
    model = st.text_input('Ollama MedGemma model', DEFAULT_OLLAMA_MODEL)
    if synthea_status(root)['ready']:
        _ = st.success('Synthea connected')
    else:
        _ = st.error('Synthea unavailable')

coh = list_cohorts()
if coh.empty:
    _ = st.info('Build and save a cohort first.')
    _ = st.stop()

cid = st.selectbox(
    'Cohort',
    coh.cohort_id.tolist(),
    format_func=lambda x: f"{coh.loc[coh.cohort_id == x, 'name'].iloc[0]} · {coh.loc[coh.cohort_id == x, 'patient_count'].iloc[0]:,} patients",
)
members = cohort_members(cid)
if members.empty:
    _ = st.warning('This cohort has no patients.')
    _ = st.stop()

_ = st.markdown('### Select patients for this MedGemma run')
left, mid, right = st.columns(3)
min_age = int(members.age.min())
max_age = int(members.age.max())
if min_age < max_age:
    age = left.slider('Age', min_age, max_age, (min_age, max_age))
else:
    left.metric('Age', f'{min_age} years')
    left.caption('All patients in this cohort have the same age, so no age filter is needed.')
    age = (min_age, max_age)
sex = mid.selectbox('Sex', ['Any', 'Female', 'Male'])
strategy = right.selectbox('Selection strategy', ['All matching patients', 'Random sample', 'Oldest patients', 'Youngest patients'])

eligible = members[(members.age >= age[0]) & (members.age <= age[1])].copy()
if sex != 'Any':
    eligible = eligible[eligible.sex.str.upper().str.startswith(sex[0], na=False)]

_ = st.metric('Patients matching batch filters', f'{len(eligible):,}')
if eligible.empty:
    _ = st.warning('No patients match these batch filters.')
    _ = st.stop()

if strategy == 'All matching patients':
    selected = eligible.copy()
else:
    size_options = [n for n in [5, 10, 15, 25, 50, 100] if n <= len(eligible)]
    if len(eligible) not in size_options:
        size_options.append(len(eligible))
    n = st.selectbox('Maximum patients to process', size_options, index=0, format_func=lambda x: f'{x:,} patients')
    if strategy == 'Random sample':
        seed = st.number_input('Sampling seed', min_value=0, value=42, step=1, help='Keeps the random sample reproducible for evaluation.')
        selected = eligible.sample(n=n, random_state=int(seed))
    elif strategy == 'Oldest patients':
        selected = eligible.sort_values(['age', 'patient_id'], ascending=[False, True]).head(n)
    else:
        selected = eligible.sort_values(['age', 'patient_id'], ascending=[True, True]).head(n)

n_selected = len(selected)
_ = st.caption(f'{n_selected:,} patients will be processed. Local MedGemma runs one patient at a time; the first result can take a minute or more depending on your Mac.')
_ = st.dataframe(selected[['patient_id', 'age', 'sex', 'city', 'state']].head(100), use_container_width=True, hide_index=True)

running = active_jobs()
if running:
    j = running[0]
    _ = st.info(
        f"{j.get('batch_id')} is already {j.get('status','running').lower()}: "
        f"{j.get('stage','processing')} · {j.get('processed',0)}/{j.get('total',0)} complete. "
        "A second batch is disabled so it does not sit invisibly in a queue."
    )
    b1, b2 = st.columns([1, 4])
    if b1.button('Request cancellation', type='secondary'):
        request_cancel(j.get('batch_id'))
        _ = st.warning('Cancellation requested. The current MedGemma inference must finish before the worker can stop.')
else:
    if st.button(f'Run MedGemma on {n_selected:,} selected patients', type='primary'):
        try:
            batch = start_batch(cid, selected.reset_index(drop=True), root, model)
            st.session_state['latest_batch_id'] = batch
            _ = st.success(f'{batch} started in the background. You can move to any other page; processing will continue.')
            _ = st.info('The activity panel below refreshes automatically every 2 seconds.')
        except RuntimeError as exc:
            _ = st.warning(str(exc))

_ = st.markdown('### Batch activity')

@st.fragment(run_every=2)
def live_batch_activity():
    jobs = recent_jobs(6)
    if not jobs:
        _ = st.caption('No batches have been run yet.')
        return
    for j in jobs:
        processed = int(j.get('processed', 0) or 0)
        total = int(j.get('total', 0) or 0)
        pct = int(100 * processed / max(1, total))
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([2.4, 1, 1, 1])
            c1.markdown(f"**{j.get('batch_id')}**")
            c1.caption(j.get('stage') or j.get('status') or '')
            if j.get('current_patient'):
                c1.caption(f"Current patient: {j.get('current_patient')}")
            if j.get('last_patient_seconds') is not None:
                c1.caption(f"Last MedGemma inference: {j.get('last_patient_seconds')} s")
            c2.metric('Progress', f'{processed}/{total}')
            c3.metric('Failed', int(j.get('failed', 0) or 0))
            c4.metric('Complete', f'{pct}%')
            _ = st.progress(min(1.0, max(0.0, pct / 100)))
            if j.get('status') == 'Queued':
                _ = st.caption('Queued jobs start automatically after the active local MedGemma job finishes.')
            if j.get('status') == 'Interrupted':
                _ = st.warning(j.get('error') or 'This batch was interrupted by an app restart.')
            elif j.get('error'):
                _ = st.error(j['error'])

live_batch_activity()

_ = st.caption('The page auto-refreshes the batch status. Navigating between pages does not cancel an active run. Stopping the Streamlit/Python process or Ollama will stop inference.')
