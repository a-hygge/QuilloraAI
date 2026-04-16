"""Voice chat WebSocket — adapted from p-inno-drawing/routers/voice_chat.py.

Keeps the same protocol so the existing Android client can reconnect
with only a URL change. If GEMINI_API_KEY is missing, the endpoint
returns a friendly text message and closes.

Protocol:
  1. Client connects: WS /ws/voice?book_id=<int>
  2. Client sends JSON {"action":"start"} (optional)
  3. Client streams binary PCM 16-bit LE, 16kHz mono
  4. Server streams binary PCM 16-bit LE, 24kHz mono + JSON transcripts
"""
from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app import rag, storage
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


def _book_system_prompt(book_id: int) -> str:
    book = storage.get_book(book_id)
    if not book:
        return "Bạn là LibMate AI, linh hồn của một cuốn sách trong thư viện PTIT."
    summary = book.get("ai_summary") or ""
    try:
        hits = rag.retrieve(book_id, book["title"] + " ý chính", top_k=5)
    except Exception:
        hits = []
    excerpts = "\n\n".join(h["text"] for h in hits) if hits else ""
    return (
        f"Bạn đóng vai 'linh hồn' của cuốn sách '{book['title']}' trong thư viện PTIT. "
        f"Giọng điệu: điềm đạm, học thuật, ấm áp. Luôn trả lời tiếng Việt trừ khi người dùng "
        f"đổi ngôn ngữ. Bám sát nội dung dưới đây, nếu không biết thì nói thật.\n\n"
        f"### Tóm tắt sách\n{summary}\n\n### Trích đoạn quan trọng\n{excerpts}"
    )


@router.websocket("/ws/voice")
async def voice_chat(ws: WebSocket, book_id: int = Query(...)):
    await ws.accept()

    if not settings.GEMINI_API_KEY:
        await ws.send_json(
            {
                "type": "error",
                "message": "GEMINI_API_KEY chưa được cấu hình — voice chat không khả dụng trong demo.",
            }
        )
        await ws.close()
        return

    try:
        from google import genai
        from google.genai import types
    except Exception as e:
        await ws.send_json({"type": "error", "message": f"google-genai SDK missing: {e}"})
        await ws.close()
        return

    system_prompt = _book_system_prompt(book_id)
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=types.Content(parts=[types.Part.from_text(text=system_prompt)]),
    )

    try:
        async with client.aio.live.connect(model=settings.VOICE_MODEL, config=config) as session:
            await ws.send_json({"type": "ready", "book_id": book_id})

            async def pump_client_to_gemini():
                try:
                    while True:
                        msg = await ws.receive()
                        if msg.get("type") == "websocket.disconnect":
                            return
                        if "bytes" in msg and msg["bytes"] is not None:
                            await session.send_realtime_input(
                                audio=types.Blob(data=msg["bytes"], mime_type="audio/pcm;rate=16000")
                            )
                        elif "text" in msg and msg["text"] is not None:
                            try:
                                data = json.loads(msg["text"])
                            except Exception:
                                continue
                            if data.get("action") == "stop":
                                return
                except WebSocketDisconnect:
                    return

            async def pump_gemini_to_client():
                # session.receive() is per-turn — loop across turns.
                while True:
                    turn = session.receive()
                    async for response in turn:
                        if getattr(response, "data", None):
                            await ws.send_bytes(response.data)
                        if getattr(response, "text", None):
                            await ws.send_json({"type": "transcript", "text": response.text})

            await asyncio.gather(pump_client_to_gemini(), pump_gemini_to_client())
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.exception("Voice session error: %s", e)
        try:
            await ws.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        try:
            await ws.close()
        except Exception:
            pass
