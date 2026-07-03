import hashlib
import math
import re
from functools import lru_cache

import httpx
from langchain_openai import OpenAIEmbeddings

from app.config import settings

_WORD_RE = re.compile(r"[a-z0-9]+")
_GEMINI_API = "https://generativelanguage.googleapis.com/v1beta"


class EmbeddingError(RuntimeError):
    """Raised when the embedding provider fails (quota, auth, network, etc.)."""


@lru_cache
def get_embeddings() -> OpenAIEmbeddings:
    """Shared OpenAI embeddings client (cached)."""
    return OpenAIEmbeddings(
        model=settings.embedding_model,
        api_key=settings.openai_api_key,
    )


def _gemini_embed(texts: list[str]) -> list[list[float]]:
    """Embed via Gemini's REST API.

    We call REST (httpx) rather than langchain-google-genai here because that
    library's gRPC transport deadlocks when invoked from inside the server's
    event loop / threadpool. `outputDimensionality` keeps vectors at
    EMBEDDING_DIM so they fit the pgvector HNSW index (max 2000 dims).
    """
    model = settings.gemini_embedding_model  # e.g. "models/gemini-embedding-001"
    payload = {
        "requests": [
            {
                "model": model,
                "content": {"parts": [{"text": t}]},
                "outputDimensionality": settings.embedding_dim,
            }
            for t in texts
        ]
    }
    resp = httpx.post(
        f"{_GEMINI_API}/{model}:batchEmbedContents",
        params={"key": settings.google_api_key},
        json=payload,
        timeout=60.0,
    )
    resp.raise_for_status()
    return [item["values"] for item in resp.json()["embeddings"]]


def _fake_embed(text: str) -> list[float]:
    """Deterministic, offline "embedding" via feature hashing.

    Not semantically trained, but shared words map to shared dimensions, so
    cosine similarity still reflects keyword overlap — good enough to exercise
    the full retrieval pipeline without calling an API.
    """
    dim = settings.embedding_dim
    vec = [0.0] * dim
    for token in _WORD_RE.findall(text.lower()):
        h = int(hashlib.md5(token.encode()).hexdigest(), 16)
        idx = h % dim
        sign = 1.0 if (h >> 1) & 1 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0:
        vec = [x / norm for x in vec]
    return vec


def embed_texts(texts: list[str]) -> list[list[float]]:
    try:
        if settings.ai_provider == "fake":
            return [_fake_embed(t) for t in texts]
        if settings.ai_provider == "gemini":
            return _gemini_embed(texts)
        return get_embeddings().embed_documents(texts)
    except Exception as exc:  # normalize all provider failures
        raise EmbeddingError(str(exc)) from exc


def embed_query(text: str) -> list[float]:
    try:
        if settings.ai_provider == "fake":
            return _fake_embed(text)
        if settings.ai_provider == "gemini":
            return _gemini_embed([text])[0]
        return get_embeddings().embed_query(text)
    except Exception as exc:
        raise EmbeddingError(str(exc)) from exc
