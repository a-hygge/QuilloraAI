"""Ingest PTIT textbooks from the 0xl4p/Giao-Trinh-PTIT repo.

- Extracts text from a curated subset of PDFs (pypdf)
- Chunks and embeds via Gemini (app.rag)
- Fetches real cover images from Google Books API (fallback: LoremFlickr)
- Writes data/books.json + data/chunks.json

Run: python -m scripts.ingest_ptit
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path
from urllib.parse import quote_plus

import httpx

# Force UTF-8 stdout so Vietnamese prints on Windows cp1252 consoles.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import llm, rag, storage  # noqa: E402

PTIT_REPO = Path("d:/New folder (2)/Giao-Trinh-PTIT")

# Curated 10 PTIT IT textbooks. Filename must match the repo exactly.
BOOKS: list[dict] = [
    {
        "file": "Mạng máy tính và internet - 2014.pdf",
        "title": "Mạng máy tính và Internet",
        "authors": ["PTIT"],
        "category": "Mạng & Truyền thông",
        "difficulty": 3,
        "keywords": ["TCP/IP", "OSI", "mạng", "routing"],
        "search_title": "computer networks",
        "flickr_tags": "computer,network,cable",
    },
    {
        "file": "Nhập môn trí tuệ nhân tạo - 2015.pdf",
        "title": "Nhập môn Trí tuệ nhân tạo",
        "authors": ["PTIT"],
        "category": "Trí tuệ nhân tạo",
        "difficulty": 4,
        "keywords": ["AI", "search", "machine learning", "heuristic"],
        "search_title": "artificial intelligence textbook",
        "flickr_tags": "robot,ai,brain",
    },
    {
        "file": "Cấu trúc dữ liệu và giải thuật - 2013.pdf",
        "title": "Cấu trúc dữ liệu và Giải thuật",
        "authors": ["PTIT"],
        "category": "Lập trình cơ bản",
        "difficulty": 3,
        "keywords": ["mảng", "cây", "đồ thị", "sắp xếp"],
        "search_title": "data structures algorithms",
        "flickr_tags": "code,algorithm,binary",
    },
    {
        "file": "Giáo trình hệ điều hành - 2013.pdf",
        "title": "Hệ điều hành",
        "authors": ["PTIT"],
        "category": "Hệ thống",
        "difficulty": 4,
        "keywords": ["process", "scheduling", "memory", "file system"],
        "search_title": "operating systems textbook",
        "flickr_tags": "server,computer,linux",
    },
    {
        "file": "Ngôn ngữ lập trình Java.pdf",
        "title": "Ngôn ngữ lập trình Java",
        "authors": ["PTIT"],
        "category": "Lập trình",
        "difficulty": 3,
        "keywords": ["Java", "OOP", "JVM", "class"],
        "search_title": "java programming",
        "flickr_tags": "java,programming,coffee",
    },
    {
        "file": "Nhập môn công nghệ phần mềm.pdf",
        "title": "Nhập môn Công nghệ phần mềm",
        "authors": ["PTIT"],
        "category": "Kỹ nghệ phần mềm",
        "difficulty": 3,
        "keywords": ["SDLC", "requirement", "design", "testing"],
        "search_title": "software engineering",
        "flickr_tags": "software,developer,team",
    },
    {
        "file": "Kỹ thuật đồ họa - 2016.pdf",
        "title": "Kỹ thuật đồ hoạ",
        "authors": ["PTIT"],
        "category": "Đồ hoạ máy tính",
        "difficulty": 4,
        "keywords": ["rasterization", "transformation", "OpenGL"],
        "search_title": "computer graphics",
        "flickr_tags": "graphics,geometry,render",
    },
    {
        "file": "Giáo trình Cơ sở an toàn thông tin - 2018.pdf",
        "title": "Cơ sở An toàn thông tin",
        "authors": ["PTIT"],
        "category": "An toàn thông tin",
        "difficulty": 4,
        "keywords": ["mã hoá", "CIA", "TLS", "tấn công"],
        "search_title": "information security",
        "flickr_tags": "security,lock,cyber",
    },
    {
        "file": "Kho dữ liệu và khai phá dữ liệu - 2014.pdf",
        "title": "Kho dữ liệu & Khai phá dữ liệu",
        "authors": ["PTIT"],
        "category": "Dữ liệu lớn",
        "difficulty": 4,
        "keywords": ["data warehouse", "OLAP", "clustering", "mining"],
        "search_title": "data mining warehouse",
        "flickr_tags": "data,chart,analytics",
    },
    {
        "file": "Toán rời rạc 1 - 2016.pdf",
        "title": "Toán rời rạc 1",
        "authors": ["PTIT"],
        "category": "Toán học",
        "difficulty": 3,
        "keywords": ["logic", "tập hợp", "đếm", "quan hệ"],
        "search_title": "discrete mathematics",
        "flickr_tags": "math,equation,blackboard",
    },
]


# ---------- PDF extraction ----------

def extract_pdf_text(path: Path, skip_pages: int = 4, max_pages: int = 160) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = reader.pages[skip_pages : skip_pages + max_pages]
    parts: list[str] = []
    for p in pages:
        try:
            t = p.extract_text() or ""
        except Exception:
            t = ""
        parts.append(t)
    return "\n".join(parts)


def clean_text(text: str) -> str:
    # Fix common PDF artefacts: soft hyphen, zero-width chars, repeated whitespace.
    text = text.replace("\xa0", " ").replace("\u200b", "")
    text = re.sub(r"-\n(\w)", r"\1", text)  # de-hyphenate line breaks
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_into_chunks(text: str, target_chars: int = 1100) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    buf = ""
    for p in paragraphs:
        if len(p) < 40:  # skip headers / page numbers
            continue
        if len(buf) + len(p) + 2 <= target_chars:
            buf = f"{buf}\n\n{p}" if buf else p
        else:
            if buf:
                chunks.append(buf)
            buf = p if len(p) <= target_chars else p[:target_chars]
    if buf:
        chunks.append(buf)
    return chunks


# ---------- Cover lookup ----------

def google_books_cover(title_en: str) -> str | None:
    """Try Google Books — works for well-known titles."""
    try:
        r = httpx.get(
            "https://www.googleapis.com/books/v1/volumes",
            params={"q": f"intitle:{title_en}", "maxResults": 1},
            timeout=15.0,
        )
        r.raise_for_status()
        items = r.json().get("items") or []
        if not items:
            return None
        links = items[0].get("volumeInfo", {}).get("imageLinks", {})
        url = links.get("thumbnail") or links.get("smallThumbnail")
        if url and url.startswith("http://"):
            url = "https://" + url[len("http://") :]
        return url
    except Exception:
        return None


def loremflickr_cover(tags: str, lock: int) -> str:
    """Fallback: LoremFlickr serves CC-licensed Flickr photos by tag.
    `lock` param makes the result deterministic so the same book always
    gets the same cover."""
    return f"https://loremflickr.com/400/560/{quote_plus(tags)}?lock={lock}"


# ---------- Main ----------

def _is_mock_blurb(text: str) -> bool:
    if not text:
        return True
    return text.startswith("(Demo mock)") or "GEMINI_API_KEY" in text[:120]


def main() -> None:
    if not PTIT_REPO.exists():
        print(f"[ingest] PTIT repo not found at {PTIT_REPO}. Clone it first.")
        sys.exit(1)

    # Preserve existing summaries so re-ingesting doesn't wipe good ones when
    # the Gemini quota is exhausted and describe_book falls back to mock.
    existing_by_title: dict[str, str] = {}
    try:
        for b in storage.load_books():
            s = b.get("ai_summary") or ""
            if s and not _is_mock_blurb(s):
                existing_by_title[b["title"]] = s
    except Exception:
        pass

    books_out: list[dict] = []
    chunks_out: list[dict] = []
    all_texts: list[str] = []
    meta: list[tuple[int, str, int]] = []

    chunk_id = 1
    for idx, b in enumerate(BOOKS, start=1):
        pdf_path = PTIT_REPO / b["file"]
        if not pdf_path.exists():
            print(f"[ingest] MISS: {b['file']}")
            continue

        print(f"[ingest] ({idx:02d}) {b['title']}")
        raw = extract_pdf_text(pdf_path)
        text = clean_text(raw)
        chunks = split_into_chunks(text)[:30]  # cap 30 chunks per book — better RAG coverage
        if not chunks:
            print(f"[ingest]   ! no extractable text, skip")
            continue

        cover = google_books_cover(b["search_title"]) or loremflickr_cover(b["flickr_tags"], idx)

        # Try the LLM for a clean blurb; if quota is exhausted and we get a
        # mock reply, keep the previously-saved summary for this title.
        ctx = "\n\n".join(chunks[:3])
        summary = llm.describe_book(b["title"], ctx)
        if _is_mock_blurb(summary) and b["title"] in existing_by_title:
            summary = existing_by_title[b["title"]]
            print(f"[ingest]   ↳ kept previous summary (LLM quota exhausted)")

        books_out.append(
            {
                "id": idx,
                "title": b["title"],
                "authors": b["authors"],
                "language": "vi",
                "category": b["category"],
                "difficulty": b["difficulty"],
                "cover_url": cover,
                "cover_emoji": "📘",  # fallback if image fails to load
                "ai_summary": summary,
                "keywords": b["keywords"],
                "num_chapters": len(chunks),
                "source_file": b["file"],
            }
        )

        for ci, chunk in enumerate(chunks, start=1):
            label = f"Phần {ci}"
            all_texts.append(chunk)
            meta.append((idx, label, ci))

    if not all_texts:
        print("[ingest] Nothing extracted — aborting.")
        return

    print(f"[ingest] Embedding {len(all_texts)} chunks across {len(books_out)} books...")
    vecs = rag.embed_texts(all_texts)

    for (book_id, label, page), text, vec in zip(meta, all_texts, vecs):
        chunks_out.append(
            {
                "id": chunk_id,
                "book_id": book_id,
                "chapter": label,
                "page": page,
                "text": text,
                "embedding": vec,
            }
        )
        chunk_id += 1

    storage.save_books(books_out)
    storage.save_chunks(chunks_out)
    rag.refresh_index()
    print(f"[ingest] Done. {len(books_out)} books, {len(chunks_out)} chunks.")


if __name__ == "__main__":
    main()
