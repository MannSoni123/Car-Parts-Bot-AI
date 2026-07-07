import os
import re
import fasttext
import urllib.request
from deep_translator import GoogleTranslator


# -------------------- CONSTANTS --------------------

BASE_LANG = "en"

FULL_SUPPORT_LANGS = {
    "en", "ar", "hi", "ur", "es", "fr", "pt", "de", "ru", "zh", "it", "ja"
}

FASTTEXT_MODEL_URL = (
    "https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.bin"
)

# Part-number–like input (force English)
PART_PATTERN = re.compile(r"^[A-Za-z0-9\s\-\/\.\+]+$", re.UNICODE)

# Word detection
WORD_REGEX = re.compile(r"[A-Za-z\u0600-\u06FF]+", re.UNICODE)
VOWEL_REGEX = re.compile(r"[aeiouAEIOU\u0621-\u064A]", re.UNICODE)


# -------------------- HELPERS --------------------

def get_model_path() -> str:
    """
    Resolve model path.
    Uses persistent disk on Render if available.
    """
    base_dir = os.getenv("RENDER_DISK_PATH") or os.getcwd()
    return os.path.join(base_dir, "models", "lid.176.bin")


def ensure_fasttext_model(path: str) -> None:
    """
    Download fastText model if missing.
    """
    if os.path.exists(path):
        return

    os.makedirs(os.path.dirname(path), exist_ok=True)
    print("Downloading fastText language detection model...")

    urllib.request.urlretrieve(FASTTEXT_MODEL_URL, path)

    print("fastText model downloaded.")


# -------------------- SERVICE --------------------

class TranslationService:
    _model = None

    @classmethod
    def _get_model(cls):
        if cls._model is None:
            model_path = get_model_path()
            ensure_fasttext_model(model_path)
            cls._model = fasttext.load_model(model_path)
        return cls._model

    @staticmethod
    def _contains_real_word(text: str) -> bool:
        words = WORD_REGEX.findall(text)
        return any(len(w) >= 3 and VOWEL_REGEX.search(w) for w in words)

    # -------------------- LANGUAGE DETECTION --------------------

    def detect_language(self, text: str) -> str:
        text = text.strip()
        if not text:
            return BASE_LANG

        # Part numbers / codes → English
        if PART_PATTERN.match(text):
            return BASE_LANG

        try:
            model = self._get_model()
            # FastText requires single line
            clean_text = text.replace("\n", " ").strip()
            if not clean_text:
                return BASE_LANG

            labels, scores = model.predict(clean_text)
            lang = labels[0].replace("__label__", "")
            confidence = scores[0]
            if confidence < 0.80:
                return BASE_LANG 
            return lang or BASE_LANG
        except Exception as e:
            print("FastText detection failed:", e)
            return BASE_LANG

    # -------------------- TRANSLATION FLOWS --------------------

    def to_base_language(self, text: str) -> tuple[str, str]:
        """
        Detect language and translate input → BASE_LANG.
        Returns: (translated_text, detected_language)
        """
        lang = self.detect_language(text)

        if lang == BASE_LANG:
            return text, lang

        if lang in FULL_SUPPORT_LANGS:
            try:
                translated = GoogleTranslator(
                    source=lang, target=BASE_LANG
                ).translate(text)
                return translated or text, lang
            except Exception as e:
                print("Google Translate failed:", e)

        return text, lang

    def from_base_language(self, text: str, target_language: str) -> str:
        """
        Translate BASE_LANG response → user's language (UI only).
        """
        if not text or target_language == BASE_LANG:
            return text

        if target_language not in FULL_SUPPORT_LANGS:
            return text

        try:
            return GoogleTranslator(
                source=BASE_LANG, target=target_language
            ).translate(text) or text
        except Exception as e:
            print("Google Translate failed:", e)
            return text

    def translate(self, text: str, target_language: str) -> str:
        """
        Generic translation (auto → target).
        """
        if not text:
            return text

        try:
            return GoogleTranslator(
                source="auto", target=target_language
            ).translate(text) or text
        except Exception as e:
            print("Translate failed:", e)
            return text
