"""Rewrite ai_summary for every book already in data/books.json using the LLM.
Does NOT touch embeddings — just updates the blurb shown on book cards.

Run: python -m scripts.regen_summaries
"""
from __future__ import annotations

import io
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import llm, storage  # noqa: E402


THROTTLE_SECONDS = 13  # Gemini free tier: 5 requests / minute → ~12s spacing.


def _is_mock(text: str) -> bool:
    return text.startswith("(Demo mock)") or "GEMINI_API_KEY" in text[:120]


def main() -> None:
    # --only-mock flag: re-run only the books whose summary is still a mock.
    only_mock = "--only-mock" in sys.argv

    books = storage.load_books()
    chunks = storage.load_chunks()

    by_book: dict[int, list[dict]] = {}
    for c in chunks:
        by_book.setdefault(c["book_id"], []).append(c)

    targets = [b for b in books if not only_mock or _is_mock(b.get("ai_summary", ""))]
    print(f"[regen] {len(targets)} book(s) to update (throttle {THROTTLE_SECONDS}s between calls)")

    updated = 0
    for i, b in enumerate(targets):
        items = by_book.get(b["id"], [])
        if not items:
            print(f"[skip] {b['title']} — no chunks")
            continue
        ctx = "\n\n".join(c["text"] for c in items[:3])
        print(f"[regen] ({i + 1}/{len(targets)}) {b['title']}")
        new_summary = llm.describe_book(b["title"], ctx)
        if new_summary and len(new_summary) >= 10 and not _is_mock(new_summary):
            b["ai_summary"] = new_summary
            storage.save_books(books)  # save after each call so rate-limit failure doesn't lose progress
            updated += 1
        else:
            print("  ! got mock/empty response, keeping old summary")
        if i < len(targets) - 1:
            time.sleep(THROTTLE_SECONDS)

    print(f"\n[done] Updated {updated}/{len(targets)} book summaries.")


if __name__ == "__main__":
    main()
