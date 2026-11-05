from app.database.models import InvoiceProcessingResult
from app.services.classification_service import classify_invoice
from app.services.extraction_service import extract_invoice_fields
from app.services.ocr_service import extract_pdf_text
from app.services.rag_service import retrieve_policy_context
from app.services.validation_service import validate_invoice
from app.services.push_to_db import get_push_confirmation_reasons, push_invoice_to_db
from app.utils.approval_rules import determine_approval


def process_invoice(
    pdf_bytes: bytes,
    source_filename: str = "uploaded_invoice.pdf",
) -> tuple[InvoiceProcessingResult, str, int, int, list[str], int | None, list[str]]:
    invoice_text, page_count, ocr_pages = extract_pdf_text(pdf_bytes)
    if not invoice_text.strip():
        raise ValueError("The uploaded PDF contains no readable text.")

    classification = classify_invoice(invoice_text)
    extraction = extract_invoice_fields(invoice_text)
    policy_query = " ".join(
        value
        for value in (
            classification.invoice_type,
            extraction.vendor_name or "",
            extraction.po_number or "",
            str(extraction.total_amount or ""),
            "invoice approval GST payment purchase order",
        )
        if value
    )
    _, policy_sources = retrieve_policy_context(policy_query)
    validation = validate_invoice(extraction)
    approval = determine_approval(extraction, validation)
    result = InvoiceProcessingResult(
        classification=classification,
        extraction=extraction,
        validation=validation,
        approval=approval,
    )
    confirmation_reasons = get_push_confirmation_reasons(result)
    record_id = None
    if not confirmation_reasons:
        record_id = push_invoice_to_db(result, source_filename)
    return (
        result,
        invoice_text,
        page_count,
        ocr_pages,
        policy_sources,
        record_id,
        confirmation_reasons,
    )