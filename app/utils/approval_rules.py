from decimal import Decimal

from app.database.models import (
    ApprovalDecision,
    InvoiceExtraction,
    InvoiceValidation,
    PolicyAudit,
)


def determine_approval(
    extraction: InvoiceExtraction,
    validation: InvoiceValidation,
    policy_audit: PolicyAudit | None = None,
) -> ApprovalDecision:
    if not validation.is_valid or extraction.total_amount is None:
        return ApprovalDecision(
            approval_authority=None,
            status="Manual Review",
            reason="Required invoice details are missing or inconsistent.",
        )

    if policy_audit and not policy_audit.compliant:
        issues = (
            "; ".join(v.issue for v in policy_audit.violations[:2])
            if policy_audit.violations
            else "Policy non-compliance detected."
        )
        return ApprovalDecision(
            approval_authority=None,
            status="Manual Review",
            reason=f"Policy compliance flag: {issues}",
        )

    amount = extraction.total_amount
    if amount < Decimal("10000"):
        return ApprovalDecision(
            approval_authority="Automatic approval after validation",
            status="Auto Approved",
            reason="Validated invoice is below ₹10,000, per Invoice Approval Policy.",
        )
    if amount <= Decimal("50000"):
        return ApprovalDecision(
            approval_authority="Department Manager",
            status="Pending Approval",
            reason="Invoice is within the ₹10,000–₹50,000 manager approval band.",
        )
    if amount <= Decimal("200000"):
        return ApprovalDecision(
            approval_authority="Finance Manager",
            status="Pending Approval",
            reason="Invoice is within the ₹50,001–₹2,00,000 finance approval band.",
        )
    return ApprovalDecision(
        approval_authority="Finance Head",
        status="Pending Approval",
        reason="Invoice exceeds ₹2,00,000 and requires Finance Head approval.",
    )
