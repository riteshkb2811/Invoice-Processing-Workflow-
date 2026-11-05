import numpy as np
import pymupdf
import hashlib
import json
from pathlib import Path
from rapidocr_onnxruntime import RapidOCR

from langchain_ollama import OllamaEmbeddings
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma


project_dir = Path(__file__).resolve().parent
pdf_path = project_dir / "Dataset" / "images (1).pdf"
if not pdf_path.is_file():
   raise FileNotFoundError(f"PDF not found: {pdf_path}")

ocr = RapidOCR()
docs = []

for text_path in sorted((project_dir / "Dataset").glob("*.txt")):
   text = text_path.read_text(encoding="utf-8-sig").strip()
   if text:
      docs.append(
         Document(
            page_content=text,
            metadata={"source": text_path.name, "type": "text"},
         )
      )

with pymupdf.open(pdf_path) as pdf:
   for page_number, page in enumerate(pdf, start=1):
      page_text = page.get_text("text").strip()
      if not page_text:
         pixmap = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
         image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
            pixmap.height, pixmap.width, pixmap.n
         )
         results, _ = ocr(image)
         page_text = "\n".join(result[1] for result in (results or []))

      if page_text.strip():
         docs.append(
            Document(
               page_content=page_text,
               metadata={"source": pdf_path.name, "page": page_number - 1},
            )
         )

if not docs:
   raise ValueError(f"No text could be extracted from {pdf_path}; OCR found no text.")

splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
chunks = splitter.split_documents(docs)
if not chunks:
   raise ValueError(f"No text chunks were created from {pdf_path}.")

embeddings = OllamaEmbeddings(model="bge-m3")
vector_store = Chroma(
   embedding_function=embeddings,
   collection_name="invoice_docs",
   persist_directory=str(project_dir / ".db_invoice"),
)
chunk_ids = [
   hashlib.sha256(
      json.dumps(
         {"content": chunk.page_content, "metadata": chunk.metadata},
         sort_keys=True,
         ensure_ascii=False,
      ).encode("utf-8")
   ).hexdigest()
   for chunk in chunks
]
vector_store.add_documents(documents=chunks, ids=chunk_ids)
print("Ingestion complete")
print("Text sources loaded:", len(list((project_dir / "Dataset").glob("*.txt"))))
print("Documents loaded:", len(docs))
print("Chunks embedded:", len(chunks))
