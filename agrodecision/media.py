"""Photo / PDF preparation and the photo-description ("vision observer") step."""
from __future__ import annotations

import base64
import io

from PIL import Image, ImageOps

from .config import settings
from .llm import chat_text, extract_json

MAX_SIDE = 1280


def prepare_image(data: bytes, max_side: int = MAX_SIDE, quality: int = 80) -> tuple[bytes, str]:
    """Return (jpeg_bytes, base64). Downscaling keeps requests small and inside Groq's limits."""
    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img)
    img = img.convert("RGB")
    img.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    jpeg = buf.getvalue()
    return jpeg, base64.b64encode(jpeg).decode("ascii")


def pdf_extract(data: bytes, max_pages: int = 3, min_text_chars: int = 80) -> tuple[str, bytes | None]:
    """Return (text, first_page_png_or_None).

    If the PDF has a text layer (e.g. a lab report) its text is returned.
    If it has no text (scan / photo saved as PDF) page 1 is rendered as an image instead."""
    import fitz  # PyMuPDF

    doc = fitz.open(stream=data, filetype="pdf")
    text = "\n".join(doc[i].get_text() for i in range(min(max_pages, len(doc)))).strip()
    if len(text) >= min_text_chars:
        return text, None
    pix = doc[0].get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
    return "", pix.tobytes("png")


PHOTO_PROMPT = (
    "You are looking at a photo submitted for a crop-health investigation. Crop stated by the farmer: {crop}. "
    "Describe ONLY what is visibly present. Do NOT name a disease, pest or cause. "
    "Return ONE JSON object: "
    '{{"organ": "leaf|fruit|stem|whole plant|root/soil|field|unclear", '
    '"visible_symptoms": ["short factual phrases"], '
    '"colour_and_pattern": "e.g. yellowing between veins, tan spots with dark rim", '
    '"distribution": "e.g. older leaves, one side, patchy", '
    '"pests_or_structures_visible": ["e.g. insects, webbing, white powder, or none"], '
    '"image_quality": "good|fair|poor", "limitations": "what cannot be judged from this photo"}}'
)


def describe_photo(jpeg_b64: str, crop: str, label: str) -> dict:
    s = settings()
    content = [
        {"type": "text", "text": PHOTO_PROMPT.format(crop=crop or "not stated")},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{jpeg_b64}"}},
    ]
    raw = chat_text(s.model_vision, [{"role": "user", "content": content}], max_tokens=600, image_count=1)
    try:
        data = extract_json(raw)
    except ValueError:
        data = {"visible_symptoms": [], "colour_and_pattern": raw[:400], "image_quality": "unknown"}
    data["label"] = label
    return data
