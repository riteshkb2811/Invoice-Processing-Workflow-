# AutoMobile_RAG: Intelligent Invoice Review & Policy Audit System

[![Python](https://img.shields.io/badge/Python-3.13%2B-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.40%2B-FF4B4B.svg)](https://streamlit.io/)
[![LangChain](https://img.shields.io/badge/LangChain-Core%20%7C%20Community-1C3C3C.svg)](https://www.langchain.com/)
[![Groq](https://img.shields.io/badge/Groq-Fast%20Inference-F05A28.svg)](https://groq.com/)
[![Ollama](https://img.shields.io/badge/Ollama-BGE--M3%20Embeddings-white.svg)](https://ollama.com/)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-Vector%20Store-orange.svg)](https://www.trychroma.com/)
[![MySQL](https://img.shields.io/badge/MySQL-Persistence-00758F.svg)](https://www.mysql.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An enterprise-ready **Retrieval-Augmented Generation (RAG)** and document intelligence solution designed to automate accounts payable, invoice verification, compliance auditing, and approval workflows. 

**AutoMobile_RAG** ingests raw digital or scanned invoice PDFs, executes local OCR, classifies invoice categories, extracts structured data with Groq LLMs, audits line items against company policies via ChromaDB vector retrieval, validates GST and arithmetic integrity, routes approvals according to corporate delegation of authority, and archives auditable records to MySQL.

---

## Table of Contents

- [Key Features](#key-features)
- [System Architecture](#system-architecture)
- [Repository Structure](#repository-structure)
- [Technology Stack](#technology-stack)
- [Corporate Policies & Approval Rules](#corporate-policies--approval-rules)
- [Prerequisites](#prerequisites)
- [Installation & Setup](#installation--setup)
- [Environment Variables](#environment-variables)
- [Running the Application](#running-the-application)
- [End-to-End Processing Pipeline](#end-to-end-processing-pipeline)
- [Database Schema](#database-schema)
- [Troubleshooting & FAQ](#troubleshooting--faq)
- [License](#license)

---

## Key Features

- **Hybrid PDF Text & Local OCR Extraction**:
  Fast native text extraction via LangChain `PDFMinerParser` with an automatic, local fallback to `PyMuPDF` (`fitz`) and `RapidOCR` (ONNX Runtime) for scanned invoices and image pages—no data leaves the local machine during OCR.
- **Structured LLM Extraction & Classification**:
  Leverages Groq's low-latency inference engine with strict Pydantic JSON schema constraints to classify invoices (`Purchase`, `Service`, `Utility`, `Other`) and parse critical metadata (invoice number, vendor name, GSTIN, dates, PO numbers, subtotal, CGST, SGST, IGST, and total amounts).
- **Policy-Aware Retrieval-Augmented Generation (RAG)**:
  Indexes company governance policies (GST rules, expense guidelines, PO policies, exception policies) using Ollama's `bge-m3` embedding model and ChromaDB for targeted context retrieval during audits.
- **Deterministic Financial & GST Validation**:
  Performs multi-point validation including 15-character GSTIN format checks, required field verification, and arithmetic reconciliation ($\text{Subtotal} + \sum \text{Taxes} = \text{Total Amount}$).
- **Automated Delegation of Authority (DoA) Routing**:
  Dynamically assigns invoices to approval tiers based on validated amounts and internal compliance thresholds (Auto-Approved, Department Manager, Finance Manager, or Finance Head).
- **Intelligent Database Upsert & Deduplication**:
  Computes a deterministic SHA-256 hash of the invoice identity to prevent duplicate records in MySQL while updating records if re-processed.
- **Human-in-the-Loop Streamlit UI**:
  A modern, dark-themed Streamlit dashboard with tabs for JSON payload review, policy citations, extracted OCR text, and a manual override button (*"Push to database anyway"*) for flagged or incomplete invoices.

---

## System Architecture

```mermaid
flowchart TD
    A["Uploaded Invoice PDF"] --> B["app/services/ocr_service.py"]
    
    subgraph Ingestion ["1. Document Ingestion & OCR"]
        B -->|Native Text Available| C["LangChain PDFMiner"]
        B -->|Scanned / Image Page| D["PyMuPDF + RapidOCR ONNX"]
        C --> E["Extracted Text Buffer"]
        D --> E
    end

    subgraph Intelligence ["2. Groq LLM Structuring"]
        E --> F["app/services/classification_service.py\n(ChatGroq: Purchase/Service/Utility/Other)"]
        E --> G["app/services/extraction_service.py\n(ChatGroq: Structured Pydantic Fields)"]
    end

    subgraph PolicyRAG ["3. Policy Retrieval (RAG)"]
        H["company_policies/*.txt"] --> I["RecursiveCharacterTextSplitter"]
        I --> J["Ollama bge-m3 Embeddings"]
        J --> K[("ChromaDB .db_invoice_policies")]
        F & G --> L["Query Generator"]
        L -->|Similarity Search| K
        K --> M["Retrieved Policy Context & Sources"]
    end

    subgraph ValidationEngine ["4. Verification & Decisioning"]
        G --> N["app/services/validation_service.py\n- GSTIN 15-char format\n- Mandatory field check\n- Subtotal + Tax = Total check"]
        N & M --> O["app/utils/approval_rules.py\n- < ₹10k: Auto Approved\n- ₹10k–₹50k: Dept Manager\n- ₹50k–₹200k: Finance Manager\n- > ₹200k: Finance Head"]
    end

    subgraph Persistence ["5. Storage & UI Desk"]
        O --> P{"Clean & Valid?"}
        P -->|Yes| Q["Auto-save to MySQL (invoices table)"]
        P -->|No / Flagged| R["Human-in-the-Loop Confirmation\n('Push to database anyway')"]
        R -->|User Confirms| Q
        Q --> S["Streamlit Dashboard Display\n(Details, Policy citations, Extracted text)"]
    end
```

---

## Repository Structure

```text
AutoMobile_RAG/
├── .db_invoice/                  # Chroma vector store generated by load_data.py
├── .db_invoice_policies/         # Chroma vector store generated by app RAG service
├── .streamlit/
│   └── config.toml               # Streamlit custom dark UI styling & theme
├── app/
│   ├── database/
│   │   ├── __init__.py
│   │   └── models.py             # Pydantic schemas (Extraction, Classification, Validation)
│   ├── routes/
│   │   ├── __init__.py
│   │   └── invoice_routes.py     # End-to-end invoice review orchestrator
│   ├── services/
│   │   ├── __init__.py
│   │   ├── classification_service.py # Groq structured invoice classification
│   │   ├── extraction_service.py     # Groq structured field extraction
│   │   ├── ocr_service.py            # PDFMiner parser + RapidOCR ONNX fallback
│   │   ├── push_to_db.py             # MySQL connection, table DDL, and upsert logic
│   │   ├── rag_service.py            # Policy loader, Ollama embedding & Chroma index
│   │   └── validation_service.py     # GSTIN, mandatory fields & arithmetic rules
│   ├── utils/
│   │   ├── __init__.py
│   │   └── approval_rules.py         # Corporate approval threshold router
│   ├── __init__.py
│   └── main.py                   # Main Streamlit application dashboard
├── company_policies/             # Active business rules loaded into RAG vector store
│   ├── Expense Policy.txt        # Employee expense guidelines
│   ├── GST Guidelines.txt        # GST validation and tax calculation rules
│   ├── Invoice Approval Policy.txt # Approval limits and routing criteria
│   ├── Invoice Exception Policy.txt# Dispute, mismatch, and exception protocols
│   ├── Payment Terms Policy.txt  # Payment timelines, early payment discounts
│   ├── Purchase Order Policy.txt # PO matching rules and non-PO requirements
│   └── Vendor Policy.txt         # Approved vendor guidelines & onboarding
├── Dataset/                      # Sample documents and offline training data
│   ├── images (1).pdf            # Sample automobile invoice PDF
│   └── *.txt                     # Source policy backups
├── uploads/                      # Upload workspace directory (with .gitkeep)
├── .env                          # Local environment variables (DO NOT COMMIT)
├── .gitignore                    # Git exclusions
├── app.py                        # Root launcher script (calls app.main.render_app)
├── LICENSE                       # MIT License
├── load_data.py                  # Standalone batch data loader & Chroma indexer
├── README.md                     # Comprehensive documentation
└── requirements.txt              # Project Python dependencies
```

---

## Technology Stack

| Component | Library / Tool | Role in Project |
| :--- | :--- | :--- |
| **User Interface** | [Streamlit](https://streamlit.io/) | Interactive dashboard for uploading, reviewing, and confirming invoices |
| **PDF Extraction** | [pdfminer.six](https://github.com/pdfminer/pdfminer.six) / [PyMuPDF](https://pymupdf.readthedocs.io/) | Native selectable text extraction and PDF rendering |
| **OCR Fallback** | [RapidOCR (ONNX)](https://github.com/RapidAI/RapidOCR) | Fast, local text recognition for scanned pages and images |
| **LLM Inference** | [Groq](https://groq.com/) (`ChatGroq`) | Structured JSON extraction and categorization (`openai/gpt-oss-20b`) |
| **Data Validation** | [Pydantic v2](https://docs.pydantic.dev/) | Strict typing, parsing schemas, and serialization |
| **Vector Embeddings** | [Ollama](https://ollama.com/) (`bge-m3`) | High-density semantic embeddings for multi-page policy retrieval |
| **Vector Database** | [ChromaDB](https://www.trychroma.com/) | Persistent vector store for internal corporate policies |
| **Database Storage** | [MySQL](https://www.mysql.com/) / [PyMySQL](https://pymysql.readthedocs.io/) | Relational audit trail and JSON document storage |
| **Orchestration** | [LangChain Core](https://python.langchain.com/) | Document loaders, text splitters, and embedding integrations |

---

## Corporate Policies & Approval Rules

The system automatically checks invoices against the rules defined in `company_policies/`.

### Approval Delegation of Authority (DoA)

| Invoice Total (INR) | Required Approval Tier | Action Status | Rule Source |
| :--- | :--- | :--- | :--- |
| **< ₹10,000** | Automatic Approval | `Auto Approved` | *Invoice Approval Policy* (requires valid fields & math) |
| **₹10,000 – ₹50,000** | Department Manager | `Pending Approval` | Managerial operational expense approval band |
| **₹50,001 – ₹2,00,000** | Finance Manager | `Pending Approval` | Mid-to-high corporate finance approval band |
| **> ₹2,00,000** | Finance Head | `Pending Approval` | Executive approval band |
| **Any Missing / Invalid** | None (Flagged) | `Manual Review` | Blocked until human confirmation |

### Automated Compliance Checks

1. **Mandatory Fields**: Confirms presence of Invoice Number, Vendor Name, Invoice Date, and Total Amount.
2. **GSTIN Format**: Enforces 15-character alphanumeric format for Indian Goods & Services Tax Identification Numbers.
3. **Arithmetic Reconciliation**: Verifies that:
   $$\text{Calculated Total} = \text{Subtotal} + \text{CGST} + \text{SGST} + \text{IGST}$$
   If $|\text{Calculated Total} - \text{Stated Total}| > 1.00$, the invoice is flagged for math discrepancy.

---

## Prerequisites

Before setting up the project, ensure your environment meets the following:

- **Operating System**: Windows 10/11, macOS, or Linux.
- **Python**: Python 3.13 (recommended; 3.10+ supported).
- **MySQL Server**: Running instance (v8.0+) with a database created (default: `info`).
- **Ollama**: Installed and running locally ([Download Ollama](https://ollama.com/)).
- **Groq API Key**: Active key from [Groq Console](https://console.groq.com/).

---

## Installation & Setup

### 1. Clone the Repository

```powershell
git clone https://github.com/riteshkb2811/Invoice-Processing-Workflow-.git
cd Invoice-Processing-Workflow-
```

### 2. Set Up a Virtual Environment

On Windows (PowerShell):
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

On Linux/macOS:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Pull the Embedding Model in Ollama

Ensure Ollama is running, then pull the `bge-m3` embedding model:

```powershell
ollama pull bge-m3
```

> **Note**: Verify that Ollama is accessible at `http://localhost:11434`.

### 5. Configure MySQL Database

Open your MySQL client and create the database specified in your configuration (default is `info`):

```sql
CREATE DATABASE IF NOT EXISTS info CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

---

## Environment Variables

Create a `.env` file in the project root (adjacent to `requirements.txt`):

```dotenv
# ==============================================================================
# Groq API Configuration
# ==============================================================================
GroqKEY=gsk_your_groq_api_key_here
GROQ_MODEL=openai/gpt-oss-20b

# ==============================================================================
# MySQL Database Configuration
# ==============================================================================
user1=your_mysql_username
pass1=your_mysql_password
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=info

# ==============================================================================
# Ollama & Embeddings Configuration
# ==============================================================================
OLLAMA_EMBEDDING_MODEL=bge-m3
```

> [!WARNING]
> Never commit your `.env` file to version control. The `.gitignore` file already excludes `.env` and `.venv/`.

---

## Running the Application

### Option A: Launch Streamlit Dashboard

Run directly with Streamlit:

```powershell
streamlit run app/main.py
```

Or using the root-level launcher:

```powershell
streamlit run app.py
```

Once running, navigate to `http://localhost:8501` in your browser.

### Option B: Standalone Batch Ingestion (`load_data.py`)

To populate `.db_invoice` with the documents and sample PDF located in `Dataset/`:

```powershell
python load_data.py
```

This script extracts text from `Dataset/images (1).pdf` using RapidOCR, reads all policy text files, chunks the content, computes SHA-256 hashes for deduplication, and writes vectors to `.db_invoice/`.

---

## End-to-End Processing Pipeline

1. **Upload**: User uploads one or multiple invoice PDFs via the Streamlit interface.
2. **Local Text Extraction**:
   - `app/services/ocr_service.py` inspects each page.
   - Selectable text is parsed via LangChain `PDFMinerParser`.
   - Blank or scanned pages are rendered into pixmaps via `PyMuPDF` and passed to `RapidOCR` ONNX runtime.
3. **LLM Classification & Parsing**:
   - `app/services/classification_service.py` sends invoice text to Groq with an explicit schema (`Purchase`, `Service`, `Utility`, or `Other`).
   - `app/services/extraction_service.py` extracts dates, tax figures, currency, line totals, vendor names, and GSTIN.
4. **Contextual Policy Audit (RAG)**:
   - `app/services/rag_service.py` executes similarity searches against `.db_invoice_policies` for matching rules.
5. **Deterministic Validation**:
   - `app/services/validation_service.py` tests completeness, validates GSTIN length, and recomputes totals.
6. **Approval Determination**:
   - `app/utils/approval_rules.py` assigns an approval tier (`Auto Approved`, `Department Manager`, `Finance Manager`, `Finance Head`, or `Manual Review`).
7. **Database Persistence**:
   - **Fully clean invoices**: Automatically persisted into the MySQL `invoices` table.
   - **Flagged invoices**: Display a clear warning and push reasons, allowing the user to inspect the tabs and click **Push to database anyway**.

---

## Database Schema

When an invoice is approved or manually confirmed, it is persisted to the `invoices` table in MySQL. The table is automatically initialized on the first insert:

```sql
CREATE TABLE IF NOT EXISTS invoices (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    record_key CHAR(64) NOT NULL UNIQUE,
    source_filename VARCHAR(255) NOT NULL,
    invoice_number VARCHAR(100),
    vendor_name VARCHAR(255),
    total_amount DECIMAL(18, 2),
    review_json JSON NOT NULL,
    pushed_at DATETIME(6) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### Column Descriptions

- `record_key`: SHA-256 hash calculated from invoice number, vendor, date, amount, and filename. Guarantees deduplication.
- `source_filename`: Name of the uploaded PDF file.
- `invoice_number`: Extracted invoice identifier.
- `vendor_name`: Extracted vendor or supplier name.
- `total_amount`: Final payable amount stored as a high-precision decimal.
- `review_json`: Full structured JSON payload containing extraction, classification, validation warnings/errors, and approval decisions.
- `pushed_at`: UTC timestamp of when the record was saved or updated.

---

## Troubleshooting & FAQ

### 1. `RuntimeError: Set GroqKEY in the project .env file...`
Ensure your `.env` file exists in the workspace root and contains `GroqKEY=...` with a valid Groq API token.

### 2. `Connection refused` when connecting to Ollama
Verify that the Ollama desktop service is running:
```powershell
curl http://localhost:11434/api/tags
```
If not running, launch the Ollama application or start the daemon (`ollama serve`).

### 3. RapidOCR fails or dependencies missing
`rapidocr-onnxruntime` requires a working C++ runtime on Windows. If you encounter ONNX runtime errors, ensure Microsoft Visual C++ Redistributable 2015–2022 is installed.

### 4. `Can't connect to MySQL server on 'localhost'`
- Check if your MySQL server is running (e.g., via Windows Services or `net start mysql`).
- Verify credentials (`user1`, `pass1`, `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_DATABASE`) in `.env`.
- Ensure the database `info` (or your custom name) is created.

---

## License

This project is licensed under the [MIT License](LICENSE) - see the `LICENSE` file for details.

Developed by **Ritesh Kamble** (2026).
