"""RAG: chunking + embedding + in-memory cosine search.

Adapted from EduMentorAI/indexing and retrievers — stripped down
for a JSON-file demo store (no Milvus). Embeddings come from Gemini
(text-embedding-004) so we don't need a heavy local model.
"""
from __future__ import annotations

import hashlib
import math
import re
from functools import lru_cache
from typing import Iterable

import numpy as np

from app.config import settings
from app.storage import load_chunks


# -------- chunking --------

def split_into_chunks(text: str, target_chars: int = 900, overlap: int = 150) -> list[str]:
    text = re.sub(r"[ \t]+", " ", text).strip()
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]

    chunks: list[str] = []
    buf = ""
    for p in paragraphs:
        if len(buf) + len(p) + 2 <= target_chars:
            buf = f"{buf}\n\n{p}" if buf else p
        else:
            if buf:
                chunks.append(buf)
            if len(p) <= target_chars:
                buf = p
            else:
                for i in range(0, len(p), target_chars - overlap):
                    chunks.append(p[i : i + target_chars])
                buf = ""
    if buf:
        chunks.append(buf)
    return chunks


# -------- embeddings --------

@lru_cache(maxsize=1)
def _get_genai_client():
    if not settings.GEMINI_API_KEY:
        return None
    try:
        from google import genai

        return genai.Client(api_key=settings.GEMINI_API_KEY)
    except Exception:
        return None


def _normalize(vec: list[float]) -> list[float]:
    arr = np.array(vec, dtype=np.float32)
    n = np.linalg.norm(arr)
    if n == 0:
        return arr.tolist()
    return (arr / n).tolist()


def _hash_embed(text: str, dim: int = 384) -> list[float]:
    """Deterministic fallback embedding (token hashing) — keeps demo runnable
    when GEMINI_API_KEY is missing or quota is exhausted. Not as good as a
    real model, but enough for RAG over 11 chunks."""
    vec = np.zeros(dim, dtype=np.float32)
    for tok in re.findall(r"\w+", text.lower()):
        h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
        idx = h % dim
        sign = 1.0 if (h >> 16) & 1 else -1.0
        vec[idx] += sign
    n = np.linalg.norm(vec)
    if n > 0:
        vec /= n
    return vec.tolist()


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Atomic: every returned vector has the same dimension. Either all chunks
    come from Gemini (3072-d) or all come from the hash fallback (384-d)."""
    import time

    client = _get_genai_client()
    if client is None:
        return [_hash_embed(t) for t in texts]

    BATCH = 80  # Gemini hard limit is 100 per request
    out: list[list[float]] = []
    for start in range(0, len(texts), BATCH):
        batch = texts[start : start + BATCH]
        batch_vecs: list[list[float]] | None = None
        for attempt in range(3):
            try:
                resp = client.models.embed_content(
                    model="gemini-embedding-001",
                    contents=batch,
                )
                vecs: list[list[float]] = []
                for emb in resp.embeddings:
                    values = list(getattr(emb, "values", []) or [])
                    if not values:
                        raise ValueError("empty embedding values")
                    vecs.append(_normalize(values))
                batch_vecs = vecs
                break
            except Exception as e:
                msg = str(e)
                if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "503" in msg:
                    m = re.search(r"retry in ([\d.]+)", msg)
                    delay = int(float(m.group(1))) + 2 if m else (30 if attempt == 0 else 60)
                    print(
                        f"[rag] embedding batch {start}-{start + len(batch)} "
                        f"rate limited, sleeping {delay}s (attempt {attempt + 1}/3)..."
                    )
                    time.sleep(min(delay, 90))
                else:
                    print(
                        f"[rag] embedding batch {start}-{start + len(batch)} "
                        f"failed ({msg[:120]})"
                    )
                    break
        if batch_vecs is None:
            # Give up on Gemini entirely → return all-hash for consistent dim.
            print(
                f"[rag] Gemini embedding unavailable — falling back to hash "
                f"embedding for ALL {len(texts)} chunks (consistent dim)"
            )
            return [_hash_embed(t) for t in texts]
        out.extend(batch_vecs)
        # light throttle between batches to stay under burst limits
        if start + BATCH < len(texts):
            time.sleep(1.5)
    return out


def embed_query(q: str) -> list[float]:
    return embed_texts([q])[0]


# -------- retrieval --------

_INDEX: dict | None = None  # {book_id: (chunks_list, matrix)}


def _build_index() -> dict:
    chunks = load_chunks()
    index: dict[int, tuple[list[dict], np.ndarray]] = {}
    per_book: dict[int, list[dict]] = {}
    for c in chunks:
        per_book.setdefault(c["book_id"], []).append(c)
    for book_id, items in per_book.items():
        mat = np.array([c["embedding"] for c in items], dtype=np.float32)
        index[book_id] = (items, mat)
    return index


def refresh_index() -> None:
    global _INDEX
    _INDEX = _build_index()


def _index() -> dict:
    global _INDEX
    if _INDEX is None:
        _INDEX = _build_index()
    return _INDEX


def retrieve(book_id: int, query: str, top_k: int | None = None) -> list[dict]:
    top_k = top_k or settings.TOP_K
    idx = _index()
    if book_id not in idx:
        return []
    items, mat = idx[book_id]
    q = np.array(embed_query(query), dtype=np.float32)
    scores = mat @ q  # cosine since we normalized
    order = np.argsort(-scores)[:top_k]
    out = []
    for i in order:
        c = items[int(i)]
        out.append(
            {
                "chunk_id": c["id"],
                "book_id": c["book_id"],
                "chapter": c.get("chapter"),
                "page": c.get("page"),
                "text": c["text"],
                "score": float(scores[int(i)]),
            }
        )
    return out


def format_context(snippets: Iterable[dict]) -> str:
    parts = []
    for s in snippets:
        tag = f"[{s.get('chapter') or 'Đoạn'} · tr.{s.get('page') or '?'}]"
        parts.append(f"{tag}\n{s['text']}")
    return "\n\n---\n\n".join(parts)
