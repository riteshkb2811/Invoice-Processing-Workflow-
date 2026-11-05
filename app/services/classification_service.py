import os

from dotenv import load_dotenv
from langchain_groq import ChatGroq

from app.database.models import InvoiceClassification


PROJECT_DIR = __import__("pathlib").Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_DIR / ".env")


def classify_invoice(invoice_text: str) -> InvoiceClassification:
    api_key = os.getenv("GroqKEY", "")
    if not api_key:
        raise RuntimeError("Set GroqKEY in the project .env file before invoice analysis.")
    llm = ChatGroq(
        api_key=api_key,
        model=os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"),
        temperature=0,
        max_tokens=500,
    ).with_structured_output(
        InvoiceClassification,
        method="json_schema",
        strict=True,
    )
    prompt = (
        "Classify this invoice as Purchase, Service, Utility, or Other. "
        "Set confidence between 0 and 1 and do not infer unsupported details.\n\n"
        f"INVOICE:\n{invoice_text}"
    )
    return llm.invoke(prompt)