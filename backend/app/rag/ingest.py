"""Document ingestion: extract text -> chunk -> embed -> store in pgvector."""
from __future__ import annotations

import io

from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Document, DocumentChunk
from app.rag.embeddings import embed_texts


def extract_text(raw: bytes, content_type: str, filename: str) -> str:
    """Extract plain text from an uploaded file."""
    name = filename.lower()
    if content_type == "application/pdf" or name.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(raw))
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)
    # Treat everything else (txt, md, html-ish) as UTF-8 text.
    return raw.decode("utf-8", errors="ignore")


def split_text(text: str) -> list[str]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return [c for c in splitter.split_text(text) if c.strip()]


def ingest_document(
    db: Session,
    *,
    title: str,
    source: str,
    content_type: str,
    raw: bytes,
) -> Document:
    """Full ingestion pipeline. Returns the persisted Document."""
    text = extract_text(raw, content_type, source)
    chunks = split_text(text)
    if not chunks:
        raise ValueError("No extractable text found in the document.")

    document = Document(
        title=title,
        source=source,
        content_type=content_type,
        chunk_count=len(chunks),
    )
    db.add(document)
    db.flush()  # assign document.id

    # Embed in batches to stay within request limits.
    batch_size = 100
    for start in range(0, len(chunks), batch_size):
        batch = chunks[start : start + batch_size]
        vectors = embed_texts(batch)
        for offset, (content, vector) in enumerate(zip(batch, vectors)):
            db.add(
                DocumentChunk(
                    document_id=document.id,
                    chunk_index=start + offset,
                    content=content,
                    embedding=vector,
                )
            )

    db.commit()
    db.refresh(document)
    return document
