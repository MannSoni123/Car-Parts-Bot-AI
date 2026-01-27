import hmac
import json
import hashlib
from typing import Any
from flask import Blueprint, current_app, jsonify, request
import requests
from ..extensions import db
from ..models import Lead,Stock
from ..services.gpt_service import GPTService
from ..services.lead_service import LeadService
from sqlalchemy import or_, and_
from ..redis_client import redis_client
import json
from datetime import datetime
from sqlalchemy import func
from ..tasks import task_queue, process_whatsapp_message
from ..services.media_service import download_whatsapp_media as _download_media
whatsapp_bp = Blueprint("whatsapp", __name__)

@whatsapp_bp.get("")
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == current_app.config.get("META_VERIFY_TOKEN"):
        return challenge, 200
    return "Forbidden", 403


@whatsapp_bp.post("")
def receive_message():
    payload: dict[str, Any] = request.get_json(silent=True) or {}
    entries = payload.get("entry", [])

    for entry in entries:
        for change in entry.get("changes", []):
            value = change.get("value", {})

            # Block status webhooks
            if "statuses" in value:
                continue

            messages = value.get("messages", [])
            if not messages:
                continue

            bot_number = value.get("metadata", {}).get("display_phone_number")
            contacts = value.get("contacts", [])
            user_id = contacts[0]["wa_id"] if contacts else None

            for msg in messages:

                msg_id = msg.get("id")
                if msg_id:
                    cache_key = f"whatsapp_msg:{msg_id}"
                    try:
                        if redis_client.exists(cache_key):
                            print("⏭ Skip duplicate:", msg_id)
                            continue
                        redis_client.setex(cache_key, 172800, "processed")
                    except Exception as e:
                        print("⚠️ Redis dedupe failed:", e)
                

                if msg.get("from") == bot_number:
                    print("Skip bot msg")
                    continue

                msg_type = msg.get("type")
                # print("MSG TYPE",msg_type)
                if msg_type == "text":
                    text = msg["text"]["body"].strip().upper()
                    try:
                        redis_client.publish(
                            "chatbot_events",
                            json.dumps({
                                "type": "user_message",
                                "from": user_id,
                                "text": text
                            })
                        )
                    except Exception as e:
                        print("⚠️ Redis dedupe failed:", e)

                    try:
                        task_queue.enqueue(process_whatsapp_message, user_id, text, "text", job_timeout=600)
                    except Exception as e:
                        print("❌ RQ enqueue failed:", e)

                elif msg_type == "image":
                    img_media_id = msg["image"]["id"]
                    try:
                        redis_client.publish(
                            "chatbot_events",
                            json.dumps({
                                "type": "user_image",
                                "from": user_id,
                                "media_id": img_media_id
                            })
                        )
                    except Exception as e:
                        print("⚠️ Redis dedupe failed:", e)

                    try:
                        task_queue.enqueue(process_whatsapp_message, user_id, img_media_id, "image", job_timeout=600)
                    except Exception as e:
                        print("❌ RQ enqueue failed:", e)

                elif msg_type == "audio":
                    media_id = msg["audio"]["id"]
                    try:
                        redis_client.publish(
                            "chatbot_events",
                            json.dumps({
                                "type": "user_audio",
                                "from": user_id,
                                "media_id": media_id
                            })
                        )
                    except Exception as e:
                        print("⚠️ Redis dedupe failed:", e)

                    try:
                    # 🚀 Send to worker for transcription + GPT + reply
                        task_queue.enqueue(process_whatsapp_message, user_id, media_id, "audio", job_timeout=600)
                    except Exception as e:
                        print("❌ RQ enqueue failed:", e)

                elif msg_type == "document":
                    doc = msg.get("document", {})
                    media_id = doc.get("id")
                    filename = doc.get("filename", "document.bin")
                    mime_type = doc.get("mime_type")

                    try:
                        redis_client.publish(
                            "chatbot_events",
                            json.dumps({
                                "type": "user_document",
                                "from": user_id,
                                "media_id": media_id,
                                "filename": filename
                            })
                        )
                    except Exception as e:
                        print("⚠️ Redis dedupe failed:", e)

                    try:
                        task_queue.enqueue(process_whatsapp_message, user_id, media_id, "document", filename, job_timeout=600)
                    except Exception as e:
                        print("❌ RQ enqueue failed:", e)

    # ALWAYS only one final response
    return jsonify({"status": "ok"}), 200
