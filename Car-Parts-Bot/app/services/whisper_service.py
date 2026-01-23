from openai import OpenAI
from flask import current_app

_client = None

def _get_client():
    global _client
    if _client is None:
        api_key = current_app.config.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY missing in config")
        _client = OpenAI(api_key=api_key)
    return _client


def transcribe_audio(audio_bytes: bytes):
    client = _get_client()

    response = client.audio.transcriptions.create(
        model="gpt-4o-mini-transcribe",
        file=("audio.ogg", audio_bytes, "audio/ogg")
    )
    print(response)

    text = response.text.strip()

    # Try reading language (only available in new transcription models)
    detected_lang = getattr(response, "language", None)

    # If missing, fallback to GPT language detection (very accurate)
    if not detected_lang:
        detected_lang = detect_language_with_gpt(text)

    return text, detected_lang


def detect_language_with_gpt(text: str) -> str:
    client = _get_client()

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "Detect the language of the user's text. Respond ONLY with ISO code (en, hi, gu, ta, etc.)."
            },
            {"role": "user", "content": text}
        ],
        temperature=0
    )

    return resp.choices[0].message.content.strip()


def clean_voice_text(raw_text: str, user_lang: str):
    client = _get_client()

    system_prompt = f"""
        You will receive text in language: {user_lang}.
        You must return a JSON object with exactly two fields:

        1. "english": Cleaned and corrected English version of the text.
        2. "native": Cleaned version written back in the user's original language ({user_lang}).

        Rules:
        - ALWAYS output valid JSON.
        - NEVER output anything outside JSON.
        - If user_lang == "en", 'native' should be the same as 'english'.
        """

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": raw_text}
        ],
        temperature=0.2
    )

    return resp.choices[0].message.content.strip()
