import os

import streamlit as st

from app.database.models import InvoiceProcessingResult
from app.routes.invoice_routes import process_invoice
from app.services.rag_service import load_policy_documents
from app.services.push_to_db import push_invoice_to_db


def render_app() -> None:
    st.set_page_config(
        page_title="Invoice review",
        page_icon=":material/receipt_long:",
        layout="wide",
    )

    policies = load_policy_documents()
    policy_names = sorted({document.metadata["source"] for document in policies})

    with st.sidebar:
        st.subheader("Review settings")
        model_name = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
        st.caption(f"Review model · {model_name}")
        st.caption("Text extraction · LangChain PDFMiner + local OCR fallback")
        st.caption("Policy search · Ollama embeddings + Chroma")
        st.divider()
        st.subheader("Email alerts")
        recipient = os.getenv("MANUAL_REVIEW_EMAIL", "reviewer@company.com")
        st.caption(f"Recipient: {recipient}")
        from pathlib import Path
        token_path = Path(__file__).resolve().parents[1] / "token.json"
        secret_path = Path(__file__).resolve().parents[1] / "client_secret.json"
        if token_path.exists():
            st.badge("Gmail API connected", color="green")
        elif secret_path.exists():
            st.badge("Gmail auth required", color="orange")
            st.caption("To link Gmail, run in terminal:\n`python -m app.services.email_service --auth`")
        elif os.getenv("SMTP_USER"):
            st.badge("SMTP active", color="green")
        else:
            st.badge("Simulation mode", color="gray")
        st.divider()
        st.caption("PDF text extraction is local. Extracted invoice text is sent to Groq for classification and field extraction.")

    st.title("Invoice review desk")
    st.write("Upload invoices to extract key fields and check them against approval policies.")

    policy_col, policy_state = st.columns([3, 1], vertical_alignment="center")
    policy_col.caption(f"{len(policy_names)} policy files available")
    policy_state.badge(
        "Policies loaded" if policies else "No policies found",
        color="green" if policies else "orange",
    )

    uploads = st.file_uploader(
        "Choose invoice PDFs",
        type=["pdf"],
        accept_multiple_files=True,
        help="Select one or more PDFs. Scanned pages are processed with local OCR.",
    )

    if uploads:
        file_col, size_col = st.columns(2)
        file_col.metric("PDFs selected", len(uploads))
        total_size = sum(upload.size for upload in uploads)
        size_col.metric("Total upload size", f"{total_size / (1024 * 1024):.1f} MB")
        with st.expander("Selected files", expanded=False):
            for upload in uploads:
                st.write(f"{upload.name} · {upload.size / 1024:.0f} KB")

    process = st.button(
        "Analyze invoices",
        type="primary",
        icon=":material/analytics:",
        disabled=not uploads,
        width="stretch",
    )

    if process and uploads:
        results = []
        progress = st.progress(0, text="Preparing review")
        status = st.status("Processing invoices", expanded=True)
        for index, upload in enumerate(uploads, start=1):
            try:
                status.write(f"Reviewing {upload.name}")
                (
                    review,
                    invoice_text,
                    page_count,
                    ocr_pages,
                    sources,
                    record_id,
                    push_reasons,
                ) = process_invoice(
                    upload.getvalue(),
                    upload.name,
                )
                results.append(
                    {
                        "filename": upload.name,
                        "index": index,
                        "page_count": page_count,
                        "ocr_pages": ocr_pages,
                        "invoice_text": invoice_text,
                        "review": review,
                        "policy_names": sources,
                        "record_id": record_id,
                        "push_reasons": push_reasons,
                    }
                )
            except Exception as error:
                results.append(
                    {"filename": upload.name, "index": index, "error": str(error)}
                )
                status.write(f"Could not review {upload.name}: {error}")
            progress.progress(index / len(uploads), text=f"Processed {index} of {len(uploads)}")
        status.update(label="Review complete", state="complete", expanded=False)
        st.session_state["invoice_results"] = results

    if st.session_state.get("invoice_results"):
        st.divider()
        st.subheader("Review results")
        for item in st.session_state["invoice_results"]:
            if "error" in item:
                st.warning(
                    f"{item['filename']}: {item['error']}",
                    title="Invoice could not be reviewed",
                )
                continue

            review: InvoiceProcessingResult = item["review"]
            extraction = review.extraction
            approval = review.approval
            with st.container(border=True):
                title_col, badge_col = st.columns([3, 1], vertical_alignment="center")
                title_col.markdown(f"#### {item['filename']}")
                badge_col.badge(
                    approval.status,
                    color="green" if approval.status == "Auto Approved" else "orange",
                )

                metrics = st.columns(3)
                metrics[0].metric("Invoice number", extraction.invoice_number or "Not found")
                metrics[1].metric("Vendor", extraction.vendor_name or "Not found")
                amount = (
                    f"{extraction.currency} {extraction.total_amount:,.2f}"
                    if extraction.total_amount is not None
                    else "Not found"
                )
                metrics[2].metric("Total amount", amount)

                gst_amount = (
                    sum(
                        (value or 0 for value in (extraction.cgst, extraction.sgst, extraction.igst)),
                        start=0,
                    )
                    if any(value is not None for value in (extraction.cgst, extraction.sgst, extraction.igst))
                    else None
                )
                invoice_rows = [
                    ("Invoice number", extraction.invoice_number or "Missing"),
                    ("Vendor", extraction.vendor_name or "Missing"),
                    ("GSTIN", extraction.vendor_gstin or "Missing"),
                    (
                        "Invoice date",
                        extraction.invoice_date.strftime("%d-%m-%Y")
                        if extraction.invoice_date
                        else "Missing",
                    ),
                    ("PO number", extraction.po_number or "Missing"),
                    (
                        "Subtotal",
                        f"{extraction.currency} {extraction.subtotal:,.2f}"
                        if extraction.subtotal is not None
                        else "Missing",
                    ),
                    (
                        "GST",
                        f"{extraction.currency} {gst_amount:,.2f}"
                        if gst_amount is not None
                        else "Missing",
                    ),
                    ("Total", amount),
                ]
                st.table(
                    {"Field": [field for field, _ in invoice_rows], "Extracted value": [value for _, value in invoice_rows]},
                    border="horizontal",
                )

                if item["record_id"] is not None:
                    st.success(f"Saved to invoice database · record {item['record_id']}")
                else:
                    st.warning(
                        "Some requested details are missing or validation found errors. "
                        "Review the fields before confirming a partial save.",
                        title="Confirmation required",
                    )
                    for reason in item["push_reasons"]:
                        st.caption(f"· {reason}")
                    if st.button(
                        "Push to database anyway",
                        key=f"push_invoice_{item['index']}",
                        icon=":material/database:",
                    ):
                        try:
                            saved_id = push_invoice_to_db(review, item["filename"])
                            item["record_id"] = saved_id
                            st.success(f"Saved to invoice database · record {saved_id}")
                        except Exception as error:
                            st.error(f"Could not save invoice: {error}")

                if review.email_notification_status:
                    st.caption(f"📧 {review.email_notification_status}")

                details_tab, policy_tab, text_tab = st.tabs(
                    ["Details", "Policy review", "Extracted text"]
                )
                with details_tab:
                    st.json(review.model_dump(mode="json"))
                    messages = review.validation.errors + review.validation.warnings
                    if messages:
                        st.warning(
                            "Check extracted values before acting on this invoice.",
                            title="Validation findings",
                        )
                        for message in messages:
                            st.write(f"- {message}")
                    else:
                        st.success("No validation errors were found.")
                with policy_tab:
                    st.write(f"**Approval Decision:** {approval.reason}")
                    st.write(
                        f"**Approval authority:** {approval.approval_authority or 'Not specified'}"
                    )
                    st.caption(
                        "Policy sources: "
                        + (", ".join(item["policy_names"]) or "none")
                    )
                    if review.policy_audit:
                        st.divider()
                        st.subheader("Policy compliance audit")
                        if review.policy_audit.compliant:
                            st.success("Invoice complies with matched company policies.")
                        else:
                            st.error("Policy compliance violations detected:")
                            for violation in review.policy_audit.violations:
                                st.markdown(
                                    f"- **[{violation.policy_name}]** ({violation.severity}): {violation.issue}"
                                )
                                st.caption(f"  {violation.explanation}")
                        if review.policy_audit.recommendations:
                            st.markdown("**Recommendations:**")
                            for rec in review.policy_audit.recommendations:
                                st.write(f"- {rec}")
                with text_tab:
                    st.caption(
                        f"{item['page_count']} pages · {item['ocr_pages']} pages required OCR"
                    )
                    st.text_area(
                        "Extracted invoice text",
                        value=item["invoice_text"],
                        height=260,
                        key=f"invoice_text_{item['index']}",
                    )

if __name__ == "__main__":
    render_app()