import hashlib
import os
from functools import lru_cache
from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter


PROJECT_DIR = Path(__file__).resolve().parents[2]
POLICY_DIR = PROJECT_DIR / "company_policies"
POLICY_DB_DIR = PROJECT_DIR / ".db_invoice_policies"


def load_policy_documents() -> list[Document]:
    documents = []
    for path in sorted(POLICY_DIR.glob("*.txt")):
        text = path.read_text(encoding="utf-8-sig").strip()
        if text:
            documents.append(
                Document(page_content=text, metadata={"source": path.name})
            )
    return documents


@lru_cache(maxsize=1)
def get_policy_vector_store() -> Chroma:
    documents = load_policy_documents()
    if not documents:
        raise FileNotFoundError(f"No policy .txt files found in {POLICY_DIR}")

    chunks = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=120,
    ).split_documents(documents)
    store = Chroma(
        collection_name="invoice_policy",
        embedding_function=OllamaEmbeddings(
            model=os.getenv("OLLAMA_EMBEDDING_MODEL", "bge-m3")
        ),
        persist_directory=str(POLICY_DB_DIR),
    )
    ids = [
        hashlib.sha256(
            f"{chunk.metadata.get('source', '')}\n{chunk.page_content}".encode("utf-8")
        ).hexdigest()
        for chunk in chunks
    ]
    existing_ids = set(store._collection.get(ids=ids, include=[]) ["ids"])
    new_chunks = [
        (chunk, chunk_id)
        for chunk, chunk_id in zip(chunks, ids)
        if chunk_id not in existing_ids
    ]
    if new_chunks:
        store.add_documents(
            documents=[chunk for chunk, _ in new_chunks],
            ids=[chunk_id for _, chunk_id in new_chunks],
        )
    return store


def retrieve_policy_context(query: str, k: int = 5) -> tuple[str, list[str]]:
    store = get_policy_vector_store()
    matches = store.similarity_search(query, k=k)
    context = "\n\n".join(
        f"SOURCE: {document.metadata.get('source', 'Policy')}\n{document.page_content}"
        for document in matches
    )
    sources = list(dict.fromkeys(
        document.metadata.get("source", "Policy") for document in matches
    ))
    return context, sources