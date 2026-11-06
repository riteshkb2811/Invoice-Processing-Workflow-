import base64
import os
import smtplib
import sys
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from app.database.models import InvoiceProcessingResult

PROJECT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_DIR / ".env")

CLIENT_SECRET_FILE = PROJECT_DIR / "client_secret.json"
TOKEN_FILE = PROJECT_DIR / "token.json"
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def get_recipient_email() -> str:
    """Return the designated recipient email for manual review alerts."""
    return os.getenv("MANUAL_REVIEW_EMAIL", "reviewer@company.com").strip()


def authenticate_gmail() -> Credentials | None:
    """Run one-time interactive OAuth2 authorization and persist token.json."""
    if not CLIENT_SECRET_FILE.exists():
        print(f"Error: {CLIENT_SECRET_FILE} not found.")
        return None

    flow = InstalledAppFlow.from_client_secrets_file(
        str(CLIENT_SECRET_FILE),
        scopes=GMAIL_SCOPES,
    )
    creds = flow.run_local_server(port=0)
    TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
    print(f"Authentication successful! Token saved to {TOKEN_FILE}")
    return creds


def get_gmail_credentials() -> Credentials | None:
    """Retrieve or refresh valid Gmail API OAuth2 credentials without blocking."""
    creds = None
    if TOKEN_FILE.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), GMAIL_SCOPES)
        except Exception:
            creds = None

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
        except Exception:
            creds = None

    return creds if (creds and creds.valid) else None


def build_email_content(
    result: InvoiceProcessingResult,
    source_filename: str,
) -> tuple[str, str, str]:
    """Generate subject, plain-text body, and HTML body for a manual review notification."""
    extraction = result.extraction
    approval = result.approval
    validation = result.validation
    policy_audit = result.policy_audit

    invoice_num = extraction.invoice_number or "UNKNOWN"
    vendor = extraction.vendor_name or "Unknown Vendor"
    amount = (
        f"{extraction.currency} {extraction.total_amount:,.2f}"
        if extraction.total_amount is not None
        else "Unstated"
    )

    subject = f"[Action Required] Manual Review Needed: Invoice {invoice_num} ({vendor})"

    # Plain-text version
    text_lines = [
        "===========================================================",
        "        MANUAL INVOICE REVIEW REQUIRED",
        "===========================================================",
        f"File Name:       {source_filename}",
        f"Invoice Number:  {invoice_num}",
        f"Vendor:          {vendor}",
        f"Date:            {extraction.invoice_date or 'Not extracted'}",
        f"Total Amount:    {amount}",
        f"Approval Status: {approval.status}",
        f"Reason:          {approval.reason}",
        "",
        "--- Validation Findings ---",
    ]

    issues = validation.errors + validation.warnings
    if issues:
        for item in issues:
            text_lines.append(f"  * {item}")
    else:
        text_lines.append("  * None (Validation passed arithmetic checks)")

    if policy_audit:
        text_lines.append("")
        text_lines.append("--- Policy Compliance Audit ---")
        text_lines.append(f"Compliant: {'YES' if policy_audit.compliant else 'NO'}")
        if policy_audit.violations:
            for violation in policy_audit.violations:
                text_lines.append(
                    f"  * [{violation.policy_name}] ({violation.severity}): {violation.issue} - {violation.explanation}"
                )
        if policy_audit.recommendations:
            text_lines.append("Recommendations:")
            for rec in policy_audit.recommendations:
                text_lines.append(f"  * {rec}")

    text_lines.append("")
    text_lines.append("The original invoice PDF is attached for your review.")
    text_lines.append("Please log into the Invoice Review Desk to inspect and resolve this invoice.")
    text_body = "\n".join(text_lines)

    # HTML version
    violations_html = ""
    if policy_audit and policy_audit.violations:
        violations_html = "<h3>Policy Violations</h3><ul>"
        for v in policy_audit.violations:
            color = "#d9534f" if v.severity.lower() == "high" else "#f0ad4e"
            violations_html += (
                f"<li><span style='color:{color};font-weight:bold;'>[{v.severity}]</span> "
                f"<strong>{v.policy_name}</strong>: {v.issue}<br>"
                f"<small style='color:#666;'>{v.explanation}</small></li>"
            )
        violations_html += "</ul>"

    validation_html = ""
    if issues:
        validation_html = "<h3>Validation Discrepancies</h3><ul>"
        for issue in issues:
            validation_html += f"<li>{issue}</li>"
        validation_html += "</ul>"

    html_body = f"""<!DOCTYPE html>
<html>
<head>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #222; }}
    .container {{ max-width: 650px; margin: auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px; }}
    .header {{ background-color: #f7a825; color: #1a1a1a; padding: 12px 18px; border-radius: 6px; font-weight: bold; font-size: 18px; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
    th, td {{ text-align: left; padding: 8px 12px; border-bottom: 1px solid #eee; }}
    th {{ background-color: #f9f9f9; color: #555; width: 35%; }}
    .attachment-note {{ background-color: #eaf4fc; border-left: 4px solid #2196F3; padding: 10px 14px; margin-top: 16px; font-size: 14px; border-radius: 4px; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      Invoice Flagged for Manual Review
    </div>
    <p>An uploaded invoice PDF has been routed to <strong>Manual Review</strong> by the compliance and validation engine.</p>
    <table>
      <tr><th>Source File</th><td>{source_filename}</td></tr>
      <tr><th>Invoice Number</th><td><strong>{invoice_num}</strong></td></tr>
      <tr><th>Vendor</th><td>{vendor}</td></tr>
      <tr><th>Total Amount</th><td><strong>{amount}</strong></td></tr>
      <tr><th>Review Reason</th><td>{approval.reason}</td></tr>
    </table>
    {validation_html}
    {violations_html}
    <div class="attachment-note">
      📎 The original invoice PDF (<strong>{source_filename}</strong>) is attached to this email for your review.
    </div>
    <p style="margin-top: 20px; font-size: 13px; color: #777;">
      This notification was generated automatically by AutoMobile_RAG Invoice Review Desk.
    </p>
  </div>
</body>
</html>"""

    return subject, text_body, html_body


def _build_message_with_attachment(
    recipient: str,
    subject: str,
    text_body: str,
    html_body: str,
    pdf_bytes: bytes | None,
    pdf_filename: str,
    sender: str | None = None,
) -> MIMEMultipart:
    """Build a MIMEMultipart email with text/html body and optional PDF attachment."""
    message = MIMEMultipart("mixed")
    message["Subject"] = subject
    message["To"] = recipient
    if sender:
        message["From"] = sender

    # Text and HTML alternatives
    body_part = MIMEMultipart("alternative")
    body_part.attach(MIMEText(text_body, "plain", "utf-8"))
    body_part.attach(MIMEText(html_body, "html", "utf-8"))
    message.attach(body_part)

    # PDF attachment
    if pdf_bytes:
        attachment = MIMEApplication(pdf_bytes, _subtype="pdf")
        attachment.add_header(
            "Content-Disposition",
            "attachment",
            filename=pdf_filename,
        )
        message.attach(attachment)

    return message


def _send_via_gmail_api(
    creds: Credentials,
    recipient: str,
    subject: str,
    text_body: str,
    html_body: str,
    pdf_bytes: bytes | None = None,
    pdf_filename: str = "invoice.pdf",
) -> tuple[bool, str]:
    """Send email with PDF attachment using the official Google Gmail REST API."""
    try:
        service = build("gmail", "v1", credentials=creds)
        message = _build_message_with_attachment(
            recipient, subject, text_body, html_body, pdf_bytes, pdf_filename
        )

        raw_bytes = message.as_bytes()
        raw_b64 = base64.urlsafe_b64encode(raw_bytes).decode("utf-8")

        service.users().messages().send(
            userId="me",
            body={"raw": raw_b64},
        ).execute()

        return True, f"Manual review alert with invoice PDF sent via Gmail API to {recipient}"
    except Exception as error:
        return False, f"Gmail API delivery failed: {error}"


def _send_via_smtp(
    recipient: str,
    subject: str,
    text_body: str,
    html_body: str,
    pdf_bytes: bytes | None = None,
    pdf_filename: str = "invoice.pdf",
) -> tuple[bool, str]:
    """Send email with PDF attachment using standard SMTP server."""
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "").strip()
    smtp_password = os.getenv("SMTP_PASSWORD", "").strip()
    smtp_from = os.getenv("SMTP_FROM", smtp_user or "noreply@automobile-rag.com").strip()

    if not smtp_user or not smtp_password:
        return False, "SMTP credentials (SMTP_USER/SMTP_PASSWORD) not configured."

    try:
        message = _build_message_with_attachment(
            recipient, subject, text_body, html_body, pdf_bytes, pdf_filename, sender=smtp_from
        )

        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_from, [recipient], message.as_string())

        return True, f"Manual review alert with invoice PDF sent via SMTP to {recipient}"
    except Exception as error:
        return False, f"SMTP delivery failed: {error}"


def send_manual_review_email(
    result: InvoiceProcessingResult,
    source_filename: str,
    pdf_bytes: bytes | None = None,
    recipient: str | None = None,
) -> tuple[bool, str]:
    """
    Send an email notification with the invoice PDF attached when
    an invoice requires manual checking.

    Priority order:
    1. Gmail API via OAuth2 (if token.json or authenticated creds exist)
    2. Standard SMTP (if SMTP_USER and SMTP_PASSWORD configured)
    3. Simulated delivery notice (prevents workflow failure during local development)
    """
    target_email = recipient or get_recipient_email()
    subject, text_body, html_body = build_email_content(result, source_filename)

    # 1. Try Gmail API OAuth2
    gmail_creds = get_gmail_credentials()
    if gmail_creds:
        success, msg = _send_via_gmail_api(
            gmail_creds, target_email, subject, text_body, html_body,
            pdf_bytes=pdf_bytes, pdf_filename=source_filename,
        )
        if success:
            return True, msg

    # 2. Try Standard SMTP
    if os.getenv("SMTP_USER") and os.getenv("SMTP_PASSWORD"):
        success, msg = _send_via_smtp(
            target_email, subject, text_body, html_body,
            pdf_bytes=pdf_bytes, pdf_filename=source_filename,
        )
        if success:
            return True, msg

    # 3. Notification guidance if client_secret exists but token not generated yet
    if CLIENT_SECRET_FILE.exists() and not TOKEN_FILE.exists():
        return (
            True,
            f"Gmail client_secret detected. To authorize live sending, run: python -m app.services.email_service --auth (Target: {target_email})",
        )

    # 4. Default fallback simulation
    attachment_note = f" with PDF attachment ({len(pdf_bytes):,} bytes)" if pdf_bytes else ""
    msg = f"Simulated: Manual review alert{attachment_note} prepared for {target_email} (Configure Gmail OAuth or SMTP in .env for live email)"
    return True, msg


if __name__ == "__main__":
    if "--auth" in sys.argv:
        print("Starting Gmail OAuth2 authentication...")
        authenticate_gmail()
    else:
        print("Usage:")
        print("  python -m app.services.email_service --auth   (Authorize Gmail account via OAuth2)")
