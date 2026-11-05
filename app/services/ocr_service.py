from functools import lru_cache

import numpy as np
import pymupdf
from langchain_community.document_loaders.parsers.pdf import PDFMinerParser
from langchain_core.documents.base import Blob
from rapidocr_onnxruntime import RapidOCR


@lru_cache(maxsize=1)
def get_ocr_engine() -> RapidOCR:
    return RapidOCR()


def extract_pdf_text(pdf_bytes: bytes) -> tuple[str, int, int]:
    blob = Blob.from_data(pdf_bytes, mime_type="application/pdf")
    extracted_pages = list(PDFMinerParser(mode="page").lazy_parse(blob))
    page_texts = []
    ocr_pages = 0
    ocr = None

    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as pdf:
        page_count = len(pdf)
        for page_index, page in enumerate(pdf):
            text = (
                extracted_pages[page_index].page_content.strip()
                if page_index < len(extracted_pages)
                else ""
            )
            if not text:
                if ocr is None:
                    ocr = get_ocr_engine()
                pixmap = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
                image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
                    pixmap.height, pixmap.width, pixmap.n
                )
                results, _ = ocr(image)
                text = "\n".join(item[1] for item in (results or []))
                if text.strip():
                    ocr_pages += 1
            if text.strip():
                page_texts.append(f"[Page {page_index + 1}]\n{text}")

    return "\n\n".join(page_texts), page_count, ocr_pages