from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app import llm, rag, storage

router = APIRouter(prefix="/api/reader", tags=["reader"])


class AskBody(BaseModel):
    question: str
    top_k: int | None = None


class LengthBody(BaseModel):
    length: str = "200 từ"


class CountBody(BaseModel):
    n: int = 5
    topic: str | None = None


def _require_book(book_id: int) -> dict:
    book = storage.get_book(book_id)
    if not book:
        raise HTTPException(404, "Book not found")
    return book


@router.post("/{book_id}/ask")
def ask(book_id: int, body: AskBody):
    book = _require_book(book_id)
    hits = rag.retrieve(book_id, body.question, top_k=body.top_k)
    if not hits:
        raise HTTPException(400, "Book has not been indexed. Run scripts/ingest.py.")
    context = rag.format_context(hits)
    answer = llm.answer_with_context(body.question, context, book["title"])
    return {
        "answer": answer,
        "citations": [
            {
                "chunk_id": h["chunk_id"],
                "chapter": h["chapter"],
                "page": h["page"],
                "score": round(h["score"], 3),
                "excerpt": h["text"][:240] + ("…" if len(h["text"]) > 240 else ""),
            }
            for h in hits
        ],
    }


@router.post("/{book_id}/summary")
def summary(book_id: int, body: LengthBody):
    book = _require_book(book_id)
    hits = rag.retrieve(book_id, book["title"] + " tóm tắt nội dung chính", top_k=6)
    context = rag.format_context(hits) if hits else (book.get("ai_summary") or "")
    text = llm.summarize(context, book["title"], length=body.length)
    return {"summary": text}


def _clamp_n(n: int, lo: int = 1, hi: int = 20) -> int:
    try:
        n = int(n)
    except Exception:
        n = 5
    return max(lo, min(hi, n))


@router.post("/{book_id}/quiz")
def quiz(book_id: int, body: CountBody):
    book = _require_book(book_id)
    n = _clamp_n(body.n)
    topic = (body.topic or "").strip()
    query = (
        f"{book['title']} {topic}" if topic else f"{book['title']} những khái niệm quan trọng"
    )
    hits = rag.retrieve(book_id, query, top_k=8 if topic else 6)
    context = rag.format_context(hits)
    questions = llm.make_quiz(context, book["title"], n=n, topic=topic or None)
    return {"questions": questions}


@router.post("/{book_id}/flashcards")
def flashcards(book_id: int, body: CountBody):
    book = _require_book(book_id)
    n = _clamp_n(body.n)
    topic = (body.topic or "").strip()
    query = (
        f"{book['title']} {topic}" if topic else f"{book['title']} thuật ngữ định nghĩa"
    )
    hits = rag.retrieve(book_id, query, top_k=8 if topic else 6)
    context = rag.format_context(hits)
    cards = llm.make_flashcards(context, book["title"], n=n, topic=topic or None)
    return {"cards": cards}
