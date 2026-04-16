"""Per-user personalization: reading history, favorites, quiz results, stats.

Stored as a simple JSON file keyed by user id. Demo scale only.
"""
from __future__ import annotations

import json
import time
from threading import Lock
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app import storage
from app.config import settings
from app.routers.auth import require_user

router = APIRouter(prefix="/api/me", tags=["profile"])

STORE_FILE = settings.DATA_DIR / "user_data.json"
_lock = Lock()

_DEFAULT = {"history": [], "favorites": [], "quizzes": []}


def _load_all() -> dict[str, Any]:
    if not STORE_FILE.exists():
        return {}
    try:
        with STORE_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_all(data: dict) -> None:
    with _lock:
        with STORE_FILE.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def _get_user_data(uid: int) -> dict:
    all_data = _load_all()
    key = str(uid)
    return all_data.get(key) or dict(_DEFAULT, history=[], favorites=[], quizzes=[])


def _set_user_data(uid: int, data: dict) -> None:
    all_data = _load_all()
    all_data[str(uid)] = data
    _save_all(all_data)


def _enrich_book(book_id: int) -> dict | None:
    b = storage.get_book(book_id)
    if not b:
        return None
    return {
        "id": b["id"],
        "title": b.get("title"),
        "authors": b.get("authors"),
        "cover_url": b.get("cover_url"),
        "cover_emoji": b.get("cover_emoji"),
        "category": b.get("category"),
    }


# ---------- schemas ----------

class HistoryBody(BaseModel):
    book_id: int
    tab: str | None = None  # which tab they opened


class QuizBody(BaseModel):
    book_id: int
    score: int = Field(ge=0)
    total: int = Field(ge=1)
    topic: str | None = None


# ---------- history ----------

@router.post("/history")
def add_history(body: HistoryBody, user: dict = Depends(require_user)):
    data = _get_user_data(user["sub"])
    history = [h for h in data["history"] if h.get("book_id") != body.book_id]
    history.insert(0, {
        "book_id": body.book_id,
        "tab": body.tab,
        "at": int(time.time()),
    })
    data["history"] = history[:40]
    _set_user_data(user["sub"], data)
    return {"ok": True, "count": len(data["history"])}


@router.get("/history")
def get_history(user: dict = Depends(require_user)):
    data = _get_user_data(user["sub"])
    out = []
    for h in data["history"][:20]:
        b = _enrich_book(h["book_id"])
        if b:
            out.append({**b, "last_tab": h.get("tab"), "at": h.get("at")})
    return {"items": out}


# ---------- favorites ----------

@router.get("/favorites")
def get_favorites(user: dict = Depends(require_user)):
    data = _get_user_data(user["sub"])
    items = []
    for bid in data["favorites"]:
        b = _enrich_book(bid)
        if b:
            items.append(b)
    return {"items": items}


@router.post("/favorites/{book_id}")
def add_favorite(book_id: int, user: dict = Depends(require_user)):
    if not storage.get_book(book_id):
        raise HTTPException(404, "Book not found")
    data = _get_user_data(user["sub"])
    if book_id not in data["favorites"]:
        data["favorites"].insert(0, book_id)
        _set_user_data(user["sub"], data)
    return {"ok": True, "favorited": True}


@router.delete("/favorites/{book_id}")
def remove_favorite(book_id: int, user: dict = Depends(require_user)):
    data = _get_user_data(user["sub"])
    if book_id in data["favorites"]:
        data["favorites"] = [b for b in data["favorites"] if b != book_id]
        _set_user_data(user["sub"], data)
    return {"ok": True, "favorited": False}


# ---------- quiz results ----------

@router.post("/quiz")
def save_quiz(body: QuizBody, user: dict = Depends(require_user)):
    if not storage.get_book(body.book_id):
        raise HTTPException(404, "Book not found")
    data = _get_user_data(user["sub"])
    data["quizzes"].insert(0, {
        "book_id": body.book_id,
        "score": body.score,
        "total": body.total,
        "topic": (body.topic or "").strip() or None,
        "at": int(time.time()),
    })
    data["quizzes"] = data["quizzes"][:50]
    _set_user_data(user["sub"], data)
    return {"ok": True}


@router.get("/quiz")
def get_quiz_history(user: dict = Depends(require_user)):
    data = _get_user_data(user["sub"])
    out = []
    for q in data["quizzes"][:20]:
        b = _enrich_book(q["book_id"])
        out.append({
            "book": b,
            "score": q["score"],
            "total": q["total"],
            "topic": q.get("topic"),
            "at": q.get("at"),
            "percent": round(100 * q["score"] / max(1, q["total"])),
        })
    return {"items": out}


# ---------- stats ----------

@router.get("/stats")
def stats(user: dict = Depends(require_user)):
    data = _get_user_data(user["sub"])
    qs = data["quizzes"]
    avg = 0
    if qs:
        pts = sum(q["score"] / max(1, q["total"]) for q in qs) / len(qs)
        avg = round(pts * 100)
    return {
        "books_read": len(data["history"]),
        "favorites": len(data["favorites"]),
        "quizzes_done": len(qs),
        "avg_score": avg,
    }
