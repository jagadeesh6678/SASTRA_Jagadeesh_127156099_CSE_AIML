"""
Streamlit frontend — complete HARA guided workflow.
5 phases: Upload → Hazards → S/E/C → ASIL → Goals + Traceability
"""

import os
import json
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

# ── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="HARA Assistant",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Session State Init ────────────────────────────────────────────────────────
def init_state():
    defaults = {
        "phase": 1,
        "session_id": None,
        "system_description": "",
        "raw_hazards": [],
        "approved_hazards": [],      # list of hazard dicts after user review
        "sec_results": {},           # hazard_id → {S, E, C, rationale}
        "asil_results": {},          # hazard_id → {asil, rationale}
        "goal_results": {},          # hazard_id → {safety_goal, fsr, tsr, quality_flags}
        "req_status": {},            # hazard_id → {fsr_status, tsr_status}
        "pages_extracted": 0,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()


# ── Sidebar ───────────────────────────────────────────────────────────────────
def render_sidebar():
    with st.sidebar:
        st.title("🛡️ HARA Assistant")
        st.caption("ISO 26262 Functional Safety")
        st.divider()

        phases = [
            (1, "📄 PDF Upload"),
            (2, "⚠️ Hazard Identification"),
            (3, "📊 S / E / C Assessment"),
            (4, "🎯 ASIL Determination"),
            (5, "📋 Safety Goals & Export"),
        ]

        for num, label in phases:
            current = st.session_state.phase
            if num < current:
                st.success(f"✅ {label}")
            elif num == current:
                st.info(f"▶ {label}")
            else:
                st.markdown(f"<div style='color:gray;padding:4px 0'>🔒 {label}</div>",
                            unsafe_allow_html=True)

        st.divider()
        if st.session_state.session_id:
            st.caption(f"Session: `{st.session_state.session_id[:8]}...`")
            st.caption(f"Pages extracted: {st.session_state.pages_extracted}")
        if st.button("🔄 Reset Session", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()


# ── ASIL Badge Helper ─────────────────────────────────────────────────────────
ASIL_COLORS = {
    "QM": ("⬜", "#6c757d"),
    "A":  ("🟡", "#856404"),
    "B":  ("🟠", "#7d4e00"),
    "C":  ("🔴", "#721c24"),
    "D":  ("🔴", "#721c24"),
}

def asil_badge(level: str) -> str:
    icon, color = ASIL_COLORS.get(level, ("⬜", "#333"))
    full = f"ASIL {level}" if level != "QM" else "QM"
    return f"{icon} **{full}**"


# ── Phase 1: PDF Upload ───────────────────────────────────────────────────────
def phase_upload():
    st.header("Phase 1 — System Architecture Upload")
    st.markdown("Upload the PDF containing your system architecture, component descriptions, and design details.")

    col1, col2 = st.columns([2, 1])
    with col1:
        uploaded = st.file_uploader("Upload System Architecture PDF", type=["pdf"])
        st.session_state.system_description = st.text_area(
            "System Description",
            value=st.session_state.system_description,
            placeholder="e.g., Electric vehicle braking system with ABS and regenerative braking...",
            height=100,
        )

    with col2:
        st.info("**What to upload:**\n- System architecture documents\n- Component datasheets\n- Interface control documents\n- System design specifications")

    if uploaded and st.session_state.system_description.strip():
        if st.button("🚀 Ingest PDF & Build Knowledge Base", type="primary", use_container_width=True):
            with st.spinner("Extracting text, tables, and images from PDF..."):
                try:
                    resp = requests.post(
                        f"{BACKEND_URL}/ingest",
                        files={"file": (uploaded.name, uploaded.getvalue(), "application/pdf")},
                        timeout=240,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    st.session_state.session_id = data["session_id"]
                    st.session_state.pages_extracted = data["pages_extracted"]
                    st.success(f"✅ PDF ingested — {data['pages_extracted']} content blocks extracted.")
                    st.session_state.phase = 2
                    st.rerun()
                except requests.RequestException as e:
                    st.error(f"Backend error: {e}")
    elif uploaded and not st.session_state.system_description.strip():
        st.warning("Please provide a system description before ingesting.")


# ── Phase 2: Hazard Identification ───────────────────────────────────────────
def phase_hazards():
    st.header("Phase 2 — Hazard & Hazardous Event Identification")
    st.markdown("The AI retrieves relevant sections from your PDF and suggests hazardous events with source evidence.")

    if not st.session_state.raw_hazards:
        if st.button("🔍 Suggest Hazards from PDF", type="primary", use_container_width=True):
            with st.spinner("Retrieving context and identifying hazards..."):
                try:
                    resp = requests.post(
                        f"{BACKEND_URL}/suggest-hazards",
                        json={
                            "session_id": st.session_state.session_id,
                            "system_description": st.session_state.system_description,
                        },
                        timeout=120,
                    )
                    resp.raise_for_status()
                    st.session_state.raw_hazards = resp.json()["hazards"]
                    st.rerun()
                except requests.RequestException as e:
                    st.error(f"Error: {e}")
        return

    st.markdown(f"**{len(st.session_state.raw_hazards)} hazardous events identified.** Review each and Accept, Reject, or Edit.")

    approved = []
    for i, hazard in enumerate(st.session_state.raw_hazards):
        with st.expander(f"**{hazard.get('id', f'HE-{i+1:03d}')}** — {hazard.get('hazardous_event', '')[:80]}...", expanded=(i == 0)):
            col1, col2 = st.columns([3, 1])
            with col1:
                hazard["hazard"] = st.text_input("Hazard", value=hazard.get("hazard", ""), key=f"hz_{i}")
                hazard["hazardous_event"] = st.text_area("Hazardous Event", value=hazard.get("hazardous_event", ""), key=f"he_{i}", height=80)
                hazard["operational_situation"] = st.text_input("Operational Situation", value=hazard.get("operational_situation", ""), key=f"os_{i}")
                hazard["affected_function"] = st.text_input("Affected Function", value=hazard.get("affected_function", ""), key=f"af_{i}")
            with col2:
                st.caption("**Source Evidence**")
                st.info(hazard.get("source_evidence", "No source cited."))

            c1, c2, c3 = st.columns(3)
            action = None
            with c1:
                if st.button("✅ Accept", key=f"acc_{i}", use_container_width=True):
                    action = "accept"
            with c2:
                if st.button("❌ Reject", key=f"rej_{i}", use_container_width=True):
                    action = "reject"
            with c3:
                if st.button("💾 Accept (Edited)", key=f"edit_{i}", use_container_width=True):
                    action = "accept"

            if action == "accept":
                hazard["status"] = "accepted"
                approved.append(hazard)
            elif action == "reject":
                hazard["status"] = "rejected"

    # Persist accepted hazards
    current_accepted = [h for h in st.session_state.raw_hazards if h.get("status") == "accepted"]
    st.session_state.approved_hazards = current_accepted

    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Accepted", len(current_accepted))
    with col2:
        st.metric("Rejected", len([h for h in st.session_state.raw_hazards if h.get("status") == "rejected"]))

    if current_accepted:
        if st.button("➡️ Proceed to S/E/C Assessment", type="primary", use_container_width=True):
            st.session_state.phase = 3
            st.rerun()


# ── Phase 3: S/E/C Assessment ────────────────────────────────────────────────
def phase_sec():
    st.header("Phase 3 — Severity · Exposure · Controllability Assessment")
    st.markdown("For each approved hazardous event, review or override the AI-suggested S/E/C values.")

    for hazard in st.session_state.approved_hazards:
        hid = hazard.get("id", "HE")
        with st.expander(f"**{hid}** — {hazard.get('hazardous_event', '')[:70]}...", expanded=True):

            # Fetch suggestion if not done
            if hid not in st.session_state.sec_results:
                if st.button(f"🤖 Suggest S/E/C for {hid}", key=f"sec_fetch_{hid}"):
                    with st.spinner("Analysing..."):
                        try:
                            resp = requests.post(
                                f"{BACKEND_URL}/suggest-sec",
                                json={
                                    "session_id": st.session_state.session_id,
                                    "hazardous_event": hazard["hazardous_event"],
                                    "operational_situation": hazard["operational_situation"],
                                },
                                timeout=60,
                            )
                            resp.raise_for_status()
                            st.session_state.sec_results[hid] = resp.json()
                            st.rerun()
                        except requests.RequestException as e:
                            st.error(str(e))
                continue

            sec = st.session_state.sec_results[hid]
            col1, col2, col3 = st.columns(3)

            with col1:
                st.caption(f"AI suggests: **{sec.get('S','S?')}**")
                st.caption(f"*{sec.get('S_rationale','')}*")
                sec["S"] = st.selectbox("Severity (S)", ["S0","S1","S2","S3"],
                    index=["S0","S1","S2","S3"].index(sec.get("S","S0")), key=f"S_{hid}")
            with col2:
                st.caption(f"AI suggests: **{sec.get('E','E?')}**")
                st.caption(f"*{sec.get('E_rationale','')}*")
                sec["E"] = st.selectbox("Exposure (E)", ["E0","E1","E2","E3","E4"],
                    index=["E0","E1","E2","E3","E4"].index(sec.get("E","E0")), key=f"E_{hid}")
            with col3:
                st.caption(f"AI suggests: **{sec.get('C','C?')}**")
                st.caption(f"*{sec.get('C_rationale','')}*")
                sec["C"] = st.selectbox("Controllability (C)", ["C0","C1","C2","C3"],
                    index=["C0","C1","C2","C3"].index(sec.get("C","C0")), key=f"C_{hid}")

            st.session_state.sec_results[hid] = sec

    all_sec_done = all(h.get("id") in st.session_state.sec_results
                       for h in st.session_state.approved_hazards)

    if all_sec_done and st.session_state.approved_hazards:
        if st.button("➡️ Proceed to ASIL Determination", type="primary", use_container_width=True):
            st.session_state.phase = 4
            st.rerun()


# ── Phase 4: ASIL Determination ──────────────────────────────────────────────
def phase_asil():
    st.header("Phase 4 — ASIL Determination")
    st.markdown("ASIL computed deterministically per **ISO 26262-3 Table 4** — no LLM involved.")

    for hazard in st.session_state.approved_hazards:
        hid = hazard.get("id", "HE")
        sec = st.session_state.sec_results.get(hid, {})

        with st.container():
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.markdown(f"**{hid}** — {hazard.get('hazardous_event','')[:80]}")

            if hid not in st.session_state.asil_results:
                with col3:
                    if st.button("Compute ASIL", key=f"asil_{hid}"):
                        try:
                            resp = requests.post(
                                f"{BACKEND_URL}/compute-asil",
                                json={"S": sec["S"], "E": sec["E"], "C": sec["C"]},
                                timeout=30,
                            )
                            resp.raise_for_status()
                            st.session_state.asil_results[hid] = resp.json()
                            st.rerun()
                        except requests.RequestException as e:
                            st.error(str(e))
            else:
                result = st.session_state.asil_results[hid]
                level = result.get("asil", "QM")
                with col2:
                    st.markdown(asil_badge(level))
                with st.expander("View ISO 26262 Rationale"):
                    st.markdown(result.get("rationale", ""))

            st.divider()

    all_asil_done = all(h.get("id") in st.session_state.asil_results
                        for h in st.session_state.approved_hazards)

    if all_asil_done and st.session_state.approved_hazards:
        if st.button("➡️ Proceed to Safety Goals", type="primary", use_container_width=True):
            st.session_state.phase = 5
            st.rerun()


# ── Phase 5: Safety Goals & Traceability Export ───────────────────────────────
def phase_goals():
    st.header("Phase 5 — Safety Goals, FSRs & TSRs")

    for hazard in st.session_state.approved_hazards:
        hid = hazard.get("id", "HE")
        asil_data = st.session_state.asil_results.get(hid, {})
        asil_label = asil_data.get("asil_full", asil_data.get("asil", "QM"))

        with st.expander(f"**{hid}** [{asil_badge(asil_data.get('asil','QM'))}] — {hazard.get('hazardous_event','')[:60]}...", expanded=True):

            if hid not in st.session_state.goal_results:
                if st.button(f"📝 Draft Goals for {hid}", key=f"goal_fetch_{hid}"):
                    with st.spinner("Drafting safety goals..."):
                        try:
                            resp = requests.post(
                                f"{BACKEND_URL}/draft-goals",
                                json={
                                    "session_id": st.session_state.session_id,
                                    "hazardous_event": hazard["hazardous_event"],
                                    "asil": asil_label,
                                    "affected_function": hazard.get("affected_function", ""),
                                },
                                timeout=90,
                            )
                            resp.raise_for_status()
                            result = resp.json()
                            st.session_state.goal_results[hid] = result
                            st.session_state.req_status[hid] = {"fsr_status": "Pending", "tsr_status": "Pending"}
                            st.rerun()
                        except requests.RequestException as e:
                            st.error(str(e))
                continue

            goals = st.session_state.goal_results[hid]

            # Quality flags warning
            flags = goals.get("quality_flags", [])
            if flags:
                for flag in flags:
                    st.warning(f"⚠️ Quality flag: {flag}")

            goals["safety_goal"] = st.text_area("Safety Goal (SG)", value=goals.get("safety_goal",""), key=f"sg_{hid}", height=80)
            goals["fsr"] = st.text_area("Functional Safety Requirement (FSR)", value=goals.get("fsr",""), key=f"fsr_{hid}", height=100)
            goals["tsr"] = st.text_area("Technical Safety Requirement (TSR)", value=goals.get("tsr",""), key=f"tsr_{hid}", height=100)

            st.session_state.goal_results[hid] = goals

            # Approve/Reject FSR & TSR
            status = st.session_state.req_status.get(hid, {"fsr_status":"Pending","tsr_status":"Pending"})
            col1, col2 = st.columns(2)
            with col1:
                st.caption("FSR Status")
                c1, c2, c3 = st.columns(3)
                with c1:
                    if st.button("✅", key=f"fsr_acc_{hid}", help="Approve FSR"):
                        status["fsr_status"] = "Approved"
                with c2:
                    if st.button("❌", key=f"fsr_rej_{hid}", help="Reject FSR"):
                        status["fsr_status"] = "Rejected"
                with c3:
                    if st.button("✏️", key=f"fsr_edit_{hid}", help="Mark as Edited"):
                        status["fsr_status"] = "Edited"
                st.markdown(f"Status: **{status['fsr_status']}**")
            with col2:
                st.caption("TSR Status")
                c1, c2, c3 = st.columns(3)
                with c1:
                    if st.button("✅", key=f"tsr_acc_{hid}", help="Approve TSR"):
                        status["tsr_status"] = "Approved"
                with c2:
                    if st.button("❌", key=f"tsr_rej_{hid}", help="Reject TSR"):
                        status["tsr_status"] = "Rejected"
                with c3:
                    if st.button("✏️", key=f"tsr_edit_{hid}", help="Mark as Edited"):
                        status["tsr_status"] = "Edited"
                st.markdown(f"Status: **{status['tsr_status']}**")

            st.session_state.req_status[hid] = status

    # ── Export Section ─────────────────────────────────────────────────────
    st.divider()
    st.subheader("📊 Traceability Matrix Export")

    all_goals_done = all(
        h.get("id") in st.session_state.goal_results
        for h in st.session_state.approved_hazards
    )

    if not all_goals_done:
        st.info("Draft goals for all approved hazards to enable export.")
        return

    if st.button("📥 Generate & Download Traceability Matrix (Excel)", type="primary", use_container_width=True):
        rows = []
        for hazard in st.session_state.approved_hazards:
            hid = hazard.get("id", "HE")
            sec = st.session_state.sec_results.get(hid, {})
            asil_data = st.session_state.asil_results.get(hid, {})
            goals = st.session_state.goal_results.get(hid, {})
            status = st.session_state.req_status.get(hid, {})

            rows.append({
                "id": hid,
                "hazard": hazard.get("hazard", ""),
                "hazardous_event": hazard.get("hazardous_event", ""),
                "operational_situation": hazard.get("operational_situation", ""),
                "affected_function": hazard.get("affected_function", ""),
                "source_evidence": hazard.get("source_evidence", ""),
                "S": sec.get("S", ""),
                "E": sec.get("E", ""),
                "C": sec.get("C", ""),
                "asil": asil_data.get("asil_full", ""),
                "safety_goal": goals.get("safety_goal", ""),
                "fsr": goals.get("fsr", ""),
                "tsr": goals.get("tsr", ""),
                "fsr_status": status.get("fsr_status", "Pending"),
                "tsr_status": status.get("tsr_status", "Pending"),
            })

        try:
            resp = requests.post(
                f"{BACKEND_URL}/export-traceability",
                json={"rows": rows},
                timeout=60,
            )
            resp.raise_for_status()
            st.download_button(
                label="⬇️ Download Excel File",
                data=resp.content,
                file_name="HARA_Traceability_Matrix.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        except requests.RequestException as e:
            st.error(f"Export failed: {e}")


# ── Main Router ───────────────────────────────────────────────────────────────
def main():
    render_sidebar()
    phase = st.session_state.phase

    if phase == 1:
        phase_upload()
    elif phase == 2:
        phase_hazards()
    elif phase == 3:
        phase_sec()
    elif phase == 4:
        phase_asil()
    elif phase == 5:
        phase_goals()


if __name__ == "__main__":
    main()