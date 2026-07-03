"""The RAG answer chain: build a grounded, cited answer and stream it token-by-token."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator

from langchain_openai import ChatOpenAI

from app.config import settings
from app.rag.retriever import RetrievedChunk

SYSTEM_PROMPT = """You are a helpful assistant. Below is context retrieved from the
company knowledge base: a numbered list of sources that may or may not be relevant.

How to answer:
- If the context is relevant to the question, base your answer on it and cite the
  sources you actually use with bracketed numbers like [1], [2].
- If the context is NOT relevant, just answer the question directly from your own
  general knowledge, like a normal helpful assistant.
- IMPORTANT: When answering from general knowledge, do NOT mention the context, the
  knowledge base, or that the information "wasn't found" there. Do NOT apologize and
  do NOT add disclaimers like "I cannot provide this based on the context." Simply
  give the answer as if you were a knowledgeable assistant. Only add citations when
  you actually used a source above.
- Never invent citations or attribute general knowledge to the sources.
- Be concise, friendly, and accurate.

Context:
{context}
"""


def format_context(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return "(no relevant sources found)"
    blocks = []
    for i, c in enumerate(chunks, start=1):
        blocks.append(f"[{i}] (from \"{c.document_title}\")\n{c.content}")
    return "\n\n".join(blocks)


def _get_llm():
    if settings.ai_provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=settings.gemini_chat_model,
            google_api_key=settings.google_api_key,
            temperature=0.2,
        )
    return ChatOpenAI(
        model=settings.chat_model,
        api_key=settings.openai_api_key,
        temperature=0.2,
        streaming=True,
    )


def build_messages(
    question: str,
    chunks: list[RetrievedChunk],
    history: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    """history is a list of (role, content) tuples in chronological order."""
    messages: list[tuple[str, str]] = [
        ("system", SYSTEM_PROMPT.format(context=format_context(chunks)))
    ]
    # Keep the last few turns for conversational continuity.
    for role, content in history[-6:]:
        messages.append(("assistant" if role == "assistant" else "user", content))
    messages.append(("user", question))
    return messages


async def _fake_stream(chunks: list[RetrievedChunk]) -> AsyncGenerator[str, None]:
    """Offline canned answer built from the top retrieved chunk (no API cost)."""
    if not chunks:
        text = "I don't have information about that in the knowledge base yet."
    else:
        snippet = " ".join(chunks[0].content.split())[:300]
        text = f"(offline demo) Based on the knowledge base: {snippet} [1]"
    for word in text.split(" "):
        yield word + " "
        await asyncio.sleep(0.01)  # simulate token streaming


async def stream_answer(
    question: str,
    chunks: list[RetrievedChunk],
    history: list[tuple[str, str]],
) -> AsyncGenerator[str, None]:
    """Yield answer tokens as they are produced by the model."""
    if settings.ai_provider == "fake":
        async for token in _fake_stream(chunks):
            yield token
        return

    llm = _get_llm()
    messages = build_messages(question, chunks, history)
    async for token in llm.astream(messages):
        if token.content:
            yield token.content
