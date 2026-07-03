"""Chat endpoint with Server-Sent Events (SSE) token streaming."""
from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.deps import get_current_user
from app.models import Conversation, Message, User
from app.rag.chain import stream_answer
from app.rag.embeddings import EmbeddingError
from app.rag.retriever import RetrievedChunk, retrieve
from app.schemas import ChatRequest, ConversationDetail, ConversationOut

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _get_owned_conversation(db: Session, conversation_id: uuid.UUID, user: User) -> Conversation:
    convo = db.get(Conversation, conversation_id)
    if not convo or convo.user_id != user.id:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return convo


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post("")
def chat(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    question = payload.message.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    # Resolve or create the conversation.
    if payload.conversation_id:
        convo = _get_owned_conversation(db, payload.conversation_id, user)
    else:
        convo = Conversation(user_id=user.id, title=question[:60])
        db.add(convo)
        db.flush()

    # Gather prior history before we add the new message.
    history: list[tuple[str, str]] = [
        (m.role, m.content)
        for m in db.execute(
            select(Message)
            .where(Message.conversation_id == convo.id)
            .order_by(Message.created_at)
        ).scalars()
    ]

    # Persist the user's message.
    db.add(Message(conversation_id=convo.id, role="user", content=question))
    db.commit()

    # Retrieve grounding chunks now (needs the request-scoped session).
    # Embedding the query can call OpenAI, so surface provider errors cleanly.
    try:
        chunks: list[RetrievedChunk] = retrieve(db, question)
    except EmbeddingError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Embedding service unavailable: {exc}. "
            "Check your AI provider credentials/billing, or set AI_PROVIDER=fake.",
        )
    citations = [
        {
            "document_id": c.document_id,
            "document_title": c.document_title,
            "chunk_index": c.chunk_index,
            "snippet": c.content[:280],
        }
        for c in chunks
    ]
    convo_id = convo.id

    async def event_stream():
        # Tell the client which conversation this belongs to.
        yield _sse("meta", {"conversation_id": str(convo_id)})

        answer_parts: list[str] = []
        try:
            async for token in stream_answer(question, chunks, history):
                answer_parts.append(token)
                yield _sse("token", {"text": token})
        except Exception as exc:  # surface model/API errors to the client
            yield _sse("error", {"message": str(exc)})

        answer = "".join(answer_parts)
        yield _sse("citations", {"citations": citations})

        # Persist the assistant message in a fresh session (request session may be closed).
        with SessionLocal() as write_db:
            write_db.add(
                Message(
                    conversation_id=convo_id,
                    role="assistant",
                    content=answer,
                    citations=json.dumps(citations),
                )
            )
            write_db.commit()

        yield _sse("done", {})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Conversation]:
    return list(
        db.execute(
            select(Conversation)
            .where(Conversation.user_id == user.id)
            .order_by(Conversation.created_at.desc())
        ).scalars()
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(
    conversation_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Conversation:
    convo = _get_owned_conversation(db, conversation_id, user)
    # Parse stored citations JSON into the schema shape.
    for m in convo.messages:
        m.citations = json.loads(m.citations) if m.citations else []
    return convo


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conversation_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    convo = _get_owned_conversation(db, conversation_id, user)
    db.delete(convo)  # messages cascade
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
