"""Simple JSON-file store for books and chunks. Demo scale only."""
import json
from threading import Lock
from typing import Any

from app.config import settings

_lock = Lock()

BOOKS_FILE = settings.DATA_DIR / "books.json"
CHUNKS_FILE = settings.DATA_DIR / "chunks.json"


def _read(path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _write(path, data) -> None:
    with _lock:
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def load_books() -> list[dict]:
    return _read(BOOKS_FILE)


def save_books(books: list[dict]) -> None:
    _write(BOOKS_FILE, books)


def get_book(book_id: int) -> dict | None:
    for b in load_books():
        if b["id"] == book_id:
            return b
    return None


def load_chunks() -> list[dict]:
    """Each chunk: {id, book_id, chapter, page, text, embedding}"""
    return _read(CHUNKS_FILE)


def save_chunks(chunks: list[dict]) -> None:
    _write(CHUNKS_FILE, chunks)
