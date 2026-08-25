import streamlit as st
import pandas as pd
from src.audit_log import read_audit, init_db
from src.branding import inject_enterprise_css

_ = st.set_page_config(page_title="Audit Log", layout="wide")
_ = st.title("Audit Log")
_ = inject_enterprise_css()
init_db()
rows = read_audit()
if not rows:
    _ = st.info("No audit records yet. Review a case first.")
else:
    df = pd.DataFrame(rows, columns=["timestamp", "case_id", "recommended_priority", "reviewer_decision", "reviewer_notes"])
    _ = st.dataframe(df, use_container_width=True)
