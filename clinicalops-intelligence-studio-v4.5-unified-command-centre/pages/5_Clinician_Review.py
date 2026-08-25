import json
import streamlit as st
import pandas as pd
from src.branding import inject_enterprise_css
from src.ui_helpers import chips
from src.cohort_engine import list_batch_results, list_clinician_reviews, save_clinician_review
from src.synthea_patient import get_patient_snapshot
from src.trial_ops import DEFAULT_SYNTHEA_DIR

_ = st.set_page_config(page_title='Clinician Review', layout='wide')
_ = inject_enterprise_css()
_ = st.title('Clinician Review')
_ = st.caption('Inspect the source patient record and MedGemma assessment side-by-side, then submit a traceable human decision.')

with st.sidebar:
    root=st.text_input('Synthea CSV directory', DEFAULT_SYNTHEA_DIR)

results=list_batch_results()
if results.empty:
    _ = st.info('No MedGemma batch results yet. Run MedGemma Batch Review first.')
    _ = st.stop()

batch_ids=results.batch_id.drop_duplicates().tolist()
preferred=st.session_state.get('latest_batch_id')
default_idx=batch_ids.index(preferred) if preferred in batch_ids else 0
batch_id=st.selectbox('Batch', batch_ids, index=default_idx)
batch=results[results.batch_id==batch_id].copy()
completed=int((batch.status=='Complete').sum()); open_loops=int(batch.open_loop.fillna(False).sum())
urgent=int(batch.priority.fillna('').str.contains('urgent|emergency|same-day', case=False, regex=True).sum())
c1,c2,c3,c4=st.columns(4)
c1.metric('Patients', f'{len(batch):,}'); c2.metric('Completed', f'{completed:,}')
c3.metric('Open loops', f'{open_loops:,}'); c4.metric('Urgent / same-day', f'{urgent:,}')

f1,f2,f3=st.columns(3)
status=f1.selectbox('Status', ['Any']+sorted(batch.status.dropna().unique().tolist()))
priority=f2.selectbox('Priority', ['Any']+sorted([x for x in batch.priority.dropna().unique().tolist() if x]))
loop=f3.selectbox('Open loop', ['Any','Yes','No'])
view=batch.copy()
if status!='Any': view=view[view.status==status]
if priority!='Any': view=view[view.priority==priority]
if loop=='Yes': view=view[view.open_loop==True]
elif loop=='No': view=view[view.open_loop==False]

reviews=list_clinician_reviews()
reviewed=set(reviews[reviews.batch_id==batch_id].patient_id.tolist()) if not reviews.empty else set()
view['reviewed']=view.patient_id.isin(reviewed)
_ = st.markdown('### Review queue')
_ = st.dataframe(view[['patient_id','status','priority','open_loop','reviewed']], use_container_width=True, hide_index=True)
if view.empty: st.stop()
patient_id=st.selectbox('Patient to review', view.patient_id.tolist())
row=view[view.patient_id==patient_id].iloc[0]

try:
    snap=get_patient_snapshot(patient_id, root)
except Exception as e:
    _ = st.error(f'Could not load Synthea patient record: {e}'); snap=None

_ = st.markdown('---'); st.markdown('## Patient context')
if snap:
    d=snap['demographics']; a,b,c,dcol=st.columns(4)
    a.metric('Patient ID', str(d['patient_id'])[:12]+'…'); b.metric('Age', d['age'] if d['age'] is not None else '—')
    c.metric('Sex', d['sex'] or '—'); dcol.metric('Location', f"{d['city']}, {d['state']}")
    _ = st.caption(f"Race: {d['race']} · Ethnicity: {d['ethnicity']}")
    t1,t2,t3,t4,t5=st.tabs(['Conditions','Observations','Medications','Encounters','Procedures'])
    with t1: st.dataframe(snap['conditions'], use_container_width=True, hide_index=True)
    with t2: st.dataframe(snap['observations'], use_container_width=True, hide_index=True)
    with t3: st.dataframe(snap['medications'], use_container_width=True, hide_index=True)
    with t4: st.dataframe(snap['encounters'], use_container_width=True, hide_index=True)
    with t5: st.dataframe(snap['procedures'], use_container_width=True, hide_index=True)

_ = st.markdown('## MedGemma assessment')
if row.status=='Failed':
    _ = st.error('MedGemma processing failed for this patient.'); st.code(str(row.model_notes or 'Unknown error'))
else:
    m1,m2,m3=st.columns(3); m1.metric('Priority', row.priority or 'Not assigned')
    m2.metric('Open loop', 'Yes' if bool(row.open_loop) else 'No'); m3.metric('Clinical question', row.clinical_question or 'Not identified')
    def loads(v):
        try: return json.loads(v or '[]')
        except Exception: return []
    red=loads(row.red_flags); missing=loads(row.missing_information); symptoms=loads(row.symptoms)
    ordered=loads(row.ordered_tests); missing_results=loads(row.missing_results); received=loads(row.received_results)
    l,r=st.columns(2)
    with l:
        _ = st.markdown('#### Red flags'); chips(red, empty_text='None identified')
        _ = st.markdown('#### Symptoms / signals'); chips(symptoms, empty_text='None extracted')
        _ = st.markdown('#### Ordered tests'); chips(ordered, empty_text='None extracted')
    with r:
        _ = st.markdown('#### Missing information'); chips(missing, empty_text='None identified')
        _ = st.markdown('#### Missing results'); chips(missing_results, empty_text='None identified')
        _ = st.markdown('#### Received results')
        if received: st.dataframe(pd.DataFrame(received), use_container_width=True, hide_index=True)
        else: st.caption('None extracted')
    if row.model_notes:
        with st.expander('MedGemma model notes'): st.write(row.model_notes)
    with st.expander('Exact clinical packet sent to MedGemma'):
        _ = st.text(row.clinical_text or 'Not stored for this older batch. Re-run this patient/batch with v1.0 to capture the exact packet.')

_ = st.markdown('---'); st.markdown('## Human decision')
if row.status == 'Failed':
    _ = st.warning('No clinical approval can be submitted because MedGemma did not produce a valid assessment for this patient.')
    _ = st.caption('Re-run this patient in MedGemma Batch Review. Failed model execution is tracked as a pipeline-quality event, not as a clinical decision.')
else:
    prior=reviews[(reviews.batch_id==batch_id)&(reviews.patient_id==patient_id)] if not reviews.empty else pd.DataFrame()
    if not prior.empty:
        last=prior.sort_values('reviewed_at').iloc[-1]; st.info(f"Previously submitted: {last.reviewer_decision} · {last.reviewed_at}")
    decision=st.radio('Reviewer decision', ['Approve','Needs follow-up','Escalate','Reject model output'], horizontal=True, key=f'dec_{batch_id}_{patient_id}')
    notes=st.text_area('Clinical review notes', placeholder='Why do you agree/disagree? What evidence matters? What follow-up is required?', height=130, key=f'note_{batch_id}_{patient_id}')
    confirm=st.checkbox('I have reviewed the patient context and MedGemma assessment.', key=f'confirm_{batch_id}_{patient_id}')
    if st.button('Submit clinical review', type='primary', disabled=not confirm):
        rid=save_clinician_review(batch_id, row.cohort_id, patient_id, decision, notes, row.priority, row.open_loop)
        _ = st.success(f'Review submitted · {rid}'); st.rerun()
