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

    data = {
        "messaging_product": "whatsapp",
        "to": wa_id,
        "type": "text",
        "text": {"body": text},
    }
    requests.post(url, headers=headers, json=data, timeout=10)
