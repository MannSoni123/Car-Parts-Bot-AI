import requests
import json
from flask import current_app
from app.redis_client import redis_client

def send_whatsapp_text(wa_id: str, text: str):
    token = current_app.config["META_ACCESS_TOKEN"]
    phone_id = current_app.config["META_PHONE_NUMBER_ID"]

    url = f"https://graph.facebook.com/v18.0/{phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    
    # 1. MESSAGE SPLITTING (Limit is 4096, assume safe limit 4000)
    MAX_CHARS = 4000
    chunks = [text[i:i+MAX_CHARS] for i in range(0, len(text), MAX_CHARS)]
    
    # 2. SEND CHUNKS SEQUENTIALLY
    for i, chunk in enumerate(chunks):
        payload = {
            "messaging_product": "whatsapp",
            "to": wa_id,
            "type": "text",
            "text": {"body": chunk},
        }
        
        # If splitting, add (Part X/Y) suffix to clarify? 
        # Actually better to just send. Order is usually preserved or close enough.
        # But if we want to be nice:
        if len(chunks) > 1:
            # Maybe unnecessary clutter, let's just send raw chunks.
            pass

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=15)
            if resp.status_code not in [200, 201]:
                print(f"❌ [WhatsApp Error] Status: {resp.status_code}, Response: {resp.text}")
            else:
                # print(f"✅ [WhatsApp Sent] Chunk {i+1}/{len(chunks)}")
                pass
        except Exception as e:
            print(f"❌ [WhatsApp Exception]: {e}")

