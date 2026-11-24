import json

import pandas as pd
import streamlit as st

from member3.ai.ecn_extractor import ExtractionFailure, extract_pdf_text, extract_plain_text
from member3.application.access_control import NotAllowed
from member3.application.session_manager import context, flash, page_header
from member3.services import ecn_service, planning_service
from member3.settings import ROOT

ctx = context()
page_header("ECN Intake", ctx)

with st.expander("New document", expanded=ecn_service.latest_review(ctx.scenario) is None):
    samples = json.loads((ROOT / "member3/data/demo/ecn_samples.json").read_text(encoding="utf-8"))
    sample = st.selectbox("Load a sample text", [None] + samples,
                          format_func=lambda s: f"{s['id']}: {s['title']}" if s else "None")
    upload = st.file_uploader("Upload ECN or ECR", type=["pdf", "txt"])
    pasted = st.text_area("Or paste the text", sample["text"] if sample else "", height=220)
    run_it, manual = st.columns(2)
    try:
        if run_it.button("Run extraction", type="primary"):
            if upload:
                content = upload.getvalue()
                text = extract_pdf_text(content) if upload.name.lower().endswith(".pdf") else extract_plain_text(content)
                source = upload.name
            else:
                text, source = extract_plain_text(pasted), sample["id"] if sample else "pasted text"
            ecn_service.create_review(text, ctx.scenario, ctx.member1, ctx.user, ctx.provider, source)
            flash("Extraction finished. Review the fields below.")
            st.rerun()
        if manual.button("Enter fields manually"):
            ecn_service.create_manual_review(ctx.scenario, ctx.member1, ctx.user)
            st.rerun()
    except (ExtractionFailure, NotAllowed) as error:
        st.error(str(error))

review = ecn_service.latest_review(ctx.scenario)
if not review:
    st.stop()
extraction, fields, validation = review["extraction"], review["fields"], review["validation"]
st.subheader(f"Review {review['review_id']}")
st.caption(f"Source: {extraction['source_document']} | extracted by {extraction['extraction_source']} | "
           f"{extraction['extraction_confidence']:.0%} of fields found (coverage, not a proof of correctness)")
if extraction["provider_error"]:
    st.warning(f"AI extraction failed ({extraction['provider_error']}); offline rules were used.")
(st.success if validation["validation_status"] == "VALID" else st.error
 if validation["validation_status"] == "INVALID" else st.warning)(
    f"Validation: {validation['validation_status'].replace('_', ' ').lower()}")
if validation["missing_fields"]:
    st.warning("Missing: " + ", ".join(validation["missing_fields"]))
for item in validation["ambiguous_fields"]:
    st.warning(f"Ambiguous {item['field']}: “{item['source_text']}”")
for item in validation["conflicts"]:
    st.error(f"Conflicting {item['field']}: " + " | ".join(f"{v['value']} (“{v['source_text']}”)" for v in item["values"]))
for item in extraction["unsupported_values"]:
    st.error(f"Dropped {item['field']} = {item['value']}: {item['why']}")
for item in validation["validation_errors"]:
    st.error(f"{item['code']} ({item['field']}): {item['message']}")

left, right = st.columns([2, 3])
with left:
    st.markdown("**Document text**")
    st.text_area("Document text", review["document_text"], height=420, disabled=True, label_visibility="collapsed")
    if extraction["evidence"]:
        with st.expander("Where each value was found"):
            st.dataframe(pd.DataFrame(extraction["evidence"].items(), columns=["Field", "Source text"]), hide_index=True)
with right:
    confirmed = review["status"] == "CONFIRMED"
    with st.form(f"fields-{review['review_id']}"):
        a, b = st.columns(2)
        edited = {}
        for name, column in (("change_id", a), ("part_number", b), ("old_revision", a), ("new_revision", b)):
            edited[name] = column.text_input(name.replace("_", " ").capitalize(), fields[name] or "", disabled=confirmed).strip().upper() or None
        for name, column in (("effective_week", a), ("use_up_end_week", b)):
            edited[name] = column.number_input(name.replace("_", " ").capitalize(), 1, 104, fields[name], step=1, disabled=confirmed)
        choices = [None, True, False]
        edited["interchangeability"] = a.selectbox(
            "Interchangeable", choices, choices.index(fields["interchangeability"]), disabled=confirmed,
            format_func=lambda v: {None: "Not stated", True: "Yes", False: "No"}[v])
        statuses = [None, "APPROVED", "PENDING", "DRAFT", "REJECTED"]
        current = fields["approval_status"] if fields["approval_status"] in statuses else None
        edited["approval_status"] = b.selectbox("Approval status", statuses, statuses.index(current), disabled=confirmed,
                                                format_func=lambda v: v or "Not stated")
        for name in ("reason", "approver"):
            edited[name] = st.text_input(name.capitalize(), fields[name] or "", disabled=confirmed).strip() or None
        if st.form_submit_button("Save corrections and validate", disabled=confirmed):
            try:
                ecn_service.update_fields(review["review_id"], edited, ctx.member1, ctx.user)
                st.rerun()
            except (NotAllowed, ValueError) as error:
                st.error(str(error))
    try:
        if not confirmed:
            checked = st.checkbox("I compared these fields with the document")
            ready = validation["validation_status"] == "VALID"
            if st.button("Confirm and submit", type="primary", disabled=not (checked and ready)):
                ecn_service.confirm(review["review_id"], ctx.member1, ctx.user)
                flash("ECN confirmed. It is ready for planning.")
                st.rerun()
            if not ready:
                st.caption("Submission opens when the validation is valid.")
        else:
            st.success(f"Confirmed by {review['confirmed_by']} at {review['confirmed_at']} UTC")
            if st.button("Run planning", type="primary"):
                with st.spinner("Generating and evaluating plans"):
                    planning_service.run_planning(review["review_id"], ctx.member1, ctx.member2, ctx.user, ctx.provider)
                flash("Planning finished. See Optimization Recommendations.")
                st.rerun()
    except (NotAllowed, ecn_service.NotReady) as error:
        st.error(str(error))
