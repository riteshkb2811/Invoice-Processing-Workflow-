# Invoice Review Desk

A Streamlit application for extracting invoice details from PDF files, checking them against company policies, validating invoice data, calculating approval routing, and saving reviewed invoices to MySQL.

## Features

- Upload and analyze one or more invoice PDFs.
- Extract selectable PDF text with LangChain PDFMiner; use local RapidOCR for scanned pages.
- Classify invoices and extract structured fields with Groq.
- Retrieve relevant company policy passages using Ollama embeddings and Chroma.
- Validate required fields, GSTIN presence, and subtotal/tax totals.
- Route invoices according to the approval thresholds in the company policy.
- Automatically save invoices when the required fields are present and there are no validation errors.
- Ask for confirmation before saving incomplete or validation-flagged invoices.
- Store the complete structured review in MySQL as JSON, with searchable invoice columns.

## Project layout

```text
app/
  main.py                       Streamlit entry point
  routes/
    invoice_routes.py           Invoice processing workflow
  services/
    classification_service.py   Groq invoice classification
    extraction_service.py       Groq field extraction
    ocr_service.py              PDFMiner and OCR text extraction
    rag_service.py              Ollama embeddings and Chroma policy search
    validation_service.py       Invoice data validation
    push_to_db.py               MySQL persistence
  database/
    models.py                   Pydantic invoice models
  utils/
    approval_rules.py           Approval thresholds and routing
company_policies/               Company policy text files (.txt)
Dataset/                        Source data and sample invoice PDF
uploads/                        Reserved for uploaded files (uploads are processed in memory)
requirements.txt                Python dependencies
```

## Requirements

- Windows, macOS, or Linux
- Python 3.13 (the project has been tested with Python 3.13)
- MySQL server with an existing database; defaults to `localhost:3306`, database `info`
- Ollama running locally with the `bge-m3` embedding model available
- A Groq API key

## Setup

Activate the project virtual environment, or create one:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Pull the embedding model if it is not already installed:

```powershell
ollama pull bge-m3
```

Make sure Ollama is running. On Windows, the Ollama desktop application normally starts its local service.

## Environment configuration

Create a `.env` file in the project root. Add the values locally and do not commit this file:

```dotenv
GroqKEY=your_groq_api_key
user1=your_mysql_username
pass1=your_mysql_password

# Optional overrides
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=info
GROQ_MODEL=openai/gpt-oss-20b
OLLAMA_EMBEDDING_MODEL=bge-m3
```

The MySQL database must already exist. On the first successful save, the app creates an `invoices` table if needed. The MySQL user needs permission to create and write to that table.

## Run the application

From the project root:

```powershell
streamlit run app/main.py
```

The root-level `app.py` is also retained as a launcher:

```powershell
streamlit run app.py
```

Streamlit prints the local URL, usually `http://localhost:8501`.

## Invoice processing and database behavior

Each uploaded PDF is processed in this order:

1. Extract text with PDFMiner and OCR scanned pages locally.
2. Classify the invoice and extract invoice fields with Groq structured output.
3. Retrieve relevant policy passages from `company_policies/` using Ollama and Chroma.
4. Validate fields and totals, then determine approval authority using `app/utils/approval_rules.py`.
5. Save automatically if the required invoice details are present and validation has no errors. Otherwise, display the extracted fields and wait for the user to select **Push to database anyway**.

The MySQL table stores searchable columns for invoice number, vendor, and total amount, plus the complete `InvoiceProcessingResult` as JSON. Reprocessing the same source file and invoice identity updates the matching row instead of creating another one.

Policy text files are indexed in the local Chroma store at `.db_invoice_policies/`. That directory is generated locally and is not the MySQL invoice-record database.

## Policy files

Place policy `.txt` files in `company_policies/`. The application searches those files for relevant guidance during invoice review. The current policy text files are copied from the original sources in `Dataset/`.

## Security notes

- Keep `.env` out of source control; `.gitignore` already excludes it.
- Do not expose API keys or database passwords in screenshots, logs, or chat.
- Uploaded PDFs are read from memory and are not written into `uploads/` by the current application.
- Invoice text is sent to Groq for classification and extraction. PDF parsing and OCR run locally.
