"""Authentication: email/password register + login.

No extra deps — uses stdlib hashlib/hmac/json/base64 for signed tokens and
pbkdf2 password hashing. Users persist in data/users.json.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import time
from threading import Lock
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from app.config import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])

USERS_FILE = settings.DATA_DIR / "users.json"
_lock = Lock()
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ---------- storage ----------

def _load_users() -> list[dict[str, Any]]:
    if not USERS_FILE.exists():
        return []
    try:
        with USERS_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_users(users: list[dict]) -> None:
    with _lock:
        with USERS_FILE.open("w", encoding="utf-8") as f:
            json.dump(users, f, ensure_ascii=False, indent=2)


def _find_user(email: str) -> dict | None:
    email = email.strip().lower()
    for u in _load_users():
        if u.get("email", "").lower() == email:
            return u
    return None


def _insert_user(user: dict) -> dict:
    users = _load_users()
    user["id"] = max((u.get("id", 0) for u in users), default=0) + 1
    user["created_at"] = int(time.time())
    users.append(user)
    _save_users(users)
    return user


# ---------- password ----------

def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return f"pbkdf2${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt_b64, hash_b64 = stored.split("$", 2)
        if scheme != "pbkdf2":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
        return hmac.compare_digest(dk, expected)
    except Exception:
        return False


# ---------- tokens (compact HMAC-signed JSON) ----------

def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def mint_token(user: dict) -> str:
    payload = {
        "sub": user["id"],
        "email": user["email"],
        "name": user.get("name") or user["email"].split("@")[0],
        "exp": int(time.time()) + settings.AUTH_TOKEN_TTL,
    }
    body = _b64url(json.dumps(payload, separators=(",", ":")).encode())
    sig = hmac.new(settings.AUTH_SECRET.encode(), body.encode(), hashlib.sha256).digest()
    return f"{body}.{_b64url(sig)}"


def verify_token(token: str) -> dict | None:
    try:
        body, sig_b64 = token.split(".", 1)
        expected = hmac.new(settings.AUTH_SECRET.encode(), body.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _b64url_decode(sig_b64)):
            return None
        payload = json.loads(_b64url_decode(body))
        if payload.get("exp", 0) < int(time.time()):
            return None
        return payload
    except Exception:
        return None


def current_user(request: Request) -> dict | None:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return verify_token(auth[7:])
    return None


def require_user(request: Request) -> dict:
    user = current_user(request)
    if not user:
        raise HTTPException(401, "Chưa đăng nhập")
    return user


# ---------- schemas ----------

class RegisterBody(BaseModel):
    email: str
    password: str = Field(min_length=6, max_length=128)
    name: str | None = None
    student_id: str | None = None  # MSV
    birthdate: str | None = None  # ISO yyyy-mm-dd
    major: str | None = None

    @field_validator("email")
    @classmethod
    def _v_email(cls, v: str) -> str:
        v = (v or "").strip().lower()
        if not _EMAIL_RE.match(v):
            raise ValueError("Email không hợp lệ")
        return v

    @field_validator("student_id")
    @classmethod
    def _v_msv(cls, v: str | None) -> str | None:
        v = (v or "").strip()
        if not v:
            return None
        if not re.match(r"^[A-Za-z0-9]{4,20}$", v):
            raise ValueError("Mã sinh viên không hợp lệ")
        return v.upper()

    @field_validator("birthdate")
    @classmethod
    def _v_dob(cls, v: str | None) -> str | None:
        v = (v or "").strip()
        if not v:
            return None
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", v):
            raise ValueError("Ngày sinh không hợp lệ")
        return v


class LoginBody(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def _v_email(cls, v: str) -> str:
        return (v or "").strip().lower()


def _public_user(u: dict) -> dict:
    return {
        "id": u["id"],
        "email": u["email"],
        "name": u.get("name") or u["email"].split("@")[0],
        "student_id": u.get("student_id"),
        "birthdate": u.get("birthdate"),
        "major": u.get("major"),
    }


# ---------- routes ----------

@router.post("/register")
def register(body: RegisterBody):
    if _find_user(body.email):
        raise HTTPException(409, "Email đã được đăng ký")
    user = _insert_user({
        "email": body.email,
        "name": (body.name or "").strip() or body.email.split("@")[0],
        "student_id": body.student_id,
        "birthdate": body.birthdate,
        "major": (body.major or "").strip() or None,
        "password_hash": _hash_password(body.password),
    })
    return {"token": mint_token(user), "user": _public_user(user)}


@router.post("/login")
def login(body: LoginBody):
    user = _find_user(body.email)
    if not user or not user.get("password_hash"):
        raise HTTPException(401, "Email hoặc mật khẩu không đúng")
    if not _verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "Email hoặc mật khẩu không đúng")
    return {"token": mint_token(user), "user": _public_user(user)}


@router.get("/me")
def me(request: Request):
    payload = current_user(request)
    if not payload:
        return {"user": None}
    user = _find_user(payload["email"])
    return {"user": _public_user(user) if user else None}


@router.post("/logout")
def logout():
    return {"ok": True}
