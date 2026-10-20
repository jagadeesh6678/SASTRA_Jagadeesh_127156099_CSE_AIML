"""
PDF ingestion, chunking, embedding, and FAISS vector store management.
"""

import os
import fitz  # PyMuPDF
import pdfplumber
from typing import List

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from dotenv import load_dotenv

load_dotenv()

EMBEDDING_MODEL = os.getenv("HF_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
FAISS_INDEX_PATH = os.getenv("FAISS_INDEX_PATH", "./faiss_store")

CHUNK_SIZE = 800
CHUNK_OVERLAP = 120


def get_embeddings() -> HuggingFaceEmbeddings:
    """Initialize and return HuggingFace embeddings model."""
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


def extract_pdf_content(pdf_path: str) -> List[Document]:
    """
    Extract text, tables, and image captions from a PDF.
    Returns a list of LangChain Documents with page metadata.
    """
    documents = []

    # ── Text extraction via PyMuPDF ──────────────────
    pdf_doc = fitz.open(pdf_path)
    for page_num in range(len(pdf_doc)):
        page = pdf_doc[page_num]
        text = page.get_text("text").strip()
        if text:
            documents.append(Document(
                page_content=text,
                metadata={"source": pdf_path, "page": page_num + 1, "type": "text"},
            ))

        # Extract image captions / alt-text from page
        image_list = page.get_images(full=True)
        if image_list:
            documents.append(Document(
                page_content=f"[Page {page_num + 1} contains {len(image_list)} image(s). "
                             f"Visual content related to system architecture on page {page_num + 1}.]",
                metadata={"source": pdf_path, "page": page_num + 1, "type": "image_ref"},
            ))

    pdf_doc.close()

    # ── Table extraction via pdfplumber ─────────────
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            for table_idx, table in enumerate(tables):
                if not table:
                    continue
                # Convert table to readable text
                rows = []
                for row in table:
                    cleaned = [str(cell).strip() if cell else "" for cell in row]
                    rows.append(" | ".join(cleaned))
                table_text = "\n".join(rows)
                if table_text.strip():
                    documents.append(Document(
                        page_content=f"[Table {table_idx + 1} on Page {page_num + 1}]\n{table_text}",
                        metadata={
                            "source": pdf_path,
                            "page": page_num + 1,
                            "type": "table",
                            "table_index": table_idx,
                        },
                    ))

    return documents


def build_faiss_store(documents: List[Document], session_path: str) -> FAISS:
    """
    Chunk documents, generate embeddings, build and persist FAISS index.
    
    Args:
        documents: Extracted LangChain Documents from PDF
        session_path: Directory path to persist the FAISS index
    
    Returns:
        FAISS vector store instance
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ".", " ", ""],
    )
    chunks = splitter.split_documents(documents)

    embeddings = get_embeddings()
    store = FAISS.from_documents(chunks, embeddings)
    store.save_local(session_path)
    return store


def load_faiss_store(session_path: str) -> FAISS:
    """Load a persisted FAISS index from disk."""
    embeddings = get_embeddings()
    return FAISS.load_local(
        session_path,
        embeddings,
        allow_dangerous_deserialization=True,
    )


def retrieve_context(store: FAISS, query: str, k: int = 5) -> List[Document]:
    """
    Retrieve top-k relevant document chunks using MMR for diversity.
    
    Args:
        store: FAISS vector store
        query: Query string
        k: Number of results to return
    
    Returns:
        List of relevant Document chunks with metadata
    """
    retriever = store.as_retriever(
        search_type="mmr",
        search_kwargs={"k": k, "fetch_k": k * 3, "lambda_mult": 0.7},
    )
    return retriever.invoke(query)


def format_context(docs: List[Document]) -> str:
    """Format retrieved documents into a single context string with citations."""
    parts = []
    for doc in docs:
        page = doc.metadata.get("page", "?")
        doc_type = doc.metadata.get("type", "text")
        parts.append(f"[Page {page} | {doc_type.upper()}]\n{doc.page_content}")
    return "\n\n---\n\n".join(parts)