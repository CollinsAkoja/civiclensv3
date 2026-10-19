"""CivicLens AI - Streamlit app.

Tabs: Submit (public) | Dashboard (public, aggregated) | Reviewer (password).
"""
import os
from datetime import date

import plotly.express as px
import streamlit as st

from core.analytics import (
    apply_filters, by_location, counted, headline_metrics, monthly_trend, to_frame,
)
from core.auth import verify_password
from core.db import (
    DatabaseError, add_report, init_db, list_duplicate_flags, list_reports,
    review_report, set_flag_status, set_resolution_status,
)
from core.export import to_csv_bytes
from core.llm_ollama import OllamaBackend
from core.report import generate_report
from core.schema import (
    CATEGORIES, NIGERIAN_STATES, RESOLUTION_STATUSES, ReportInput, ValidationError,
)
from core.seed import seed_demo_data
from core.service import classify_pending, process_report

st.set_page_config(page_title="CivicLens AI", page_icon="🏘️", layout="wide")
init_db()



def secret(key):
    """Read a Streamlit secret, or None if no secrets are configured."""
    try:
        return st.secrets.get(key)
    except Exception:
        return None


DEMO_MODE = os.environ.get("CIVICLENS_DEMO") == "1" or str(secret("demo_mode")).lower() in ("1", "true")
if DEMO_MODE:
    seed_demo_data()

llm = OllamaBackend()
llm_ready = llm.is_available()
backend = llm if llm_ready else None


def reviewer_password():
    return os.environ.get("CIVICLENS_REVIEWER_PASSWORD") or secret("reviewer_password")


with st.sidebar:
    st.subheader("AI status")
    if llm_ready:
        st.success(f"Language model ready: {llm.name}")
    else:
        st.warning(
            "Limited mode: the language model is not reachable, so a simple "
            f"rule-based classifier is used. Start Ollama and pull `{llm.name}` "
            "to enable AI suggestions."
        )
    st.caption("AI output is a suggestion for human review, never a verified fact.")
    if DEMO_MODE:
        st.info("Demo mode: all records are synthetic and reset when the app restarts.")

st.title("CivicLens AI")
st.caption(
    "Report local infrastructure and public service problems. "
    "Please do not include names, phone numbers or other personal details."
)

tab_submit, tab_dash, tab_review = st.tabs(["Submit a report", "Dashboard", "Reviewer"])


# ------------------------------------------------------------------ Submit
with tab_submit:
    with st.form("report_form", clear_on_submit=True):
        title = st.text_input("Issue title", max_chars=120)
        description = st.text_area(
            "Describe the problem", max_chars=2000, height=150,
            help="What is wrong, where exactly, and how long has it been this way?",
        )
        category = st.selectbox(
            "Category (optional)", ["Not sure"] + CATEGORIES,
            help="Leave as 'Not sure' and the system will suggest one.",
        )
        col1, col2, col3 = st.columns(3)
        state = col1.selectbox("State", NIGERIAN_STATES, index=NIGERIAN_STATES.index("FCT (Abuja)"))
        lga = col2.text_input("Local government area")
        community = col3.text_input("Community or neighbourhood")
        date_observed = st.date_input("Date observed", value=date.today(), max_value=date.today())
        with st.expander("Optional: approximate coordinates"):
            st.caption("Coordinates are rounded to about 110 m before saving.")
            c1, c2 = st.columns(2)
            lat_text = c1.text_input("Latitude (e.g. 9.076)")
            lon_text = c2.text_input("Longitude (e.g. 7.399)")
        submitted = st.form_submit_button("Submit report")

    if submitted:
        try:
            lat = float(lat_text) if lat_text.strip() else None
            lon = float(lon_text) if lon_text.strip() else None
            new_id = add_report(ReportInput(
                title=title, description=description, state=state, lga=lga,
                community=community, date_observed=date_observed,
                category=None if category == "Not sure" else category,
                latitude=lat, longitude=lon,
            ))
            st.success(f"Report #{new_id} saved. It is awaiting review.")
            with st.spinner("Generating AI suggestion (can take up to a minute on a laptop CPU)..."):
                result, matches = process_report(new_id, backend)
            st.info(
                f"AI-suggested category: **{result.category}** "
                f"(urgency suggestion: {result.suggested_urgency}). "
                f"Source: {result.model}. A reviewer will check this."
            )
            if matches:
                st.caption("This may be similar to an earlier report. A reviewer will check; nothing has been removed.")
        except ValueError as exc:  # ValidationError or bad coordinate text
            st.error(str(exc))
        except DatabaseError as exc:
            st.error("Sorry, the report could not be saved. Please try again.")
            st.caption(str(exc))


# --------------------------------------------------------------- Dashboard
def filter_controls(df, key):
    """Shared filter widgets. Returns (filtered_df, description_of_filters)."""
    c1, c2, c3 = st.columns(3)
    states = c1.multiselect("State", sorted(df["state"].unique()), key=f"{key}_states")
    cats = c2.multiselect("Category", sorted(df["effective_category"].unique()), key=f"{key}_cats")
    statuses = c3.multiselect("Review status", sorted(df["review_status"].unique()), key=f"{key}_status")
    dates = df["date_observed"].dropna()
    date_from = date_to = None
    if not dates.empty:
        d1, d2 = st.columns(2)
        date_from = d1.date_input("Observed from", value=dates.min().date(), key=f"{key}_from")
        date_to = d2.date_input("Observed to", value=dates.max().date(), key=f"{key}_to")
    filtered = apply_filters(df, states, cats, statuses, date_from, date_to)
    parts = []
    if states: parts.append("states: " + ", ".join(states))
    if cats: parts.append("categories: " + ", ".join(cats))
    if statuses: parts.append("review status: " + ", ".join(statuses))
    if date_from and date_to: parts.append(f"observed {date_from} to {date_to}")
    return filtered, "; ".join(parts) or "No filters applied"


with tab_dash:
    rows = list_reports()
    if not rows:
        st.info("No reports yet. Submit one in the first tab.")
    else:
        df = to_frame(rows)
        with st.expander("Filters", expanded=False):
            fdf, _ = filter_controls(df, "dash")
        flags = list_duplicate_flags("pending")
        m = headline_metrics(fdf, len(flags))

        st.markdown("#### Submitted reports (community claims, not verified facts)")
        a, b, c, d = st.columns(4)
        a.metric("Submitted", m["submitted"])
        b.metric("Awaiting review", m["awaiting_review"])
        c.metric("Reviewed", m["reviewed"])
        d.metric("Possible duplicates", m["possible_duplicates_pending"])
        st.markdown("#### Independently verified by a reviewer")
        e, f = st.columns(2)
        e.metric("Verified unresolved", m["verified_unresolved"])
        f.metric("Verified resolved", m["verified_resolved"])
        st.caption("Charts exclude rejected reports. Categories show the reviewer's choice where one exists, otherwise the reporter's or the AI suggestion.")

        left, right = st.columns(2)
        cats = counted(fdf, "effective_category")
        if not cats.empty:
            left.plotly_chart(px.bar(cats, x="reports", y="effective_category", orientation="h",
                                     title="Reports by category",
                                     labels={"effective_category": ""}), key="chart_cat")
        locs = by_location(fdf)
        if not locs.empty:
            right.plotly_chart(px.bar(locs.head(10), x="reports", y="location", orientation="h",
                                      title="Reports by LGA", labels={"location": ""}), key="chart_loc")
        trend = monthly_trend(fdf)
        if not trend.empty:
            st.plotly_chart(px.line(trend, x="month", y="reports", markers=True,
                                    title="Reports by month observed"), key="chart_trend")


# ---------------------------------------------------------------- Reviewer
def reviewer_panel():
    rows = list_reports()
    by_id = {r["id"]: r for r in rows}
    q_tab, d_tab, r_tab, x_tab = st.tabs(
        ["Review queue", "Possible duplicates", "Verification", "Export and report"])

    with q_tab:
        pending = [r for r in rows if r["review_status"] == "pending"]
        waiting = sum(1 for r in rows if r["ai_category"] is None)
        if waiting and st.button(f"Generate AI suggestions for {waiting} report(s)"):
            with st.spinner("Classifying..."):
                classify_pending(backend)
            st.rerun()
        if not pending:
            st.info("Nothing is waiting for review.")
        else:
            options = {f"#{r['id']} - {r['title']}": r["id"] for r in pending}
            report = by_id[options[st.selectbox("Report", list(options))]]
            rid = report["id"]
            st.markdown(f"**{report['title']}**")
            st.write(report["description"])
            st.caption(f"{report['community']}, {report['lga']}, {report['state']} | observed {report['date_observed']}"
                       f" | reporter category: {report['category'] or 'not given'}")
            with st.container(border=True):
                st.markdown("**AI-generated suggestion** (not verified)")
                if report["ai_category"]:
                    st.write(f"Category: {report['ai_category']} | Suggested urgency: {report['ai_urgency']} | Source: {report['ai_model']}")
                    st.write(f"Summary: {report['ai_summary']}")
                    if report["ai_uncertainty"]:
                        st.caption(f"Model note: {report['ai_uncertainty']}")
                else:
                    st.write("No AI suggestion yet.")
            b1, b2, b3 = st.columns(3)
            if b1.button("Approve AI suggestion", key=f"approve_{rid}"):
                try:
                    review_report(rid, "approve")
                    st.rerun()
                except ValidationError as exc:
                    st.error(str(exc))
            corrected = b2.selectbox("Correct category to", CATEGORIES, key=f"cat_{rid}")
            if b2.button("Save correction", key=f"correct_{rid}"):
                review_report(rid, "correct", corrected)
                st.rerun()
            if b3.button("Reject report", key=f"reject_{rid}"):
                review_report(rid, "reject")
                st.rerun()

    with d_tab:
        flags = list_duplicate_flags("pending")
        if not flags:
            st.info("No possible duplicates are waiting for review.")
        for flag in flags[:10]:
            new, old = by_id.get(flag["report_id"]), by_id.get(flag["duplicate_of_id"])
            if not new or not old:
                continue
            with st.expander(f"#{new['id']} may duplicate #{old['id']} (score {flag['score']:.2f})"):
                st.caption("Why flagged: " + "; ".join(flag["reasons"]))
                c1, c2 = st.columns(2)
                c1.markdown(f"**#{old['id']} {old['title']}**\n\n{old['description']}")
                c2.markdown(f"**#{new['id']} {new['title']}**\n\n{new['description']}")
                k1, k2 = st.columns(2)
                if k1.button("Confirm duplicate", key=f"dup_yes_{flag['id']}"):
                    set_flag_status(flag["id"], "confirmed_duplicate")
                    st.rerun()
                if k2.button("Dismiss: different issue", key=f"dup_no_{flag['id']}"):
                    set_flag_status(flag["id"], "dismissed")
                    st.rerun()

    with r_tab:
        st.warning("Only mark a report as verified when you have independent evidence "
                   "(a site visit, photographs, or an agency record). A report alone is a claim.")
        candidates = [r for r in rows if r["review_status"] in ("approved", "corrected")]
        if not candidates:
            st.info("Approve or correct a report first.")
        else:
            options = {f"#{r['id']} - {r['title']} ({r['resolution_status']})": r["id"] for r in candidates}
            rid = options[st.selectbox("Report", list(options), key="verify_pick")]
            status = st.selectbox("Verified status", RESOLUTION_STATUSES, key="verify_status")
            if st.button("Save verification status"):
                set_resolution_status(rid, status)
                st.success("Saved.")
                st.rerun()

    with x_tab:
        if not rows:
            st.info("No data to export yet.")
        else:
            df = to_frame(rows)
            fdf, filters_text = filter_controls(df, "export")
            st.write(f"{len(fdf)} report(s) match the filters.")
            st.download_button("Download CSV", to_csv_bytes(fdf), "civiclens_reports.csv", "text/csv")
            summary = generate_report(fdf, filters_text, len(list_duplicate_flags("pending")))
            st.download_button("Download community report (Markdown)", summary,
                               "civiclens_community_report.md", "text/markdown")
            with st.expander("Preview community report"):
                st.markdown(summary)


with tab_review:
    expected = reviewer_password()
    if not expected:
        st.warning("Reviewer access is switched off. Set the CIVICLENS_REVIEWER_PASSWORD "
                   "environment variable (or `reviewer_password` in Streamlit secrets) to enable it.")
    elif not st.session_state.get("reviewer_ok"):
        entered = st.text_input("Reviewer password", type="password", key="reviewer_password")
        if st.button("Log in"):
            if verify_password(entered, expected):
                st.session_state["reviewer_ok"] = True
                st.rerun()
            else:
                st.error("Incorrect password.")
    else:
        if st.button("Log out"):
            st.session_state["reviewer_ok"] = False
            st.rerun()
        reviewer_panel()
