from __future__ import annotations

from pathlib import Path
from urllib.parse import quote_plus

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app import llm, rag, storage
from app.config import settings
from app.pdf_ingest import pdf_to_chunks

router = APIRouter(prefix="/api/library", tags=["library"])

MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20MB
UPLOADS_DIR = settings.DATA_DIR / "uploads"


@router.get("/books")
def list_books():
    books = storage.load_books()
    return {"books": books}


@router.get("/books/{book_id}")
def get_book(book_id: int):
    book = storage.get_book(book_id)
    if not book:
        raise HTTPException(404, "Book not found")
    return book


def _resolve_book_pdf(book: dict) -> Path | None:
    """Locate the PDF file for a book.
    - User-uploaded books live in data/uploads/{book_id}.pdf
    - Seed (PTIT) books resolve source_file against the PTIT_REPO folder
    """
    book_id = book.get("id")
    if book.get("user_uploaded"):
        p = UPLOADS_DIR / f"{book_id}.pdf"
        return p if p.exists() else None
    source = book.get("source_file")
    if not source:
        return None
    p = settings.PTIT_REPO / source
    return p if p.exists() else None


@router.get("/books/{book_id}/file")
def get_book_file(book_id: int):
    from urllib.parse import quote

    book = storage.get_book(book_id)
    if not book:
        raise HTTPException(404, "Book not found")
    pdf = _resolve_book_pdf(book)
    if not pdf:
        raise HTTPException(404, "Không tìm thấy file sách.")
    # RFC 5987: ASCII filename + UTF-8 extended filename (for Vietnamese diacritics).
    ascii_name = f"book_{book_id}.pdf"
    utf8_name = quote(pdf.name, safe="")
    headers = {
        "Content-Disposition": (
            f'inline; filename="{ascii_name}"; filename*=UTF-8\'\'{utf8_name}'
        )
    }
    return FileResponse(str(pdf), media_type="application/pdf", headers=headers)


@router.get("/search")
def search(q: str, k: int = 5):
    """Naive semantic search across all books."""
    books = storage.load_books()
    results = []
    for b in books:
        hits = rag.retrieve(b["id"], q, top_k=2)
        for h in hits:
            h["book_title"] = b["title"]
            results.append(h)
    results.sort(key=lambda r: r["score"], reverse=True)
    return {"query": q, "results": results[:k]}


class AskBody(BaseModel):
    question: str
    k: int = 4


@router.post("/ask")
def ask_library(body: AskBody):
    """Library-wide RAG: search across every book, then ask the LLM
    to answer with cross-book citations. Used by the floating chatbot."""
    books = storage.load_books()
    if not books:
        raise HTTPException(400, "Thư viện đang trống.")

    hits: list[dict] = []
    for b in books:
        for h in rag.retrieve(b["id"], body.question, top_k=2):
            h["book_id"] = b["id"]
            h["book_title"] = b["title"]
            hits.append(h)
    hits.sort(key=lambda r: r["score"], reverse=True)
    top = hits[: body.k]
    if not top:
        return {
            "answer": "Mình chưa tìm thấy đoạn nào liên quan trong thư viện. Bạn thử hỏi cách khác nhé.",
            "citations": [],
        }

    context_blocks: list[str] = []
    for h in top:
        tag = f"[{h['book_title']} · {h.get('chapter') or 'Đoạn'} · tr.{h.get('page') or '?'}]"
        context_blocks.append(f"{tag}\n{h['text']}")
    context = "\n\n---\n\n".join(context_blocks)

    answer = llm.answer_with_context(
        question=body.question,
        context=context,
        book_title="Thư viện LibMate (nhiều cuốn sách)",
    )
    return {
        "answer": answer,
        "citations": [
            {
                "book_id": h["book_id"],
                "book_title": h["book_title"],
                "chapter": h.get("chapter"),
                "page": h.get("page"),
                "score": round(h["score"], 3),
                "excerpt": h["text"][:200] + ("…" if len(h["text"]) > 200 else ""),
            }
            for h in top
        ],
    }


@router.post("/upload")
async def upload_book(
    file: UploadFile = File(...),
    title: str = Form(...),
    authors: str = Form(""),
    category: str = Form("Sách bạn đọc"),
    difficulty: int = Form(3),
):
    """Accept a PDF, extract text, chunk + embed, append to store."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Chỉ chấp nhận file .pdf")

    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File vượt quá 20MB")
    if len(data) < 200:
        raise HTTPException(400, "File quá nhỏ hoặc rỗng")

    # Allocate new book id first so the saved PDF filename matches.
    books = storage.load_books()
    next_book_id = (max((b["id"] for b in books), default=0)) + 1

    # Persist PDF permanently so the reader tab can serve it later.
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    pdf_path = UPLOADS_DIR / f"{next_book_id}.pdf"
    pdf_path.write_bytes(data)

    try:
        chunks = pdf_to_chunks(pdf_path, max_chunks=12)
    except Exception as e:
        # Roll back the saved file if extraction blows up.
        try:
            pdf_path.unlink()
        except Exception:
            pass
        raise HTTPException(422, f"Không đọc được PDF: {e}")

    if not chunks:
        try:
            pdf_path.unlink()
        except Exception:
            pass
        raise HTTPException(422, "Không trích được text từ PDF (có thể là PDF ảnh scan).")

    # LLM-generated 1–2 sentence blurb (not a raw chunk).
    ctx = "\n\n".join(chunks[:3])
    summary = llm.describe_book(title.strip(), ctx)

    # Cover: deterministic LoremFlickr so each uploaded book gets a stable image.
    tag = quote_plus(category) if category else "book,reading"
    cover_url = f"https://loremflickr.com/400/560/{tag},book?lock={next_book_id}"

    new_book = {
        "id": next_book_id,
        "title": title.strip(),
        "authors": [a.strip() for a in authors.split(",") if a.strip()] or ["Ẩn danh"],
        "language": "vi",
        "category": category.strip() or "Sách bạn đọc",
        "difficulty": max(1, min(5, int(difficulty))),
        "cover_url": cover_url,
        "cover_emoji": "📖",
        "ai_summary": summary,
        "keywords": [],
        "num_chapters": len(chunks),
        "source_file": file.filename,
        "user_uploaded": True,
    }

    # Embed chunks and append to chunk store.
    vecs = rag.embed_texts(chunks)
    existing_chunks = storage.load_chunks()
    next_chunk_id = (max((c["id"] for c in existing_chunks), default=0)) + 1

    for ci, (text, vec) in enumerate(zip(chunks, vecs), start=1):
        existing_chunks.append(
            {
                "id": next_chunk_id,
                "book_id": next_book_id,
                "chapter": f"Phần {ci}",
                "page": ci,
                "text": text,
                "embedding": vec,
            }
        )
        next_chunk_id += 1

    books.append(new_book)
    storage.save_books(books)
    storage.save_chunks(existing_chunks)
    rag.refresh_index()

    return {"book": new_book, "num_chunks": len(chunks)}
