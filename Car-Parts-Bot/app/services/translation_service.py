import os
import re
from typing import Tuple
from openai import OpenAI
from flask import current_app

BASE_LANG = "en"

# Non-Latin Unicode Script Range Patterns
SCRIPT_PATTERNS = [
    (re.compile(r'[\u0A80-\u0AFF]'), 'gu'),  # Gujarati
    (re.compile(r'[\u0900-\u097F]'), 'hi'),  # Devanagari (Hindi, Marathi)
    (re.compile(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]'), 'ar'),  # Arabic, Urdu, Persian
    (re.compile(r'[\u0400-\u04FF]'), 'ru'),  # Cyrillic (Russian, Ukrainian)
    (re.compile(r'[\u3040-\u309F\u30A0-\u30FF]'), 'ja'),  # Japanese Hiragana/Katakana
    (re.compile(r'[\u4E00-\u9FFF]'), 'zh'),  # Chinese Hanzi
    (re.compile(r'[\uAC00-\uD7AF]'), 'ko'),  # Korean Hangul
    (re.compile(r'[\u0B80-\u0BFF]'), 'ta'),  # Tamil
    (re.compile(r'[\u0C00-\u0C7F]'), 'te'),  # Telugu
    (re.compile(r'[\u0980-\u09FF]'), 'bn'),  # Bengali
    (re.compile(r'[\u0D00-\u0D7F]'), 'ml'),  # Malayalam
    (re.compile(r'[\u0E00-\u0E7F]'), 'th'),  # Thai
    (re.compile(r'[\u0590-\u05FF]'), 'he'),  # Hebrew
]

LATIN_KEYWORDS = [
    (re.compile(r'\b(hola|buenos dias|buenas tardes|buenas noches|gracias|por favor|repuestos|piezas|coche|frenos|amortiguador)\b', re.I), 'es'),
    (re.compile(r'\b(bonjour|bonsoir|salut|merci|s\'il vous plait|pieces|pièces|voiture|freins|amortisseur)\b', re.I), 'fr'),
    (re.compile(r'\b(hallo|guten tag|guten morgen|danke|bitte|ersatzteile|auto|bremsen|stoßdämpfer)\b', re.I), 'de'),
    (re.compile(r'\b(ola|olá|bom dia|boa tarde|obrigado|obrigada|por favor|pecas|peças|carro|freios|amortecedor)\b', re.I), 'pt'),
    (re.compile(r'\b(ciao|buongiorno|buonasera|grazie|per favore|ricambi|macchina|freni|ammortizzatore)\b', re.I), 'it'),
    (re.compile(r'\b(merhaba|selam|gunaydin|günaydın|tesekkurler|teşekkürler|yedek parca|yedek parça|araba|fren)\b', re.I), 'tr'),
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

    def detect_language(self, text: str) -> str:
        text = (text or "").strip()
        if not text:
            return BASE_LANG

        # Numbers, codes, VINs -> English
        if is_likely_part_or_vin(text):
            return BASE_LANG

        # 1. Instant Unicode Script Detection
        for pattern, lang in SCRIPT_PATTERNS:
            if pattern.search(text):
                return lang

        # 2. Latin Keyword Detection
        for pattern, lang in LATIN_KEYWORDS:
            if pattern.search(text):
                return lang

        # If pure ASCII text with few words and no non-English words, default to English
        is_pure_ascii = all(ord(c) < 128 for c in text)
        if is_pure_ascii and len(text.split()) <= 2 and not any(ord(c) > 127 for c in text):
            return BASE_LANG

        # 3. Fallback: Fast GPT detection for non-ASCII or ambiguous Latin sentences
        try:
            client = self._get_openai_client()
            if client:
                resp = client.chat.completions.create(
                    model="gpt-4.1-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": "Detect the ISO 639-1 language code (e.g. en, es, fr, de, ar, hi, gu). Respond ONLY with the 2-letter code."
                        },
                        {"role": "user", "content": text[:200]}
                    ],
                    temperature=0.0,
                    max_tokens=5
                )
                detected = resp.choices[0].message.content.strip().lower()
                if len(detected) == 2 and detected.isalpha():
                    return detected
        except Exception as e:
            print(f"[TranslationService] GPT detection error: {e}")

        return BASE_LANG

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
                    model="gpt-4.1-mini",
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
                    model="gpt-4.1-mini",
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
