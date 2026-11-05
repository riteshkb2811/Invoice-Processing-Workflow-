import os

from dotenv import load_dotenv
from langchain_groq import ChatGroq

from app.database.models import InvoiceExtraction


PROJECT_DIR = __import__("pathlib").Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_DIR / ".env")


def extract_invoice_fields(invoice_text: str) -> InvoiceExtraction:
    api_key = os.getenv("GroqKEY", "")
    if not api_key:
        raise RuntimeError("Set GroqKEY in the project .env file before invoice analysis.")
    llm = ChatGroq(
        api_key=api_key,
        model=os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"),
        temperature=0,
        max_tokens=900,
    ).with_structured_output(
        InvoiceExtraction,
        method="json_schema",
        strict=True,
    )
    prompt = (
        "Extract the invoice fields from the supplied text. Use null for any "
        "missing or unclear value. Do not guess or calculate absent fields.\n\n"
        f"INVOICE:\n{invoice_text}"
    )
    return llm.invoke(prompt)