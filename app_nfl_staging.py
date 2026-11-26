"""Isolated Streamlit NFL import preview, not the production entry point."""
import json
import pandas as pd
import streamlit as st
from nfl_daily_audit import audit_nfl_daily
from nfl_reviewed_candidates import compare_reviewed_nfl
from nfl_projection_review import review_nfl_projections
from research_source_registry import research_checklist

st.set_page_config(page_title="DFS Model 2.0 NFL staging",layout="centered")
st.title("DFS Model 2.0 — NFL import staging")
st.warning("Read-only coverage audit. No certified lineup, live status check, or scoring promotion.")
with st.expander("Complete NFL research checklist"):
    st.dataframe(research_checklist("NFL"),hide_index=True)
mode=st.radio("Contest format",("Classic","Single game"))
contest_id=st.text_input("Exact FanDuel contest ID")
contest=st.file_uploader("Original FanDuel contest CSV",type=["csv"])
daily=st.file_uploader("Original DAILY projection CSV",type=["csv"])
if contest and daily and contest_id:
    try:
        report=audit_nfl_daily(contest.getvalue(),daily.getvalue(),contest_id=contest_id,
                              single_game=mode=="Single game")
    except (ValueError, UnicodeError) as exc:
        st.error(str(exc))
    else:
        st.metric("Contest players",report["contest_players"])
        st.metric("Matched identities",report["matched"])
        st.metric("Eligible header-labeled scores",report["eligible_header_scores"])
        st.metric("Eligible unlabeled score candidates",report["eligible_unlabeled_candidates"])
        st.warning(report["warning"])
        st.dataframe(pd.DataFrame(report["players"]),hide_index=True)
        st.download_button("Download coverage audit",json.dumps(report,indent=2),
                           file_name="nfl_coverage_audit.json",mime="application/json")

        with st.expander("Independent projection review (advisory)"):
            st.caption("Upload reviewer-verified source records in JSON. No score will be automatically replaced.")
            slate_date=st.date_input("Slate date",value=None)
            cutoff=st.text_input("Decision cutoff (ISO 8601 with timezone)")
            sources=st.file_uploader("Independent projection evidence JSON",type=["json"])
            if sources and slate_date and cutoff:
                try:
                    review=review_nfl_projections(report,json.loads(sources.getvalue()),
                                                  slate_date=slate_date.isoformat(),cutoff_utc=cutoff)
                except (ValueError,TypeError,UnicodeError) as exc:
                    st.error(str(exc))
                else:
                    st.warning(review["warning"])
                    st.dataframe(pd.DataFrame(review["rows"]),hide_index=True)
                    if review["rejected_evidence"]:
                        st.dataframe(pd.DataFrame(review["rejected_evidence"]),hide_index=True)
                    st.download_button("Download independent review",json.dumps(review,indent=2),
                                       file_name="nfl_projection_review.json",mime="application/json")

        with st.expander("Fixed-candidate research comparison"):
            st.caption("Requires the exact DAILY capture receipt, source evidence and timestamped candidate records. No official availability certification or optimization.")
            bundle=st.file_uploader("Reviewed candidate bundle JSON",type=["json"])
            if bundle:
                try:
                    args=json.loads(bundle.getvalue())
                    result=compare_reviewed_nfl(contest.getvalue(),daily.getvalue(),
                        contest_id=contest_id,single_game=mode=="Single game",
                        **{k:args[k] for k in ("slate_date","cutoff_utc","daily_capture","evidence","candidates","salary_cap")})
                except (ValueError,TypeError,KeyError,UnicodeError) as exc:
                    st.error(str(exc))
                else:
                    st.warning(result["warning"])
                    if result["ready"]:
                        st.dataframe(pd.DataFrame(result["rankings"]),hide_index=True)
                    else:
                        st.info("Comparison blocked until every eligible player has a reviewed score.")
                        st.dataframe(pd.DataFrame(result["unresolved"]),hide_index=True)
                    st.download_button("Download fixed-candidate review",json.dumps(result,indent=2),
                                       file_name="nfl_candidate_review.json",mime="application/json")
