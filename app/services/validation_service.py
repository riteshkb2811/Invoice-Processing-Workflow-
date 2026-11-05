from app.database.models import InvoiceExtraction, InvoiceValidation


def validate_invoice(extraction: InvoiceExtraction) -> InvoiceValidation:
    errors = []
    warnings = []
    required_fields = {
        "Invoice number": extraction.invoice_number,
        "Vendor name": extraction.vendor_name,
        "Invoice date": extraction.invoice_date,
        "Total amount": extraction.total_amount,
    }
    for label, value in required_fields.items():
        if value is None or value == "":
            errors.append(f"{label} was not confidently extracted.")

    if extraction.vendor_gstin:
        gstin = extraction.vendor_gstin.strip().upper()
        if len(gstin) != 15:
            errors.append("Supplier GSTIN must contain 15 characters.")
        extraction.vendor_gstin = gstin
    else:
        warnings.append("Supplier GSTIN was not found; verify whether it is required.")

    taxes = (extraction.cgst, extraction.sgst, extraction.igst)
    if extraction.subtotal is not None and extraction.total_amount is not None and any(
        tax is not None for tax in taxes
    ):
        calculated_total = extraction.subtotal + sum(
            (tax or 0 for tax in taxes), start=0
        )
        if abs(calculated_total - extraction.total_amount) > 1:
            errors.append(
                f"Subtotal plus tax ({calculated_total}) does not match "
                f"the stated total ({extraction.total_amount})."
            )

    return InvoiceValidation(
        is_valid=not errors,
        errors=errors,
        warnings=warnings,
    )