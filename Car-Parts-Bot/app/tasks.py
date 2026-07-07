
from .redis_client import redis_client
from rq import Queue

from .services.whatsapp_sender import send_whatsapp_text
from .services.message_processor import process_user_message
from .services.media_service import download_whatsapp_media
from .services.whisper_service import transcribe_audio, clean_voice_text
from .services.document_service import extract_text_from_document
from .services.media_utils import get_media_url
from .services.vin_ocr import extract_text_from_image, download_media_blob

import json

import time

task_queue = Queue("whatsapp", connection=redis_client)


def _process_single_item(msg_type, content, extra_data=None):
    """Helper to extract text from a single item (Text/Image/Audio/Doc)."""
    try:
        # ---- TEXT ----
        if msg_type == "text":
            return content

        # ---- IMAGE ----
        elif msg_type == "image":
            # content is media_id
            img_bytes, content_type = download_media_blob(content)
            text = extract_text_from_image(img_bytes, content_type)
            return text if text else "[Image containing no readable text]"

        # ---- AUDIO ----
        elif msg_type == "audio":
            url = get_media_url(content)
            audio_bytes = download_whatsapp_media(url)
            raw_text, user_lang = transcribe_audio(audio_bytes)
            parsed = json.loads(clean_voice_text(raw_text, user_lang))
            return parsed.get("english", "")
            
        # ---- DOCUMENT ----
        elif msg_type == "document":
            # content is media_id, extra_data is filename
            return extract_text_from_document("system", content, extra_data or "file.bin")
            
    except Exception as e:
        print(f"⚠️ item processing failed ({msg_type}): {e}")
        return ""
    return ""

def collect_and_process_batch(user_id):
    """
    Waits 6 seconds to collect all incoming messages, then processes them as one.
    """
    # ✅ IMPORT HERE (lazy import)
    from app import create_app
    app = create_app()
    
    with app.app_context():
        print(f"⏳ Collector started for {user_id}. Waiting 6s...")
        time.sleep(6)
        
        # 1. Drain the buffer
        # 1. Atomic Move: Rename buffer to a temporary processing key
        # This prevents race conditions where new messages arrive *after* lrange but *before* delete
        redis_key = f"user:{user_id}:buffer"
        processing_key = f"user:{user_id}:processing:{int(time.time())}"
        
        try:
            # Atomic rename
            redis_client.rename(redis_key, processing_key)
        except Exception:
            # If rename fails (e.g. key doesn't exist/empty), just cleanup and return
            redis_client.delete(f"user:{user_id}:collecting")
            print(f"⚠️ Batch empty or missing for {user_id}")
            return

        # Get all items from the safe processing key
        raw_items = redis_client.lrange(processing_key, 0, -1)
        
        # Cleanup temporary key
        redis_client.delete(processing_key)
        
        # Clear the 'collecting' lock so new batches can start later
        redis_client.delete(f"user:{user_id}:collecting")
        
        if not raw_items:
            return

        print(f"📦 Batch Processing: {len(raw_items)} items for {user_id}")
        
        unified_texts = []
        
        # 2. Process each item
        for raw in raw_items:
            try:
                item = json.loads(raw)
                m_type = item.get("type")
                content = item.get("content")
                extra = item.get("extra")
                
                extracted_text = _process_single_item(m_type, content, extra)
                if extracted_text and extracted_text.strip():
                    unified_texts.append(extracted_text)
                    
            except Exception as e:
                print(f"❌ Batch item error: {e}")

        # 3. Aggregate
        if not unified_texts:
            final_text = "(Empty or unreadable message)"
        else:
            final_text = "\n\n".join(unified_texts)
            
        print(f"📝 Unified Context: {final_text[:100]}...")

        # 4. Run Core Pipeline
        try:
            replies = process_user_message(user_id, final_text)
            if isinstance(replies, list):
                for reply in replies:
                    send_whatsapp_text(user_id, reply)
                    time.sleep(1) # Small delay for order
            else:
                send_whatsapp_text(user_id, replies)
        except Exception as e:
            print(f"❌ System error sending reply: {e}")
            send_whatsapp_text(user_id, "System Error: Unable to process request.")


def process_whatsapp_message(user_id, content, msg_type="text", extra_data=None):
    """
    LEGACY / SINGLE MODE (Keep for backward compatibility if needed, 
    but Webhook will now prefer collect_and_process_batch)
    """
    # ✅ IMPORT HERE (lazy import)
    from app import create_app
    app = create_app()

    with app.app_context():
        text = _process_single_item(msg_type, content, extra_data)
        if not text.strip():
            text = "(Empty message)"
        
        try:
            replies = process_user_message(user_id, text)
            if isinstance(replies, list):
                for reply in replies:
                    send_whatsapp_text(user_id, reply)
                    time.sleep(1)
            else:
                send_whatsapp_text(user_id, replies)
        except Exception as e:
            print(f"❌ Task failed: {e}")
            fail_msg = "Thank you for your message. I am unable to fetch your details accurately at the moment."
            send_whatsapp_text(user_id, fail_msg)