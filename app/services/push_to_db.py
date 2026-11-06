import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pymysql
from dotenv import load_dotenv

from app.database.models import InvoiceProcessingResult


PROJECT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_DIR / ".env")


def _connect():
    import os

    username = os.getenv("user1")
    password = os.getenv("pass1")
    if not username or not password:
        raise RuntimeError("Set user1 and pass1 in the project .env file for MySQL.")
    return pymysql.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=username,
        password=password,
        database=os.getenv("MYSQL_DATABASE", "info"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


def get_push_confirmation_reasons(result: InvoiceProcessingResult) -> list[str]:
    extraction = result.extraction
    required_values = {
        "Invoice number": extraction.invoice_number,
        "Vendor": extraction.vendor_name,
        "GSTIN": extraction.vendor_gstin,
        "Invoice date": extraction.invoice_date,
        "PO number": extraction.po_number,
        "Subtotal": extraction.subtotal,
        "GST amount": (
            sum(
                (value or 0 for value in (extraction.cgst, extraction.sgst, extraction.igst)),
                start=0,
            )
            if any(value is not None for value in (extraction.cgst, extraction.sgst, extraction.igst))
            else None
        ),
        "Total amount": extraction.total_amount,
    }
    reasons = [
        f"{label} is missing"
        for label, value in required_values.items()
        if value is None or value == ""
    ]
    if result.validation.errors:
        reasons.append("invoice has validation errors")
    if result.policy_audit and not result.policy_audit.compliant:
        reasons.append("invoice has policy compliance violations")
    return reasons


def _record_key(result: InvoiceProcessingResult, source_filename: str) -> str:
    extraction = result.extraction
    identity = {
        "invoice_number": extraction.invoice_number,
        "vendor_name": extraction.vendor_name,
        "invoice_date": (
            extraction.invoice_date.isoformat()
            if extraction.invoice_date
            else None
        ),
        "total_amount": (
            str(extraction.total_amount)
            if extraction.total_amount is not None
            else None
        ),
        "source_filename": source_filename,
    }
    return hashlib.sha256(
        json.dumps(identity, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def push_invoice_to_db(
    result: InvoiceProcessingResult,
    source_filename: str,
) -> int:
    extraction = result.extraction
    record_key = _record_key(result, source_filename)
    connection = _connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS invoices (
                    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                    record_key CHAR(64) NOT NULL UNIQUE,
                    source_filename VARCHAR(255) NOT NULL,
                    invoice_number VARCHAR(100),
                    vendor_name VARCHAR(255),
                    total_amount DECIMAL(18, 2),
                    review_json JSON NOT NULL,
                    pushed_at DATETIME(6) NOT NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""
            )
            cursor.execute(
                """INSERT INTO invoices (
                    record_key, source_filename, invoice_number, vendor_name,
                    total_amount, review_json, pushed_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    total_amount=VALUES(total_amount),
                    review_json=VALUES(review_json),
                    pushed_at=VALUES(pushed_at)""",
                (
                    record_key,
                    source_filename,
                    extraction.invoice_number,
                    extraction.vendor_name,
                    extraction.total_amount,
                    result.model_dump_json(),
                    datetime.now(timezone.utc).replace(tzinfo=None),
                ),
            )
            cursor.execute("SELECT id FROM invoices WHERE record_key = %s", (record_key,))
            row = cursor.fetchone()
    finally:
        connection.close()

    if row is None:
        raise RuntimeError("Invoice was not persisted to MySQL.")
    return int(row["id"])
