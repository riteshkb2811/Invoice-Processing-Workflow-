from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class InvoiceClassification(BaseModel):
    invoice_type: Literal["Purchase", "Service", "Utility", "Other"]
    confidence: float = Field(ge=0, le=1)


class InvoiceExtraction(BaseModel):
    invoice_number: str | None = None
    vendor_name: str | None = None
    vendor_gstin: str | None = None
    invoice_date: date | None = None
    due_date: date | None = None
    po_number: str | None = None
    subtotal: Decimal | None = None
    cgst: Decimal | None = None
    sgst: Decimal | None = None
    igst: Decimal | None = None
    total_amount: Decimal | None = None
    currency: str = "INR"


class InvoiceValidation(BaseModel):
    is_valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ApprovalDecision(BaseModel):
    approval_authority: str | None = None
    status: Literal[
        "Auto Approved",
        "Pending Approval",
        "Rejected",
        "Manual Review",
    ]
    reason: str


class InvoiceProcessingResult(BaseModel):
    classification: InvoiceClassification
    extraction: InvoiceExtraction
    validation: InvoiceValidation
    approval: ApprovalDecision