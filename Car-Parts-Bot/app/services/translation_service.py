import os
import re
import json
import hashlib
from typing import Tuple
from openai import OpenAI
from flask import current_app
from app.redis_client import redis_client

BASE_LANG = "en"

# Fast non-Latin script mapping as immediate pre-filter
SCRIPT_PATTERNS = [
    (re.compile(r'[\u0A80-\u0AFF]'), 'gu', 'Gujarati'),
    (re.compile(r'[\u0900-\u097F]'), 'hi', 'Hindi'),
    (re.compile(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]'), 'ar', 'Arabic'),
    (re.compile(r'[\u0400-\u04FF]'), 'ru', 'Russian'),
    (re.compile(r'[\u3040-\u309F\u30A0-\u30FF]'), 'ja', 'Japanese'),
    (re.compile(r'[\u4E00-\u9FFF]'), 'zh', 'Chinese'),
    (re.compile(r'[\uAC00-\uD7AF]'), 'ko', 'Korean'),
    (re.compile(r'[\u0B80-\u0BFF]'), 'ta', 'Tamil'),
    (re.compile(r'[\u0C00-\u0C7F]'), 'te', 'Telugu'),
    (re.compile(r'[\u0980-\u09FF]'), 'bn', 'Bengali'),
    (re.compile(r'[\u0D00-\u0D7F]'), 'ml', 'Malayalam'),
    (re.compile(r'[\u0E00-\u0E7F]'), 'th', 'Thai'),
    (re.compile(r'[\u0590-\u05FF]'), 'he', 'Hebrew'),
]

def is_likely_part_or_vin(t: str) -> bool:
    t_clean = re.sub(r'[^A-Za-z0-9]', '', t)
    if not t_clean:
        return False
    # VIN: 17 alphanumeric characters with digits
    if len(t_clean) == 17 and any(c.isdigit() for c in t_clean):
        return True
    # Typical Part Number: has digits and min length 4, majority digits
    digit_count = sum(1 for c in t if c.isdigit())
    if digit_count >= 4 and len(t_clean) >= 5 and (digit_count / len(t_clean) >= 0.4):
        return True
    return False

class TranslationService:
    def __init__(self):
        self._openai_client = None

    def _get_openai_client(self) -> OpenAI | None:
        if self._openai_client:
            return self._openai_client
        try:
            api_key = None
            try:
                api_key = current_app.config.get("OPENAI_API_KEY")
            except Exception:
                pass
            if not api_key:
                api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                self._openai_client = OpenAI(api_key=api_key)
        except Exception:
            pass
        return self._openai_client

    def detect_language_details(self, text: str) -> dict:
        """
        Dynamically detects language of user text using GPT-4o-mini with Redis caching.
        Returns: {"code": "gu", "name": "Gujarati"}
        Supports ALL languages globally without hardcoded limits.
        """
        text = (text or "").strip()
        if not text or is_likely_part_or_vin(text):
            return {"code": BASE_LANG, "name": "English"}

        # Fast Redis cache check
        cache_key = f"lang:det:{hashlib.md5(text.encode('utf-8')).hexdigest()}"
        try:
            cached = redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass

        # Fast script detection for non-Latin characters
        for pattern, lang_code, lang_name in SCRIPT_PATTERNS:
            if pattern.search(text):
                res = {"code": lang_code, "name": lang_name}
                try:
                    redis_client.setex(cache_key, 3600, json.dumps(res))
                except Exception:
                    pass
                return res

        # Pure short ASCII English greeting / generic word check
        is_pure_ascii = all(ord(c) < 128 for c in text)
        if is_pure_ascii and len(text.split()) <= 2:
            common_en = {"hi", "hello", "hey", "need", "car", "part", "parts", "filter", "brake", "pad", "quote", "price", "thanks", "ok"}
            if any(w.lower() in common_en for w in text.split()):
                return {"code": BASE_LANG, "name": "English"}

        # Dynamic GPT-4o-mini detection for any language in the world
        try:
            client = self._get_openai_client()
            if client:
                resp = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "Detect the language of the user text. "
                                "Return JSON with fields 'code' (ISO 639-1 2-letter code) and 'name' (Full English name of language). "
                                "If part number, VIN, or English, return code 'en' and name 'English'."
                            )
                        },
                        {"role": "user", "content": text[:300]}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.0,
                    max_tokens=30
                )
                data = json.loads(resp.choices[0].message.content)
                code = str(data.get("code") or BASE_LANG).strip().lower()
                name = str(data.get("name") or "English").strip()
                res = {"code": code, "name": name}
                try:
                    redis_client.setex(cache_key, 3600, json.dumps(res))
                except Exception:
                    pass
                return res
        except Exception as e:
            print(f"[TranslationService] GPT language detection error: {e}")

        return {"code": BASE_LANG, "name": "English"}

    def detect_language(self, text: str) -> str:
        """
        Returns the 2-letter ISO language code (e.g. 'en', 'gu', 'ar', 'nl', 'pl', 'vi', 'es').
        """
        return self.detect_language_details(text).get("code", BASE_LANG)

    def to_base_language(self, text: str) -> Tuple[str, str]:
        """
        Detect language and translate input -> BASE_LANG (English).
        Returns: (translated_text, detected_language)
        """
        lang = self.detect_language(text)
        if lang == BASE_LANG:
            return text, lang

        # Translate to English
        try:
            client = self._get_openai_client()
            if client:
                resp = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": "Translate the user message to English. Return ONLY the English translation without explanation."
                        },
                        {"role": "user", "content": text}
                    ],
                    temperature=0.0,
                    max_tokens=300
                )
                translated = resp.choices[0].message.content.strip()
                if translated:
                    return translated, lang
        except Exception:
            pass

        return text, lang

    def from_base_language(self, text: str, target_language: str) -> str:
        """
        Translate English text -> target user language.
        """
        if not text or target_language == BASE_LANG:
            return text

        try:
            client = self._get_openai_client()
            if client:
                resp = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": f"Translate the following automotive text into language code '{target_language}'. Keep brand names, part numbers, and URLs unchanged. Return ONLY the translation."
                        },
                        {"role": "user", "content": text}
                    ],
                    temperature=0.0
                )
                translated = resp.choices[0].message.content.strip()
                if translated:
                    return translated
        except Exception:
            pass

        return text
