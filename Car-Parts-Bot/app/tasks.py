from .redis_client import redis_client
from rq import Queue
from .services.gpt_service import GPTService
from .services.whatsapp_sender import send_whatsapp_text
from .services.message_processor import process_user_message
from .services.media_service import download_whatsapp_media
from .services.whisper_service import transcribe_audio, clean_voice_text
from .services.document_service import extract_text_from_document
from .services.media_utils import get_media_url
from .services.vin_ocr import extract_text_from_image, download_media_blob
import json

task_queue = Queue("whatsapp", connection=redis_client)

def process_whatsapp_message(user_id, content, msg_type="text", extra_data=None):
    unified_text = ""
    
    try:
        # ---- TEXT ----
        if msg_type == "text":
            unified_text = content

        # ---- IMAGE ----
        elif msg_type == "image":
            # content is media_id. Use download_media_blob (returns bytes, mime)
            img_bytes, content_type = download_media_blob(content)
            unified_text = extract_text_from_image(img_bytes, content_type)
            if not unified_text:
                unified_text = "User sent an image but I could not read it."

        # ---- AUDIO ----
        elif msg_type == "audio":
            url = get_media_url(content)
            audio_bytes = download_whatsapp_media(url)
            raw_text, user_lang = transcribe_audio(audio_bytes)
            parsed = json.loads(clean_voice_text(raw_text, user_lang))
            unified_text = parsed.get("english", "")
            
        # ---- DOCUMENT (PDF/Excel) ----
        elif msg_type == "document":
            # content is media_id, extra_data is filename
            unified_text = extract_text_from_document(user_id, content, extra_data or "file.bin")
            print(unified_text)
        # ---- UNIFIED PIPELINE ----
        if not unified_text.strip():
            unified_text = "(Empty message)"

        reply = process_user_message(user_id, unified_text)
        return send_whatsapp_text(user_id, reply)

    except Exception as e:
        print(f"❌ Task failed: {e}")
        # Send failure message
        fail_msg = "Thank you for your message. I am unable to fetch your details accurately at the moment. Our team will contact you soon to assist you further."
        send_whatsapp_text(user_id, fail_msg)
