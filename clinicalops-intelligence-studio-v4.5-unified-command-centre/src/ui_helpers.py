import streamlit as st


def priority_banner(priority: str):
    p = (priority or "").lower()
    if "emergency" in p:
        _ = st.error(f"🚨 {priority}")
    elif "urgent" in p or "same-day" in p:
        _ = st.warning(f"⚠️ {priority}")
    elif "follow-up" in p or "review" in p:
        _ = st.info(f"🔎 {priority}")
    else:
        _ = st.success(f"✅ {priority}")


def chips(items, empty_text="None detected"):
    if not items:
        _ = st.caption(empty_text)
        return
    html = " ".join(
        [
            f"<span style='display:inline-block;padding:4px 8px;margin:3px;border-radius:999px;"
            f"background:#EAF2F8;color:#0B3658;font-size:0.85rem;'>{str(x)}</span>"
            for x in items
        ]
    )
    _ = st.markdown(html, unsafe_allow_html=True)


def metric_card(label, value):
    _ = st.markdown(
        f"""
        <div style="padding:12px 14px;border:1px solid #D6E3EE;border-radius:12px;background:#FAFCFE;">
          <div style="font-size:0.78rem;color:#455868;margin-bottom:4px;">{label}</div>
          <div style="font-size:1.05rem;font-weight:700;color:#0B3658;">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def insight_box(title: str, body: str, tone: str = "info"):
    colors = {
        "info": ("#EAF2F8", "#0B3658", "#A8BED2"),
        "warning": ("#FFF8E5", "#6B5200", "#E4C766"),
        "success": ("#EAF7EF", "#145A32", "#9DD7B5"),
        "danger": ("#FDECEC", "#7B241C", "#E6A0A0"),
    }
    bg, fg, border = colors.get(tone, colors["info"])
    _ = st.markdown(
        f"""
        <div style="padding:14px 16px;border:1px solid {border};border-radius:12px;background:{bg};margin:8px 0 12px 0;">
          <div style="font-weight:700;color:{fg};font-size:1rem;margin-bottom:5px;">{title}</div>
          <div style="color:{fg};font-size:0.92rem;line-height:1.45;">{body}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
