import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_admin
from app.models import Document, User
from app.rag.embeddings import EmbeddingError
from app.rag.ingest import ingest_document
from app.schemas import DocumentOut

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.get("", response_model=list[DocumentOut])
def list_documents(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> list[Document]:
    return list(db.execute(select(Document).order_by(Document.created_at.desc())).scalars())


# NOTE: sync `def` on purpose. Ingestion does blocking work (the Gemini gRPC
# embedding client), so FastAPI must run it in a threadpool, not the event loop —
# a blocking gRPC call inside the running uvloop loop deadlocks.
@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
def upload_document(
    file: UploadFile = File(...),
    title: str | None = Form(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> Document:
    raw = file.file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    try:
        return ingest_document(
            db,
            title=title or file.filename or "Untitled",
            source=file.filename or "upload",
            content_type=file.content_type or "text/plain",
            raw=raw,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except EmbeddingError as exc:
        # Embedding provider failed (e.g. quota/billing/auth). Surface cleanly.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Embedding service unavailable: {exc}. "
            "Check your AI provider credentials/billing, or set AI_PROVIDER=fake.",
        )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> None:
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    db.delete(document)  # chunks cascade
    db.commit()
