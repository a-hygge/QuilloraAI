"""Visualize: excerpt -> image prompt -> Gemini / fal.ai / stub."""
from __future__ import annotations

import base64
import logging
import uuid

import httpx
from fastapi import APIRouter
from pydantic import BaseModel

from app import llm
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/visualize", tags=["visualize"])


class VisualizeBody(BaseModel):
    excerpt: str
    book_id: int | None = None


GEMINI_IMAGE_MODELS = [
    "gemini-2.5-flash-image",
    "gemini-2.0-flash-preview-image-generation",
    "gemini-2.0-flash-exp-image-generation",
]


def _call_gemini_image(prompt: str) -> str | None:
    """Use Gemini's native image generation model to turn a prompt into a PNG.
    Tries several model aliases since Google rotates them frequently."""
    if not settings.GEMINI_API_KEY:
        return None
    try:
        from google import genai
        from google.genai import types
    except Exception as e:
        logger.warning("google.genai import failed: %s", e)
        return None

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    for model in GEMINI_IMAGE_MODELS:
        try:
            resp = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE", "TEXT"],
                ),
            )
            for cand in resp.candidates or []:
                parts = getattr(cand.content, "parts", None) or []
                for part in parts:
                    inline = getattr(part, "inline_data", None)
                    if inline and getattr(inline, "data", None):
                        data = inline.data
                        b64 = data if isinstance(data, str) else base64.b64encode(data).decode("ascii")
                        mime = getattr(inline, "mime_type", None) or "image/png"
                        logger.info("Gemini image gen OK via %s", model)
                        return f"data:{mime};base64,{b64}"
            logger.info("Gemini image gen via %s returned no inline image part", model)
        except Exception as e:
            msg = str(e)
            # 404 = model not available in free tier → try next alias silently
            if "404" not in msg and "NOT_FOUND" not in msg:
                logger.warning("Gemini image gen failed via %s: %s", model, msg[:200])
    return None


FAL_MODELS = [
    # text-to-image, fast
    "fal-ai/fast-sdxl",
    "fal-ai/fast-lightning-sdxl",
    "fal-ai/fast-lcm-diffusion",
]


async def _call_fal(prompt: str) -> str | None:
    if not settings.FAL_API_KEY:
        return None
    headers = {
        "Authorization": f"Key {settings.FAL_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "prompt": prompt,
        "image_size": "square_hd",
        "num_images": 1,
        "enable_safety_checker": False,
    }
    async with httpx.AsyncClient(timeout=90.0) as client:
        for model in FAL_MODELS:
            url = f"https://fal.run/{model}"
            try:
                r = await client.post(url, headers=headers, json=payload)
                if r.status_code >= 400:
                    logger.warning(
                        "fal.ai %s HTTP %s: %s", model, r.status_code, r.text[:250]
                    )
                    continue
                data = r.json()
                images = data.get("images") or []
                if images and images[0].get("url"):
                    logger.info("fal.ai OK via %s", model)
                    return images[0]["url"]
                logger.warning("fal.ai %s returned no images: %s", model, str(data)[:250])
            except Exception as e:
                logger.warning("fal.ai %s call failed: %r", model, e)
    return None


def _stub_svg_data_url(prompt: str) -> str:
    """Return a tasteful SVG data URL so the UI always has something to render."""
    import base64

    safe = prompt.replace("&", "&amp;").replace("<", "&lt;")[:120]
    svg = f"""<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 600 600'>
  <defs>
    <linearGradient id='g' x1='0' y1='0' x2='1' y2='1'>
      <stop offset='0%' stop-color='#FAF7F2'/>
      <stop offset='100%' stop-color='#C2552D'/>
    </linearGradient>
  </defs>
  <rect width='600' height='600' fill='url(#g)'/>
  <g fill='#1E3A5F' opacity='0.85'>
    <circle cx='300' cy='240' r='120'/>
    <rect x='120' y='380' width='360' height='14' rx='7'/>
    <rect x='160' y='410' width='280' height='10' rx='5'/>
    <rect x='190' y='436' width='220' height='10' rx='5'/>
  </g>
  <text x='50%' y='560' text-anchor='middle' font-family='Georgia, serif'
        font-size='20' fill='#1A1A1A'>LibMate · minh hoạ tạm</text>
  <title>{safe}</title>
</svg>"""
    b64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{b64}"


@router.post("")
async def visualize(body: VisualizeBody):
    prompt = llm.excerpt_to_image_prompt(body.excerpt)

    # 1. Prefer Gemini native image generation (uses existing GEMINI_API_KEY)
    image_url = _call_gemini_image(prompt)
    source = "gemini"

    # 2. Fall back to fal.ai if the user configured it
    if image_url is None:
        image_url = await _call_fal(prompt)
        if image_url is not None:
            source = "fal"

    # 3. Final fallback: an editorial SVG placeholder
    used_stub = image_url is None
    if used_stub:
        image_url = _stub_svg_data_url(prompt)
        source = "stub"

    return {
        "id": str(uuid.uuid4()),
        "prompt": prompt,
        "image_url": image_url,
        "source": source,
        "stub": used_stub,
    }
