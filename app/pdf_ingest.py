"""Shared PDF → chunks helper used by scripts/ingest_ptit.py and the
upload endpoint. Keeps extraction logic in one place."""
from __future__ import annotations

import re
from pathlib import Path


def extract_pdf_text(path: Path, skip_pages: int = 4, max_pages: int = 40) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    total = len(reader.pages)
    start = min(skip_pages, max(0, total - 1))
    pages = reader.pages[start : start + max_pages]
    parts: list[str] = []
    for p in pages:
        try:
            t = p.extract_text() or ""
        except Exception:
            t = ""
        parts.append(t)
    return "\n".join(parts)


def clean_text(text: str) -> str:
    text = text.replace("\xa0", " ").replace("\u200b", "")
    text = re.sub(r"-\n(\w)", r"\1", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_into_chunks(text: str, target_chars: int = 1100) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    buf = ""
    for p in paragraphs:
        if len(p) < 40:
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


def pdf_to_chunks(path: Path, max_chunks: int = 12) -> list[str]:
    raw = extract_pdf_text(path)
    text = clean_text(raw)
    return split_into_chunks(text)[:max_chunks]
