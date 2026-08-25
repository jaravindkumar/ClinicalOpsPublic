import json
import streamlit as st
import pandas as pd
from src.branding import inject_enterprise_css
from src.cohort_engine import list_batch_results, list_clinician_reviews

_ = st.set_page_config(page_title='MedGemma Evaluation', layout='wide')
_ = inject_enterprise_css(); _ = st.title('MedGemma Evaluation')
_ = st.caption('Evaluate real Synthea batch runs using runtime reliability, model signals and submitted clinician review. Mock-case metrics are removed.')
res=list_batch_results(); rev=list_clinician_reviews()
if res.empty: st.info('No batch results yet. Run MedGemma Batch Review first.'); st.stop()
batches=res.groupby('batch_id',as_index=False).agg(processed=('patient_id','count'),latest=('processed_at','max')).sort_values('latest',ascending=False)
batch_id=st.selectbox('Batch to evaluate', batches.batch_id.tolist(), format_func=lambda x:f"{x} · {int(batches.loc[batches.batch_id==x,'processed'].iloc[0])} patients")
df=res[res.batch_id==batch_id].copy()
# Clinical validation metrics only apply to successfully generated model outputs.
complete_ids=set(df.loc[df.status=='Complete','patient_id'].tolist())
rdf=rev[(rev.batch_id==batch_id) & (rev.patient_id.isin(complete_ids))].copy() if not rev.empty else pd.DataFrame()
completed=int((df.status=='Complete').sum()); failures=int((df.status=='Failed').sum()); completion=completed/max(len(df),1)
open_rate=float(df.loc[df.status=='Complete','open_loop'].fillna(False).mean()) if completed else 0; reviewed=len(rdf.patient_id.unique()) if not rdf.empty else 0
_ = st.markdown('### 1 · Run reliability')
c1,c2,c3,c4=st.columns(4); c1.metric('Processed',len(df)); c2.metric('Completion rate',f'{completion*100:.1f}%')
c3.metric('Failed',failures); c4.metric('Clinician review coverage',f'{reviewed}/{completed}')
if failures: st.warning(f'{failures} patient(s) failed processing. Resolve failures before interpreting cohort-level model behavior.')

_ = st.markdown('### 2 · Model signal profile')
a,b,c=st.columns(3); a.metric('Open-loop rate',f'{open_rate*100:.1f}%')
urgent=int(df.priority.fillna('').str.contains('urgent|emergency|same-day',case=False,regex=True).sum()); b.metric('Urgent / same-day',urgent)
flags=[]
for v in df.red_flags.dropna():
    try: flags += json.loads(v or '[]')
    except Exception: pass
c.metric('Red-flag mentions',len(flags))
left,right=st.columns(2)
with left:
    _ = st.markdown('**Priority distribution**'); p=df[df.status=='Complete'].priority.fillna('Not assigned').value_counts().rename_axis('Priority').reset_index(name='Patients'); st.dataframe(p,use_container_width=True,hide_index=True)
with right:
    _ = st.markdown('**Most frequent red flags**')
    f=pd.Series(flags).value_counts().head(12).rename_axis('Red flag').reset_index(name='Patients') if flags else pd.DataFrame(columns=['Red flag','Patients'])
    if f.empty: st.caption('No red flags extracted.');
    else: st.dataframe(f,use_container_width=True,hide_index=True)

_ = st.markdown('### 3 · Human validation')
if rdf.empty:
    _ = st.info('No clinician reviews submitted for this batch. Review urgent/open-loop cases plus a sample of routine cases before drawing conclusions.')
else:
    latest=rdf.sort_values('reviewed_at').drop_duplicates('patient_id',keep='last')
    decisions=latest.reviewer_decision.value_counts().rename_axis('Decision').reset_index(name='Patients')
    l,r=st.columns(2)
    with l: st.dataframe(decisions,use_container_width=True,hide_index=True)
    with r:
        accepted=int((latest.reviewer_decision=='Approve').sum()); rejected=int((latest.reviewer_decision=='Reject model output').sum()); actionable=int(latest.reviewer_decision.isin(['Needs follow-up','Escalate']).sum())
        _ = st.metric('Accepted as useful',f'{accepted}/{len(latest)}'); st.metric('Rejected model output',f'{rejected}/{len(latest)}'); st.metric('Actionable after review',f'{actionable}/{len(latest)}')

_ = st.markdown('### 4 · Decision readiness')
coverage=reviewed/max(completed,1)
if completion < .95: st.error('Not ready to scale: completion rate is below 95%.')
elif reviewed == 0: st.warning('Not ready to scale: no human validation has been submitted.')
elif coverage < .2: st.warning('Limited evidence: review coverage is below 20%. Prioritise urgent/open-loop cases and a random routine sample.')
else: st.success('This batch has sufficient operational coverage for a prototype-level assessment. Continue checking disagreement patterns before increasing batch size.')

_ = st.markdown('### Patient-level audit')
show=df[['patient_id','status','priority','open_loop','model_notes']].copy()
show['pipeline_note'] = show.apply(
    lambda r: ('Structured-output failure — re-run required' if r['status']=='Failed' else (str(r['model_notes'])[:180] if pd.notna(r['model_notes']) else '')),
    axis=1,
)
show=show.drop(columns=['model_notes'])
if not rdf.empty:
    latest=rdf.sort_values('reviewed_at').drop_duplicates('patient_id',keep='last')[['patient_id','reviewer_decision','reviewer_notes','reviewed_at']]
    show=show.merge(latest,on='patient_id',how='left')
_ = st.dataframe(show,use_container_width=True,hide_index=True)
if failures:
    with st.expander('Processing failures'):
        failed=df[df.status=='Failed'][['patient_id','model_notes']].copy()
        failed['error']=failed.model_notes.fillna('').astype(str).str.slice(0,500)
        _ = st.dataframe(failed[['patient_id','error']],use_container_width=True,hide_index=True)
