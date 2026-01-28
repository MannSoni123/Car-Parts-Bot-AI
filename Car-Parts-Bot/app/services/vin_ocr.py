"""
vin_ocr.py
Clean image-only OCR pipeline:
1. Download image bytes from Meta Graph API
2. Run OCR (Tesseract or GPT Vision)
3. Extract chassis/VIN number
"""

from __future__ import annotations
import base64
import io
import json
import re
from typing import Tuple, Dict, Any

import requests
from flask import current_app
from openai import OpenAI


# --------------------------
# Utility: VIN Extractor
# --------------------------

# def extract_vin_from_text(text: str) -> str | None:
#     """
#     Extract a standard 17-character VIN.
#     """
#     match = re.search(r"[A-HJ-NPR-Za-hj-npr-z0-9]{17}", text)
#     return match.group(0) if match else None


# --------------------------
# Meta Media Downloader
# --------------------------

def download_media_blob(media_id: str) -> Tuple[bytes, str | None]:
    """
    Download raw media bytes from Meta Graph API.
    This function is IMPORTED by MediaProcessingService.
    """
    token = current_app.config.get("META_ACCESS_TOKEN")
    version = current_app.config.get("META_GRAPH_VERSION", "v18.0")

    if not token:
        raise RuntimeError("META_ACCESS_TOKEN not configured.")

    # Step 1: fetch metadata (URL + mime)
    info_url = f"https://graph.facebook.com/{version}/{media_id}"
    headers = {"Authorization": f"Bearer {token}"}

    info_resp = requests.get(info_url, headers=headers, timeout=10)
    info_resp.raise_for_status()
    info_json = info_resp.json()

    download_url = info_json.get("url")
    mime_type = info_json.get("mime_type")

    if not download_url:
        raise RuntimeError(f"Could not resolve download URL for media_id={media_id}")

    # Step 2: download actual bytes
    blob_resp = requests.get(download_url, headers=headers, timeout=20)
    blob_resp.raise_for_status()

    return blob_resp.content, mime_type or blob_resp.headers.get("Content-Type")


# # --------------------------
# # MAIN: VIN OCR Runner
# # --------------------------

# def run_chassis_ocr(img_bytes: bytes, content_type: str) -> Dict[str, Any]:
#     """
#     Runs OCR using GPT Vision (recommended) OR local Tesseract.
#     Returns:
#       { "text": "...", "chassis": "...", "confidence": 0.9 }
#     """
#     provider = (current_app.config.get("IMAGE_OCR_PROVIDER") or "gpt").lower()

#     if provider in {"gpt", "openai", "vision"}:
#         print("🤖 Running OCR via OpenAI Vision...")
#         return _run_openai_vision_ocr(img_bytes, content_type)

#     elif provider in {"tesseract", "local"}:
#         print("🖥️ Running OCR via local Tesseract...")
#         return _run_local_tesseract_ocr(img_bytes)

#     raise RuntimeError(f"Unsupported OCR provider: {provider}")


# --------------------------
# Option A: OpenAI Vision OCR
# --------------------------

def extract_text_from_image(img_bytes: bytes, content_type: str) -> str:
    """
    General OCR using GPT Vision. Returns the raw extracted text description.
    """
    api_key = current_app.config.get("OPENAI_API_KEY")
    client = OpenAI(api_key=api_key)
    model = current_app.config.get("OPENAI_VISION_MODEL") or "gpt-4o-mini"
    
    image_b64 = base64.b64encode(img_bytes).decode("utf-8")
    mime = content_type or "image/jpeg"
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are an OCR assistant."},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "1. Transcribe any visible text, especially VINs and remove spaces from it or Part Numbers.\n2. If this is a photo of a dashboard warning light, identify the symbol (e.g. 'Check Engine Light', 'Oil Pressure Low').\n3. If this is a photo of a car part, name the part (e.g. 'Alternator', 'Shock Absorber').\n\nReturn the text and/or the visual description."},
                        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_b64}"}}
                    ]
                }
            ],
            max_tokens=1000
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"OCR Error: {e}")
        return ""



# def _parse_json_response(payload: str) -> Tuple[str, float]:
#     """Parse JSON returned by GPT Vision."""
#     try:
#         clean = payload.strip()

#         # Remove markdown fences
#         if clean.startswith("```"):
#             clean = "\n".join(clean.splitlines()[1:-1])

#         data = json.loads(clean)

#         # Accept multiple possible field names
#         text = (
#             data.get("text") or
#             data.get("vin") or
#             data.get("VIN") or
#             data.get("chassis") or
#             data.get("chassis_number") or
#             ""
#         )

#         confidence = float(
#             data.get("confidence") or
#             data.get("score") or
#             0.7
#         )

#         return text.strip(), confidence

#     except Exception as exc:
#         print("❌ JSON parse failed:", exc)
#         return payload.strip(), 0.6


# # --------------------------
# # Option B: Local Tesseract OCR
# # --------------------------

# def _run_local_tesseract_ocr(img_bytes: bytes) -> Dict[str, Any]:
#     """If someone wants to use local OCR instead of GPT."""

#     try:
#         from PIL import Image
#         import pytesseract
#     except Exception:
#         raise RuntimeError("Tesseract not installed. Switch provider to GPT.")

#     image = Image.open(io.BytesIO(img_bytes)).convert("L")
#     text = pytesseract.image_to_string(image)
#     chassis = extract_vin_from_text(text)
#     return {
#         "text": text,
#         "chassis": chassis,
#         "confidence": 0.7,
#     }
