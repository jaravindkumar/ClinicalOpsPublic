import hashlib
import streamlit as st
from src.branding import inject_enterprise_css, hero
from src.trial_ops import DEFAULT_SYNTHEA_DIR, synthea_status
from src.cohort_engine import filter_population, condition_catalog, observation_catalog, save_cohort

_ = st.set_page_config(page_title="Cohort Builder", layout="wide")
_ = inject_enterprise_css()
_ = hero("Cohort Builder", "Turn the Synthea population into a reusable, auditable trial candidate cohort using explicit inclusion and exclusion criteria.", "Population → protocol cohort")

with st.sidebar:
    root = st.text_input("Synthea CSV directory", DEFAULT_SYNTHEA_DIR, key="cohort_root_v11")
    status = synthea_status(root)
    _ = st.success("Synthea connected") if status["ready"] else st.error("Synthea unavailable")
if not status["ready"]: st.stop()

catalog = condition_catalog(root); category_names=list(catalog.keys())
INC_STATE="cohort_include_selected_v11"; EXC_STATE="cohort_exclude_selected_v11"
_ = st.session_state.setdefault(INC_STATE,[]); st.session_state.setdefault(EXC_STATE,[])

def _short_hash(text): return hashlib.md5(text.encode()).hexdigest()[:10]
def _remove(state_key, condition): st.session_state[state_key]=[x for x in st.session_state[state_key] if x!=condition]
def _find_matches(keywords):
    out=[]
    for kw in keywords:
        kw=kw.lower()
        candidates=[]
        for rows in catalog.values():
            candidates.extend([r['description'] for r in rows if kw in r['description'].lower()])
        if candidates: out.append(candidates[0])
    return list(dict.fromkeys(out))

# Apply a chat-created draft once, but keep it explicitly editable.
draft=st.session_state.get("copilot_cohort_draft_v11")
if draft and not st.session_state.get("copilot_draft_applied_v11"):
    st.session_state["cohort_name_v11"]=draft.get("name","")
    st.session_state["cohort_any_age_v11"]=draft.get("any_age",True)
    st.session_state["cohort_age_range_v11"]=tuple(draft.get("age",(40,75)))
    st.session_state["cohort_sex_v11"]=draft.get("sex","Any")
    st.session_state["cohort_recent_v11"]=draft.get("recent","Any time")
    st.session_state[INC_STATE]=_find_matches(draft.get("include_keywords",[]))
    st.session_state[EXC_STATE]=_find_matches(draft.get("exclude_keywords",[]))
    st.session_state["inc_logic_v11"]="ALL selected (AND)" if draft.get("include_logic","AND")=="AND" else "ANY selected (OR)"
    st.session_state["exc_logic_v11"]="ALL selected (AND)" if draft.get("exclude_logic","OR")=="AND" else "ANY selected (OR)"
    st.session_state["copilot_draft_applied_v11"]=True
    _ = st.success("Copilot criteria applied. Review the criteria and enter your own cohort name before saving.")

def picker(title,state_key,prefix):
    selected=list(st.session_state[state_key])
    _ = st.markdown(f"#### {title}")
    if selected:
        with st.container(border=True):
            _ = st.caption(f"{len(selected)} active diagnosis criterion/criteria")
            for condition in selected:
                c1,c2=st.columns([7,1]); c1.markdown(f"**✓ {condition}**")
                if c2.button("Remove",key=f"{prefix}_rm_{_short_hash(condition)}",use_container_width=True):
                    _remove(state_key,condition); st.rerun()
    else: st.info("No diagnosis restriction is active.")
    category=st.selectbox("Clinical area",category_names,key=f"{prefix}_category_v11")
    rows=catalog.get(category,[])
    with st.container(border=True):
        _ = st.caption(f"Select diagnoses from {category}. Checked items are immediately added to the active criteria above.")
        for i in range(0,len(rows),2):
            cols=st.columns(2)
            for j,col in enumerate(cols):
                idx=i+j
                if idx>=len(rows): continue
                item=rows[idx]; cond=item['description']; checked=cond in st.session_state[state_key]
                nv=col.checkbox(f"{cond} · {item['count']:,} records",value=checked,key=f"{prefix}_{_short_hash(cond)}")
                current=list(st.session_state[state_key])
                if nv and cond not in current: st.session_state[state_key]=current+[cond]
                elif (not nv) and cond in current: st.session_state[state_key]=[x for x in current if x!=cond]
    return list(st.session_state[state_key])

name=st.text_input("Cohort name",placeholder="e.g. T2DM Phase III candidate population",key="cohort_name_v11")
_ = st.markdown("## 1 · Demographic & activity criteria")
a,b,c=st.columns(3)
any_age=a.checkbox("Any age",value=True,key="cohort_any_age_v11")
if any_age: age=(0,120); a.caption("No age restriction")
else: age=a.slider("Age range",0,120,(40,75),key="cohort_age_range_v11")
sex=b.selectbox("Sex",["Any","Female","Male"],key="cohort_sex_v11")
recent=c.selectbox("Recent encounter",["Any time","≤ 1 year","≤ 3 years","≤ 5 years","≤ 10 years"],key="cohort_recent_v11")
years={"Any time":0,"≤ 1 year":1,"≤ 3 years":3,"≤ 5 years":5,"≤ 10 years":10}[recent]

_ = st.markdown("## 2 · Diagnosis criteria")
inc,exc=st.columns(2)
with inc:
    include_conditions=picker("Include diagnoses",INC_STATE,"inc_v11")
    include_logic_value="OR"
    if len(include_conditions)>1:
        logic=st.radio("Match",["ANY selected (OR)","ALL selected (AND)"],horizontal=True,key="inc_logic_v11")
        include_logic_value="OR" if logic.startswith("ANY") else "AND"
with exc:
    exclude_conditions=picker("Exclude diagnoses",EXC_STATE,"exc_v11")
    exclude_logic_value="OR"
    if len(exclude_conditions)>1:
        logic=st.radio("Exclude if",["ANY selected (OR)","ALL selected (AND)"],horizontal=True,key="exc_logic_v11")
        exclude_logic_value="OR" if logic.startswith("ANY") else "AND"

_ = st.markdown("## 3 · Optional measurable criterion")
obs=observation_catalog(root)
use_obs=st.checkbox("Add a numeric observation/lab threshold",value=False,key="use_obs_v11")
obs_desc=""; obs_op=">="; obs_val=None
if use_obs and not obs.empty:
    o1,o2,o3=st.columns([2,1,1])
    labels=[f"{r.DESCRIPTION} ({r.units or 'unit not recorded'})" for r in obs.itertuples(index=False)]
    label=o1.selectbox("Observation / lab",labels,key="obs_desc_v11")
    idx=labels.index(label); obs_desc=str(obs.iloc[idx]['DESCRIPTION'])
    obs_op=o2.selectbox("Operator",[">=",">","<=","<","="],key="obs_op_v11")
    obs_val=o3.number_input("Value",value=0.0,step=0.1,key="obs_val_v11")
    _ = st.caption("This criterion is evaluated deterministically from numeric Synthea observations. MedGemma is reserved for interpretation/ambiguity, not basic arithmetic.")

base=filter_population(root,0,120,"Any","","",0)
a1=filter_population(root,*age,sex,"","",years)
a2=filter_population(root,*age,sex,"","",years,include_conditions=include_conditions,include_logic=include_logic_value,
                     observation_description=obs_desc,observation_operator=obs_op,observation_value=obs_val)
a3=filter_population(root,*age,sex,"","",years,include_conditions=include_conditions,exclude_conditions=exclude_conditions,
                     include_logic=include_logic_value,exclude_logic=exclude_logic_value,
                     observation_description=obs_desc,observation_operator=obs_op,observation_value=obs_val)

_ = st.markdown("## Cohort funnel")
cols=st.columns(4)
for col,label,n in zip(cols,["Source population","Demographic/activity","Clinical inclusion","Final cohort"],[len(base),len(a1),len(a2),len(a3)]): col.metric(label,f"{n:,}")
retention=100*len(a3)/max(1,len(base)); st.progress(min(1.0,retention/100)); st.caption(f"Final cohort: {len(a3):,} patients ({retention:.1f}% of source population).")

with st.expander("Review active cohort definition",expanded=True):
    _ = st.write({"age":"Any" if any_age else age,"sex":sex,"recent encounter":recent,
              "include diagnoses":include_conditions or "Any","include logic":include_logic_value,
              "exclude diagnoses":exclude_conditions or "None","exclude logic":exclude_logic_value,
              "numeric criterion":None if not use_obs else f"{obs_desc} {obs_op} {obs_val}"})

_ = st.markdown("### Preview")
_ = st.dataframe(a3.head(250),use_container_width=True,hide_index=True)
if len(a3)>250: st.caption(f"Showing 250 of {len(a3):,} matching patients.")

c1,c2=st.columns([1,3])
if c1.button("Save cohort",type="primary",disabled=not name.strip()):
    criteria={"age":"Any" if any_age else list(age),"sex":sex,"recent_years":years,
              "include_conditions":include_conditions,"include_logic":include_logic_value,
              "exclude_conditions":exclude_conditions,"exclude_logic":exclude_logic_value,
              "observation_description":obs_desc,"observation_operator":obs_op,"observation_value":obs_val}
    cid=save_cohort(name.strip(),criteria,a3); st.success(f"Saved {cid} with {len(a3):,} patients.")
c2.caption("Next: run MedGemma on the saved cohort, review exceptions, then assign validated subjects into trial operations.")
