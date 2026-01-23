# # services/image_intent_router.py

# import base64
# import json
# from typing import Literal
# from flask import current_app
# from openai import OpenAI

# ImageIntent = Literal["vin_plate", "dashboard_warning", "headlight_part", "unknown"]

# def detect_image_intent(img_bytes: bytes, content_type: str) -> ImageIntent:
#     """
#     Decide what the image contains:
#     - VIN plate / chassis number
#     - Dashboard warning light
#     """
#     client = OpenAI(api_key=current_app.config["OPENAI_API_KEY"])
#     model = current_app.config.get("OPENAI_MODEL") or "gpt-4o-mini"

#     image_b64 = base64.b64encode(img_bytes).decode()
#     mime = content_type or "image/jpeg"

#     resp = client.chat.completions.create(
#             model=model,
#             temperature=0,
#             max_tokens=50,
#             messages=[
#                 {
#                     "role": "system",
#                     "content": (
#                         """You are a strict image intent classifier for an automotive support system.

#                         Your task is to classify the image based on visible visual characteristics ONLY.

#                         Use these visual rules:

#                         - vin_plate:
#                         An image containing printed or stamped alphanumeric text used as a vehicle identification number,
#                         usually on a metal plate or sticker.

#                         - dashboard_warning:
#                         An image showing a flat dashboard warning or indicator symbol,
#                         typically an icon, light, or pictogram on a vehicle instrument cluster.

#                         - headlight_part:
#                         An image showing a physical vehicle headlight or headlamp assembly,
#                         including lenses, reflectors, LED strips, projector bowls, or housing.
#                         These images are photographic, three-dimensional, and not flat icons.

#                         - unknown:
#                         Anything that does not clearly match the above categories.

#                         Do NOT identify vehicle brand, model, or year.
#                         Do NOT explain your reasoning.

#                         Return STRICT JSON only."""
#                     ),
#                 },
#                 {
#                     "role": "user",
#                     "content": [
#                         {
#                             "type": "text",
#                             "text": (
#                                 """Classify the image into ONE category ONLY.
#                                 Return JSON strictly in this format:
#                                 { "type": "vin_plate | dashboard_warning | headlight_part | unknown" }"""

#                             ),
#                         },
#                         {
#                             "type": "image_url",
#                             "image_url": {
#                                 "url": f"data:{mime};base64,{image_b64}"
#                             },
#                         },
#                     ],
#                 },
#             ],
#         )
    
#     payload = resp.choices[0].message.content.strip()

#     try:
#         if payload.startswith("```"):
#             payload = "\n".join(payload.splitlines()[1:-1])
#         data = json.loads(payload)
#         return data.get("type", "unknown")
#     except Exception:
#         return "unknown"
import base64
import json
from flask import current_app
from openai import OpenAI
from app.models import IntentPrompt


def detect_image_intent(img_bytes: bytes, content_type: str) -> dict:
    """
    Dynamically classify image intent based on DB-defined image intents.
    """

    # 1️⃣ Fetch active IMAGE intents from DB
    try:
        image_intents = (
            IntentPrompt.query
            .filter_by(is_active=True, intent_type="image")
            .all()
        )
        intent_keys = [row.intent_key for row in image_intents]
    except Exception as e:
        current_app.logger.error(f"DB Error fetching intents: {e}")
        # Fallback to defaults
        intent_keys = ["vin_plate", "car_part_request", "dashboard_warning"]

    if not intent_keys:
        # Should not happen with fallback, but safe check
        return "unknown"

    # 2️⃣ Build dynamic intent list
    intent_list_text = "\n".join([f"- {key}" for key in intent_keys])
    # print("Intent List:\n", intent_list_text)
    system_prompt = f"""
            You are a STRICT image intent classifier for an automotive support system.

            Your task:
            - Classify the image using ONLY visible visual characteristics.
            - Choose exactly ONE intent from the allowed list below.
            - If no intent matches clearly, return "unknown".
            - Do NOT guess based on assumptions.
            - Do NOT identify brand, model, or year.
            - Do NOT explain reasoning.

            Allowed image intents:
            {intent_list_text}

            Output STRICT JSON only:
            {{
            "intent": "<intent_key_or_unknown>",
            "confidence": <number between 0 and 1>
            }}
            """

    # 3️⃣ Prepare image
    client = OpenAI(api_key=current_app.config["OPENAI_API_KEY"])
    model = current_app.config.get("OPENAI_MODEL", "gpt-4o-mini")

    image_b64 = base64.b64encode(img_bytes).decode()
    mime = content_type or "image/jpeg"

    # 4️⃣ Call GPT
    try:
        resp = client.chat.completions.create(
            model=model,
            temperature=0,
            max_tokens=1000,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Classify this image."},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime};base64,{image_b64}"
                            }
                        },
                    ],
                },
            ],
        )

        payload = resp.choices[0].message.content.strip()

        if payload.startswith("```"):
            payload = "\n".join(payload.splitlines()[1:-1])

        data = json.loads(payload)

        intent = data.get("intent", "unknown")
        confidence = float(data.get("confidence", 0.0))

        # 5️⃣ Safety checks
        if intent not in intent_keys or confidence < 0.60:
            return "unknown"

        return intent

    except Exception as e:
        current_app.logger.warning(f"Image intent detection failed: {e}")
        return "unknown"

